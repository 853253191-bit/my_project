# -*- coding: utf-8 -*-
"""食谱生成服务（LLM 流式调用）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from shike.config import AppConfig, require_api_key
from shike.db.repository import RecipeRepository
from shike.models.schemas import ChatRequest, GenerateRequest
from shike.rag.prompts import build_chat_prompt, build_generate_prompt
from shike.rag.retriever import RecipeRetriever, build_query
from shike.services.intent import form_to_dict, merge_chat_intent
from shike.services.session import SessionManager
from shike.services.weather import WeatherService


class RecipeGenerator:
    def __init__(
        self,
        config: AppConfig,
        repo: RecipeRepository,
        sessions: SessionManager,
        weather: WeatherService,
    ):
        self.config = config
        self.repo = repo
        self.sessions = sessions
        self.weather = weather
        self.retriever = RecipeRetriever(config, repo)
        api_key = require_api_key(config)
        self._client = AsyncOpenAI(api_key=api_key, base_url=config.llm.base_url)

    def _build_sources(self, recipe_ids: list[str]) -> list[dict[str, str]]:
        sources = []
        for rid in recipe_ids:
            recipe = self.repo.get_by_id(rid)
            if recipe:
                sources.append({
                    "id": rid,
                    "title": recipe.get("title", ""),
                    "source_url": recipe.get("source_url", ""),
                })
        return sources

    async def generate_stream(self, req: GenerateRequest) -> AsyncIterator[str]:
        form = form_to_dict(req)
        weather = await self.weather.get_weather(req.city) if req.city else None
        query = build_query(form)
        context, recipe_ids = self.retriever.retrieve(query, form=form)
        sources = self._build_sources(recipe_ids)

        session = self.sessions.create(form_context=form)
        messages = build_generate_prompt(form, context, weather)

        yield self._sse("session", {"session_id": session.session_id})
        if sources:
            yield self._sse("sources", {"recipes": sources})

        full_text = ""
        async for chunk in self._stream_llm(messages):
            full_text += chunk
            yield self._sse("recipe_chunk", {"type": "content", "content": chunk})

        self.sessions.add_message(session.session_id, "assistant", full_text)
        self.sessions.update_recipe(session.session_id, full_text, sources)
        yield self._sse("done", {"session_id": session.session_id})

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[str]:
        session = self.sessions.get(req.session_id)
        if not session:
            yield self._sse("error", {"message": "会话不存在或已过期"})
            return

        form = merge_chat_intent(session.form_context, req.message)
        query = build_query(form, extra=req.message)
        context, recipe_ids = self.retriever.retrieve(query, form=form)
        sources = self._build_sources(recipe_ids)

        self.sessions.add_message(req.session_id, "user", req.message)
        messages = build_chat_prompt(session.form_context, session.last_recipe, req.message, context)

        if sources:
            yield self._sse("sources", {"recipes": sources})

        full_text = ""
        async for chunk in self._stream_llm(messages):
            full_text += chunk
            yield self._sse("recipe_chunk", {"type": "content", "content": chunk})

        self.sessions.add_message(req.session_id, "assistant", full_text)
        self.sessions.update_recipe(req.session_id, full_text, sources)
        yield self._sse("done", {"session_id": req.session_id})

    async def _stream_llm(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self.config.llm.model,
            messages=messages,
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
            stream=True,
        )
        async for event in stream:
            delta = event.choices[0].delta.content
            if delta:
                yield delta

    @staticmethod
    def _sse(event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
