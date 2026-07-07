# -*- coding: utf-8 -*-
"""策略知识库检索（SPEC §5.3 / §5.4 / §5.5）。"""

from __future__ import annotations

from typing import Any, Protocol

from manus.rag.chunk import format_rag_context

AGENT_QUERY_TEMPLATES: dict[str, str] = {
    "agent1": "AI 硬件产业 终端需求 筛选标准 硬件向",
    "agent2": "产业链拆解 BOM 横向延伸 终端需求 outlook",
    "agent3": "卡点 瓶颈 供需错配 寡头 扩产慢 三阶涟漪",
    "agent4": "断供测试 定量分析 检查清单 red-team 证伪",
    "agent5": "供应商筛选 A股主板 第七章 财务排雷",
    "agent6": "研究报告 检查清单 节奏提示 免责声明",
}

FALLBACK_SNIPPET = """
## 策略知识库 fallback（第二章 七步流程）

1. 终端需求是否成立？
2. 需求由哪些部件/子系统构成？
3. 逐层向上游拆解
4. 识别卡点 / 瓶颈 / 供需错配
5. 不可替代性测试 + 定量分析
6. 筛选供应商
7. 小仓验证 → 等催化剂 → 机构覆盖前建仓

## 第一步：终端需求门槛
未来 2～3 年终端需求会不会停？会停则不继续拆。
""".strip()


class VectorStore(Protocol):
    def similarity_search_with_score(self, query: str, k: int) -> list[tuple[Any, float]]: ...


class StrategyRetriever:
    def __init__(self, store: VectorStore, config: dict[str, Any] | Any):
        self.store = store
        if hasattr(config, "model_dump"):
            self.config = config.model_dump()
        else:
            self.config = dict(config)

    def retrieve(
        self,
        agent_key: str,
        query_extra: str = "",
    ) -> tuple[list[str], list[float]]:
        template = AGENT_QUERY_TEMPLATES.get(agent_key, agent_key)
        query = f"{template} {query_extra}".strip()
        top_k = int(self.config.get("top_k", 5))
        threshold = float(self.config.get("score_threshold", 0.5))

        results = self.store.similarity_search_with_score(query, k=top_k)
        chunks: list[str] = []
        scores: list[float] = []
        for doc, score in results:
            sim = float(score)
            if sim < threshold:
                continue
            text = getattr(doc, "page_content", str(doc))
            chunks.append(text)
            scores.append(sim)
        return chunks, scores

    def retrieve_with_fallback(self, agent_key: str, query_extra: str = "") -> tuple[list[str], list[str]]:
        chunks, _ = self.retrieve(agent_key, query_extra=query_extra)
        errors: list[str] = []
        if not chunks:
            chunks = [build_fallback_context()]
            errors.append("RAG_EMPTY: 使用 fallback 策略片段")
        return chunks, errors


def build_fallback_context() -> str:
    return FALLBACK_SNIPPET
