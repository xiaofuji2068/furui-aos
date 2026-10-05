# Furui AI OS — 后端镜像（TASK-017 / 70-02）
# 构建：docker build -f backend/Dockerfile -t furui-aios-backend:2.0 .
# 运行需注入 DATABASE_URL（生产禁用 SQLite）；schema 由 alembic 管理（见 docs/UPGRADE.md）

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8

WORKDIR /srv/backend

# 依赖层（利用构建缓存）
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码 + 迁移链
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/.env.example ./.env.example

EXPOSE 8000

# 迁移与启动分离：部署窗口先 alembic upgrade head（见 UPGRADE.md），再启动服务
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
