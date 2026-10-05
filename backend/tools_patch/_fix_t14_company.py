# -*- coding: utf-8 -*-
"""TASK-014 修复：logic_nodes 补 company_id 列（RLS 租户过滤必需）。"""
from pathlib import Path

ROOT = Path(r"C:\Users\mymatebook\WorkBuddy\2026-08-31-13-04-07\furui-aios\backend")

# 1) models_ai.py：LogicNode 加 company_id
p = ROOT / "app" / "models_ai.py"
s = p.read_text(encoding="utf-8")
old = '''    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    graph_id: Mapped[int] = mapped_column(ForeignKey("logic_graphs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)'''
new = '''    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    graph_id: Mapped[int] = mapped_column(ForeignKey("logic_graphs.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), default=1, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)'''
assert old in s, "models LogicNode anchor"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK models_ai LogicNode.company_id")

# 2) logic.py：seed 写入 company_id
p = ROOT / "app" / "logic.py"
s = p.read_text(encoding="utf-8")
old = '''        for nd in g["nodes"]:
            db.add(LogicNode(graph_id=graph.id, seq=nd["seq"], key=nd["key"],'''
new = '''        for nd in g["nodes"]:
            db.add(LogicNode(graph_id=graph.id, company_id=company_id,
                             seq=nd["seq"], key=nd["key"],'''
assert old in s, "logic seed anchor"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("OK logic.py seed company_id")

# 3) 迁移：logic_nodes 建表加 company_id；对已建表 ADD COLUMN IF NOT EXISTS（幂等）
p = ROOT / "alembic" / "versions" / "f6a7b8c9d0e1_logic_graphs.py"
s = p.read_text(encoding="utf-8")
old = '''        op.create_table(
            'logic_nodes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('graph_id', sa.Integer(),
                      sa.ForeignKey('logic_graphs.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('seq', sa.Integer(), nullable=False),'''
new = '''        op.create_table(
            'logic_nodes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('graph_id', sa.Integer(),
                      sa.ForeignKey('logic_graphs.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('company_id', sa.Integer(),
                      sa.ForeignKey('companies.id', ondelete='CASCADE'),
                      nullable=False, server_default='1'),
            sa.Column('seq', sa.Integer(), nullable=False),'''
assert old in s, "migration create anchor"
s = s.replace(old, new, 1)
# 对已建表（迁移中途失败）补列
old = "    if bind.dialect.name == 'postgresql':"
new = """    if sa.inspect(bind).has_table('logic_nodes'):
        op.execute("ALTER TABLE logic_nodes ADD COLUMN IF NOT EXISTS company_id INTEGER NOT NULL DEFAULT 1;")
        op.create_index('ix_logic_nodes_company_id', 'logic_nodes', ['company_id'], unique=False)
    if bind.dialect.name == 'postgresql':"""
assert old in s, "migration pg anchor"
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("OK migration company_id + 幂等补列")