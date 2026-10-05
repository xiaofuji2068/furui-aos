"""企业知识检索 RAG（TASK-013 / TASK-015）。

设计要点
--------
1. **Embedding 双引擎，自动降级**
   有 dashscope key  → 通义 text-embedding-v3，真实语义向量（1024 维）
   无 key（默认）    → 本地哈希向量，同样 1024 维
   两者维度一致，所以切换引擎不需要重建索引结构，填上 key 即刻升级为语义检索。
   这样保证「没有 key 也能端到端跑通并演示」，符合离线兜底要求。

2. **混合检索**
   语义分数（余弦）与关键词分数（字符 2-gram 加权 TF-IDF）加权融合，
   再对候选集做 Rerank。纯向量检索在中文短句上召回不稳，纯关键词又缺乏语义泛化。

3. **权限过滤前置**
   不是「先检索再过滤」，而是把白名单下推到查询条件里 ——
   Agent 只能看到 allowed_knowledge_ids 内的知识库，用户只能看到本部门可见的知识库，
   且只检索「已发布」且在有效期内的文档。

4. **结果可溯源**
   每条命中都带 doc_id / title / version / source / 有效期，
   满足清单「必须记录使用了哪些文档、文档版本、文档来源」的验收标准。
"""
from __future__ import annotations

import array
import json
import math
import re
import zlib
from datetime import datetime
from typing import Any, Dict, List, Sequence

import httpx

from .config import settings
from .models_ai import KnowledgeChunk, KnowledgeDocument, KnowledgeBase


# ==================== 文本切分（TASK-013） ====================

def chunk_text(text: str, size: int = 400, overlap: int = 60) -> List[str]:
    """按段落优先、长度兜底切分，保留 overlap 以维持跨块语义连贯。"""
    text = (text or "").strip()
    if not text:
        return []

    chunks: List[str] = []
    buf = ""
    for para in re.split(r"\n\s*\n|\n", text):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) <= size:
            buf = f"{buf}\n{para}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = para
        while len(buf) > size:
            chunks.append(buf[:size])
            buf = buf[size - overlap:]
    if buf:
        chunks.append(buf)

    # 补 overlap
    if overlap > 0 and len(chunks) > 1:
        merged: List[str] = []
        for i, c in enumerate(chunks):
            if i > 0:
                c = chunks[i - 1][-overlap:] + c
            merged.append(c)
        chunks = merged
    return chunks


# ==================== Embedding ====================

def _tokens(text: str) -> List[str]:
    """中英文统一的字符 2-gram 分词。中文无空格，2-gram 是性价比最高的离线方案。"""
    s = re.sub(r"\s+", "", (text or "").lower())
    if not s:
        return []
    if len(s) == 1:
        return [s]
    return [s[i:i + 2] for i in range(len(s) - 1)]


def _l2(vec: Sequence[float]) -> List[float]:
    n = math.sqrt(sum(v * v for v in vec))
    return [v / n for v in vec] if n else list(vec)


def _hash_embed(text: str, dim: int) -> List[float]:
    """本地确定性哈希向量（离线兜底引擎）。

    字符 2-gram → crc32 稳定散列 → 词频累加 → L2 归一化。
    语义泛化弱于模型向量，但能稳定召回字面重叠内容，且零依赖、零成本、可离线。
    """
    vec = [0.0] * dim
    toks = _tokens(text)
    if not toks:
        return vec
    for t in toks:
        vec[zlib.crc32(t.encode("utf-8")) % dim] += 1.0
    return _l2(vec)


def _remote_embed(texts: List[str], dim: int) -> List[List[float]] | None:
    """通义 text-embedding-v3。失败返回 None，由调用方降级。"""
    if not settings.embedding_enabled:
        return None
    url = f"{settings.dashscope_base_url}/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.embedding_model,
        "input": texts,
        "dimension": dim,
        "encoding_format": "float",
    }
    try:
        with httpx.Client(timeout=30.0) as cli:
            r = cli.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json().get("data", [])
        if len(data) != len(texts):
            return None
        try:
            from .api.health import mark_embedding_call
            mark_embedding_call(True, "语义检索正常")
        except Exception:  # noqa: BLE001
            pass
        return [_l2(d["embedding"]) for d in data]
    except Exception:
        return None


def embed(texts: List[str]) -> List[List[float]]:
    """统一入口：优先远端，失败/无 key 自动降级本地。"""
    if not texts:
        return []
    dim = settings.embedding_dim
    remote = _remote_embed(texts, dim)
    if remote:
        return remote
    return [_hash_embed(t, dim) for t in texts]


def engine_name() -> str:
    return "通义 text-embedding-v3" if settings.embedding_enabled else "本地哈希向量（离线兜底）"


# 向量序列化：float32 紧凑存储
def pack_vec(vec: Sequence[float]) -> bytes:
    return array.array("f", vec).tobytes()


def unpack_vec(blob: bytes | None) -> List[float] | None:
    if not blob:
        return None
    a = array.array("f")
    a.frombytes(blob)
    return list(a)


# ==================== 索引（TASK-013 向量入库） ====================

def index_document(db, doc: KnowledgeDocument, text: str) -> int:
    """文档 → 切块 → Embedding → 向量入库。返回分块数。"""
    # 幂等：重建索引前先清旧块
    db.query(KnowledgeChunk).filter(KnowledgeChunk.doc_id == doc.id).delete()

    chunks = chunk_text(text)
    if not chunks:
        doc.chunk_count = 0
        doc.char_count = 0
        return 0

    vectors = embed(chunks)
    now = datetime.utcnow()
    for i, (c, v) in enumerate(zip(chunks, vectors)):
        db.add(KnowledgeChunk(
            doc_id=doc.id,
            kb_id=doc.kb_id,
            company_id=doc.company_id,
            seq=i,
            content=c,
            embedding=pack_vec(v),
            embedding_model=engine_name(),
        ))
    doc.chunk_count = len(chunks)
    doc.char_count = len(text)
    doc.updated_at = now
    db.flush()
    return len(chunks)


# ==================== 检索（TASK-015） ====================

def _keyword_scores(query: str, corpus: List[str]) -> List[float]:
    """字符 2-gram 的 TF-IDF 近似打分。"""
    qtoks = set(_tokens(query))
    if not qtoks:
        return [0.0] * len(corpus)

    doc_toks = [ _tokens(c) for c in corpus ]
    n = len(corpus)
    # 文档频率
    df: Dict[str, int] = {}
    for toks in doc_toks:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1

    scores = []
    for toks in doc_toks:
        if not toks:
            scores.append(0.0)
            continue
        tf: Dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for t in qtoks:
            if t in tf:
                idf = math.log((n + 1) / (df.get(t, 0) + 1)) + 1.0
                s += (1 + math.log(tf[t])) * idf
        scores.append(s)
    return scores


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    # 入库向量已 L2 归一化，点积即余弦
    return sum(x * y for x, y in zip(a, b))


def search(
    db,
    query: str,
    *,
    company_id: int,
    kb_ids: List[int] | None = None,
    department_id: int | None = None,
    top_k: int = 5,
    candidate_k: int = 30,
) -> Dict[str, Any]:
    """混合检索：语义 + 关键词 + Rerank + 权限过滤。

    权限过滤下推到 SQL，禁止「先取回再过滤」——越权内容不该进入内存。
    """
    q = (query or "").strip()
    if not q:
        return {"hits": [], "engine": engine_name(), "query": q}

    now = datetime.utcnow()

    # ---- 权限过滤（前置）----
    base = (
        db.query(KnowledgeChunk, KnowledgeDocument, KnowledgeBase)
        .join(KnowledgeDocument, KnowledgeChunk.doc_id == KnowledgeDocument.id)
        .join(KnowledgeBase, KnowledgeChunk.kb_id == KnowledgeBase.id)
        .filter(KnowledgeChunk.company_id == company_id)
        .filter(KnowledgeDocument.status == "已发布")          # 只有已发布知识可被检索
        .filter(KnowledgeBase.status == "active")
        .filter(
            (KnowledgeDocument.valid_to.is_(None)) | (KnowledgeDocument.valid_to >= now)
        )
    )
    if kb_ids is not None:
        base = base.filter(KnowledgeChunk.kb_id.in_(kb_ids) if kb_ids else KnowledgeChunk.kb_id.in_([-1]))
    if department_id is not None:
        # 知识库可见范围：空 = 企业内公开；否则需命中部门
        base = base.filter(
            (KnowledgeBase.allowed_department_ids == "[]")
            | (KnowledgeBase.allowed_department_ids.like(f"%{department_id}%"))
        )

    rows = base.limit(candidate_k * 4).all()
    if not rows:
        return {"hits": [], "engine": engine_name(), "query": q, "candidates": 0}

    chunks = [r[0] for r in rows]
    corpus = [c.content for c in chunks]

    # ---- 语义 + 关键词 ----
    qvecs = embed([q])
    qvec = qvecs[0] if qvecs else []
    vecs = [unpack_vec(c.embedding) for c in chunks]

    sem = [_cosine(qvec, v) if (v and qvec) else 0.0 for v in vecs]
    kw = _keyword_scores(q, corpus)

    def norm(xs: List[float]) -> List[float]:
        lo, hi = min(xs), max(xs)
        if hi - lo < 1e-9:
            return [0.0] * len(xs)
        return [(x - lo) / (hi - lo) for x in xs]

    sem_n, kw_n = norm(sem), norm(kw)
    fused = [0.68 * s + 0.32 * k for s, k in zip(sem_n, kw_n)]

    # ---- Rerank：综合分排序，融合分相同时以权威等级与文档版本优先 ----
    scored = []
    for i, (chunk, doc, kb) in enumerate(rows):
        boost = 1.0 + (5 - kb.authority_level) * 0.02      # 权威等级 1 级最高
        scored.append({
            "score": round(fused[i] * boost, 4),
            "semantic": round(sem_n[i], 4),
            "keyword": round(kw_n[i], 4),
            "content": chunk.content,
            "chunk_id": chunk.id,
            "doc_id": doc.id,
            "doc_title": doc.title,
            "doc_version": doc.version,
            "doc_source": doc.source or kb.name,
            "kb_id": kb.id,
            "kb_name": kb.name,
            "authority_level": kb.authority_level,
            "valid_to": doc.valid_to.isoformat() if doc.valid_to else None,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)

    return {
        "query": q,
        "engine": engine_name(),
        "candidates": len(rows),
        "hits": scored[:top_k],
    }


def format_citations(hits: List[Dict[str, Any]]) -> str:
    """把命中结果格式化为可附在回答末尾的引用块。"""
    if not hits:
        return ""
    seen: Dict[int, Dict[str, Any]] = {}
    for h in hits:
        seen.setdefault(h["doc_id"], h)
    lines = ["\n\n---\n**知识来源**"]
    for h in seen.values():
        v = f" v{h['doc_version']}"
        lines.append(f"- 《{h['doc_title']}》{v} · 来源：{h['doc_source']}")
    return "\n".join(lines)
