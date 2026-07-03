"""
阶段三：Prompt 与答案 Schema 测试（tests/phase3/test_prompts.py）

主要功能：
- 测试 PlanningDocAnswerPrompt 系统/用户 Prompt 构建
- 测试 build_rag_context 格式化检索片段
- 测试 PlanningDocAnswer Pydantic 校验与 NOT_FOUND 场景

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase3/test_prompts.py -v
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.config import NOT_FOUND_ANSWER
from src.prompts import (
    PlanningDocAnswer,
    PlanningDocAnswerPrompt,
    Reference,
    build_rag_context,
)


@pytest.mark.phase3
class TestPlanningDocAnswerSchema:
    def test_valid_answer(self):
        answer = PlanningDocAnswer(
            step_by_step_analysis="分析步骤",
            reasoning_summary="摘要",
            references=[
                Reference(
                    doc_title="D06单元控规调整",
                    doc_id="2021-KS-0017",
                    page=5,
                    excerpt="二类居住用地",
                )
            ],
            final_answer="答案内容",
        )
        assert answer.final_answer == "答案内容"

    def test_reference_requires_positive_page(self):
        with pytest.raises(ValidationError):
            Reference(
                doc_title="x",
                doc_id="x",
                page=0,
                excerpt="e",
            )


@pytest.mark.phase3
class TestPlanningDocAnswerPrompt:
    def test_system_prompt_contains_not_found_instruction(self):
        prompt = PlanningDocAnswerPrompt.build_system_prompt()
        assert NOT_FOUND_ANSWER in prompt
        assert "references" in prompt

    def test_build_rag_context_format(self):
        chunks = [
            {
                "doc_title": "D06单元控规调整",
                "page": 5,
                "text": "用地性质包括二类居住用地。",
            }
        ]
        context = build_rag_context(chunks)
        assert "D06单元控规调整" in context
        assert "二类居住用地" in context


@pytest.mark.phase3
class TestNotFoundAnswerParsing:
    def test_not_found_has_empty_references(self):
        answer = PlanningDocAnswer(
            step_by_step_analysis="无相关内容",
            reasoning_summary="无",
            references=[],
            final_answer=NOT_FOUND_ANSWER,
        )
        data = json.loads(answer.model_dump_json())
        assert data["references"] == []
        assert data["final_answer"] == NOT_FOUND_ANSWER
