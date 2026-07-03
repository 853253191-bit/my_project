"""
DashScope 问答 API 封装（src/api_requests.py）

主要功能：
- DashscopeProcessor：调用通义千问 Generation API（默认 qwen-plus）
- 解析 LLM 返回的 JSON 答案，支持 json_repair 修复格式
- APIProcessor.get_planning_doc_answer：检索上下文 + Prompt → 结构化答案

如何调用：
  from src.api_requests import APIProcessor

  api = APIProcessor(provider="dashscope")
  answer = api.get_planning_doc_answer("问题", retrieval_chunks, model="qwen-plus")
  # 由 QuestionsProcessor._generate_answer() 调用
"""
from __future__ import annotations

import json
import os
import re

import dashscope
from dotenv import load_dotenv
from json_repair import repair_json

from src.config import NOT_FOUND_ANSWER
from src.prompts import PlanningDocAnswer, PlanningDocAnswerPrompt, build_rag_context


class DashscopeProcessor:
    def __init__(self):
        load_dotenv()
        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.default_model = "qwen-plus"
        self.response_data: dict = {}

    def send_message(
        self,
        model: str | None = None,
        temperature: float = 0.1,
        system_content: str = "",
        human_content: str = "",
    ) -> dict:
        if not dashscope.api_key:
            raise ValueError("未设置环境变量 DASHSCOPE_API_KEY")
        if model is None:
            model = self.default_model
        messages = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        if human_content:
            messages.append({"role": "user", "content": human_content})
        response = dashscope.Generation.call(
            model=model,
            messages=messages,
            temperature=temperature,
            result_format="message",
        )
        if response.status_code != 200:
            raise RuntimeError(f"DashScope API 错误: {response.code} {response.message}")
        content = response.output.choices[0].message.content
        self.response_data = {
            "model": model,
            "input_tokens": getattr(response.usage, "input_tokens", None),
            "output_tokens": getattr(response.usage, "output_tokens", None),
        }
        return self._parse_json_content(content)

    @staticmethod
    def _parse_json_content(content: str) -> dict:
        text = content.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            repaired = repair_json(text)
            return json.loads(repaired)


class APIProcessor:
    def __init__(self, provider: str = "dashscope"):
        if provider != "dashscope":
            raise ValueError(f"本项目仅支持 dashscope，收到: {provider}")
        self.processor = DashscopeProcessor()

    def get_planning_doc_answer(
        self,
        question: str,
        retrieval: list[dict],
        model: str | None = None,
    ) -> dict:
        """根据检索上下文生成规划文档结构化答案。"""
        rag_context = build_rag_context(retrieval)
        system_prompt = PlanningDocAnswerPrompt.build_system_prompt()
        user_prompt = PlanningDocAnswerPrompt.build_user_prompt(question, rag_context)
        raw = self.processor.send_message(
            model=model,
            system_content=system_prompt,
            human_content=user_prompt,
        )
        return self._normalize_answer(raw)

    @staticmethod
    def _normalize_answer(raw: dict) -> dict:
        try:
            answer = PlanningDocAnswer.model_validate(raw)
            return json.loads(answer.model_dump_json())
        except Exception:
            final = raw.get("final_answer", NOT_FOUND_ANSWER)
            return {
                "step_by_step_analysis": raw.get("step_by_step_analysis", ""),
                "reasoning_summary": raw.get("reasoning_summary", ""),
                "references": raw.get("references", []),
                "final_answer": final,
            }
