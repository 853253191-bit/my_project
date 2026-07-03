"""
阶段三：Pipeline 单问接口测试（tests/phase3/test_pipeline_qa.py）

主要功能：
- 测试 Pipeline.answer_single_question 委托 QuestionsProcessor
- 测试问答配置（enterprise_config）正确传入
- mock 处理器，验证返回结构含 final_answer、references

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase3/test_pipeline_qa.py -v
"""
from __future__ import annotations

import pytest

from src.config import NOT_FOUND_ANSWER, enterprise_config
from src.pipeline import Pipeline


@pytest.mark.phase3
class TestAnswerSingleQuestion:
    def test_answer_single_question_delegates_to_processor(self, tmp_data_root, mocker):
        pipeline = Pipeline(root_path=tmp_data_root, run_config=enterprise_config())
        expected = {
            "step_by_step_analysis": "a",
            "reasoning_summary": "b",
            "references": [],
            "final_answer": "c",
            "retrieval_debug": [],
        }
        processor_instance = mocker.patch.object(
            pipeline, "_get_questions_processor",
        ).return_value
        processor_instance.process_single_question.return_value = expected

        result = pipeline.answer_single_question("测试问题")

        assert result == expected

    def test_answer_single_question_flat_structure(self, tmp_data_root, mocker):
        pipeline = Pipeline(root_path=tmp_data_root, run_config=enterprise_config())
        mocker.patch.object(
            pipeline, "_get_questions_processor",
        ).return_value.process_single_question.return_value = {
            "step_by_step_analysis": "x",
            "reasoning_summary": "y",
            "references": [{"doc_title": "T", "doc_id": "id", "page": 1, "excerpt": "e"}],
            "final_answer": "答案",
        }

        result = pipeline.answer_single_question("问题")
        assert "content" not in result
        assert result["final_answer"] == "答案"

    def test_rejection_answer(self, tmp_data_root, mocker):
        pipeline = Pipeline(root_path=tmp_data_root, run_config=enterprise_config())
        mocker.patch.object(
            pipeline, "_get_questions_processor",
        ).return_value.process_single_question.return_value = {
            "step_by_step_analysis": "无",
            "reasoning_summary": "无",
            "references": [],
            "final_answer": NOT_FOUND_ANSWER,
        }

        result = pipeline.answer_single_question("2025年昆山GDP是多少")
        assert result["final_answer"] == NOT_FOUND_ANSWER
