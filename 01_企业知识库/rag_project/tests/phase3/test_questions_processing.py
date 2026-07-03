"""
阶段三：问答处理测试（tests/phase3/test_questions_processing.py）

主要功能：
- 测试 QuestionsProcessor 检索为空时返回 NOT_FOUND_ANSWER
- 测试重排、生成、引用校验流程（mock 检索与 API）
- 测试 validate_references 过滤无效页码引用

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase3/test_questions_processing.py -v
"""
from __future__ import annotations

import pytest

from src.config import NOT_FOUND_ANSWER, enterprise_config
from src.questions_processing import QuestionsProcessor


@pytest.mark.phase3
class TestQuestionsProcessor:
    @pytest.fixture
    def processor(self, tmp_data_root):
        return QuestionsProcessor(data_root=tmp_data_root, run_config=enterprise_config())

    def test_process_single_question_returns_flat_dict(self, processor, mocker):
        mocker.patch.object(
            processor,
            "_retrieve",
            return_value=[{"doc_id": "2021-KS-0017", "page": 5, "text": "用地", "doc_title": "D06"}],
        )
        mocker.patch.object(processor, "_rerank_if_enabled", side_effect=lambda x, q: x)
        mocker.patch.object(
            processor,
            "_generate_answer",
            return_value={
                "step_by_step_analysis": "步骤",
                "reasoning_summary": "摘要",
                "references": [
                    {"doc_title": "D06", "doc_id": "2021-KS-0017", "page": 5, "excerpt": "用地"}
                ],
                "final_answer": "答案",
            },
        )

        result = processor.process_single_question("D06单元控规调整涉及哪些用地性质？")

        assert isinstance(result, dict)
        assert "final_answer" in result
        assert "references" in result
        assert not isinstance(result["final_answer"], dict)

    def test_empty_retrieval_returns_not_found(self, processor, mocker):
        mocker.patch.object(processor, "_retrieve", return_value=[])
        result = processor.process_single_question("不存在的问题")
        assert result["final_answer"] == NOT_FOUND_ANSWER
        assert result["references"] == []

    def test_validate_references_filters_invalid_pages(self, processor):
        retrieval = [{"page": 5, "doc_id": "2021-KS-0017", "doc_title": "D06", "text": "x"}]
        raw_refs = [
            {"doc_title": "D06", "doc_id": "2021-KS-0017", "page": 5, "excerpt": "ok"},
            {"doc_title": "D06", "doc_id": "2021-KS-0017", "page": 99, "excerpt": "bad"},
        ]
        validated = processor.validate_references(raw_refs, retrieval)
        pages = [r["page"] for r in validated]
        assert 5 in pages
        assert 99 not in pages
