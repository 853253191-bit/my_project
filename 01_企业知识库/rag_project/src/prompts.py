"""
问答 Prompt 与结构化答案 Schema（src/prompts.py）

主要功能：
- 定义规划文档问答的系统/用户 Prompt 模板
- build_rag_context：将检索片段格式化为 LLM 上下文
- PlanningDocAnswer：约束 LLM 输出 JSON（final_answer、references 等）

如何调用：
  from src.prompts import build_rag_context, PlanningDocAnswerPrompt

  ctx = build_rag_context(retrieval_chunks)
  user_prompt = PlanningDocAnswerPrompt.build_user_prompt("问题", ctx)
  # 由 api_requests.APIProcessor.get_planning_doc_answer() 调用
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.config import NOT_FOUND_ANSWER


class Reference(BaseModel):
    doc_title: str
    doc_id: str
    page: int = Field(gt=0)
    excerpt: str = Field(max_length=200)


class PlanningDocAnswer(BaseModel):
    step_by_step_analysis: str
    reasoning_summary: str
    references: list[Reference]
    final_answer: str


class PlanningDocAnswerPrompt:
    @staticmethod
    def build_system_prompt() -> str:
        return (
            "你是城市规划领域知识库问答助手，仅依据提供的检索上下文回答问题。\n"
            "必须输出合法 JSON，字段包括：step_by_step_analysis、reasoning_summary、"
            "references（数组，每项含 doc_title、doc_id、page、excerpt）、final_answer。\n"
            "约束：\n"
            "1. 不得编造未在上下文中出现的数据、页码或规划指标；\n"
            "2. references 中的 page 必须来自上下文标注的页码；\n"
            "3. excerpt 不超过 200 字，且须能在对应片段中找到依据；\n"
            "4. 允许综合多份文档，每条 reference 对应一个来源；\n"
            f"5. 若上下文无法回答问题，final_answer 必须为「{NOT_FOUND_ANSWER}」，"
            "且 references 为空数组；\n"
            "6. 使用简体中文。"
        )

    @staticmethod
    def build_user_prompt(question: str, rag_context: str) -> str:
        return (
            "以下是检索到的规划文档片段：\n\n"
            f"{rag_context}\n\n"
            "请根据上述内容回答以下问题，并按要求输出 JSON：\n"
            f"{question}"
        )


def build_rag_context(chunks: list[dict[str, Any]]) -> str:
    """将检索片段格式化为 RAG 上下文。"""
    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        doc_title = chunk.get("doc_title", "")
        doc_id = chunk.get("doc_id", "")
        page = chunk.get("page", "")
        text = chunk.get("text", "")
        parts.append(
            f"[片段{i}] 文档：{doc_title}（{doc_id}）第{page}页\n{text}"
        )
    return "\n\n".join(parts)
