"""
单问/批量问答编排（src/questions_processing.py）

主要功能：
- 串联检索 → 重排 → LLM 生成 → 引用校验的完整问答流程
- process_single_question：回答单个问题（Streamlit / 交互式使用）
- process_all_questions：读取 questions.json 批量评测并输出 answers.json

如何调用：
  from pathlib import Path
  from src.questions_processing import QuestionsProcessor
  from src.config import enterprise_config

  processor = QuestionsProcessor(Path("data/项目知识库"), enterprise_config())
  answer = processor.process_single_question("村庄规划编制要求？")
  # 或由 Pipeline.answer_single_question() / main.py process-questions 调用
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.api_requests import APIProcessor
from src.config import NOT_FOUND_ANSWER, EnterpriseRunConfig
from src.prompts import build_rag_context
from src.reranking import BgeReranker
from src.retrieval import VectorRetriever


class QuestionsProcessor:
    def __init__(
        self,
        data_root: Path,
        run_config: EnterpriseRunConfig,
        questions_file_path: Path | None = None,
    ):
        self.data_root = data_root
        self.run_config = run_config
        self.questions_file_path = questions_file_path
        self._retriever: VectorRetriever | None = None
        self._reranker: BgeReranker | None = None
        self._api: APIProcessor | None = None

    def _get_retriever(self) -> VectorRetriever:
        if self._retriever is None:
            self._retriever = VectorRetriever(data_root=self.data_root)
        return self._retriever

    def _get_reranker(self) -> BgeReranker:
        if self._reranker is None:
            self._reranker = BgeReranker(model=self.run_config.rerank_model)
        return self._reranker

    def _get_api(self) -> APIProcessor:
        if self._api is None:
            self._api = APIProcessor(provider=self.run_config.api_provider)
        return self._api

    def _retrieve(self, question: str) -> list[dict[str, Any]]:
        return self._get_retriever().retrieve_all(
            question,
            per_index_top_n=self.run_config.per_index_top_n,
            global_top_k=self.run_config.rerank_sample_size,
        )

    def _rerank_if_enabled(
        self,
        candidates: list[dict[str, Any]],
        question: str,
    ) -> list[dict[str, Any]]:
        if not self.run_config.use_reranking or not candidates:
            return candidates
        return self._get_reranker().rerank(
            question,
            candidates,
            top_n=self.run_config.top_n_retrieval,
        )

    def _expand_parent_pages(
        self,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """若启用 parent_document_retrieval，合并同页片段。"""
        if not self.run_config.parent_document_retrieval:
            return chunks
        merged: dict[tuple[str, int], dict[str, Any]] = {}
        for chunk in chunks:
            key = (chunk.get("doc_id", ""), chunk.get("page", 0))
            if key not in merged:
                merged[key] = dict(chunk)
            else:
                merged[key]["text"] = merged[key]["text"] + "\n" + chunk["text"]
        return list(merged.values())

    def _generate_answer(
        self,
        question: str,
        retrieval: list[dict[str, Any]],
    ) -> dict[str, Any]:
        expanded = self._expand_parent_pages(retrieval)
        return self._get_api().get_planning_doc_answer(
            question=question,
            retrieval=expanded,
            model=self.run_config.answering_model,
        )

    def validate_references(
        self,
        raw_refs: list[dict[str, Any]],
        retrieval: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """过滤页码不在检索结果中的引用。"""
        valid_pages = {(r.get("doc_id"), r.get("page")) for r in retrieval}
        validated: list[dict[str, Any]] = []
        for ref in raw_refs:
            key = (ref.get("doc_id"), ref.get("page"))
            if key in valid_pages:
                validated.append(ref)
        return validated

    def process_single_question(self, question: str) -> dict[str, Any]:
        retrieval = self._retrieve(question)
        if not retrieval:
            return {
                "step_by_step_analysis": "检索结果为空，无法在知识库中找到相关内容。",
                "reasoning_summary": "无相关内容",
                "references": [],
                "final_answer": NOT_FOUND_ANSWER,
                "retrieval_debug": [],
            }
        reranked = self._rerank_if_enabled(retrieval, question)
        answer = self._generate_answer(question, reranked)
        answer["references"] = self.validate_references(
            answer.get("references", []),
            retrieval,
        )
        answer["retrieval_debug"] = reranked
        return answer

    def process_all_questions(self, output_path: Path) -> list[dict[str, Any]]:
        if self.questions_file_path is None or not self.questions_file_path.exists():
            raise FileNotFoundError(f"问题文件不存在: {self.questions_file_path}")
        questions = json.loads(self.questions_file_path.read_text(encoding="utf-8"))
        results: list[dict[str, Any]] = []
        for item in questions:
            question_text = item["text"]
            answer = self.process_single_question(question_text)
            results.append({
                "question": question_text,
                "kind": item.get("kind", "string"),
                **answer,
            })
        output_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return results
