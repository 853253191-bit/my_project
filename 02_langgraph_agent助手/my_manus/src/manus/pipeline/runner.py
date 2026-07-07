# -*- coding: utf-8 -*-
"""PipelineRunner：串行执行 Agent 与 resolve（SPEC §3.2）。"""

from __future__ import annotations

import importlib
from typing import Any

from manus.api.step_output import as_json, build_step_output
from manus.config import config_to_dict
from manus.pipeline.constants import AGENT_NAMES, validate_step
from manus.pipeline.field_clear import apply_field_clear
from manus.pipeline.gates import build_approval_hints, gate_checklist, gate_outlook
from manus.pipeline.normalize import normalize_state_models
from manus.pipeline.normalize import normalize_state_models
from manus.pipeline.progress import bind_progress_context, reset_progress_context
from manus.pipeline.state import PipelineState
from manus.schemas.models import ApprovalHints, NewsItem
from manus.steps.agent1_news import _normalize_news


class StepNotAwaitingError(Exception):
    """当前 run 不在 awaiting_step_approval 状态。"""


class DuplicateResolveError(Exception):
    """重复 resolve（等价 HTTP 409）。"""


class PipelineRunner:
    def __init__(self, config: dict[str, Any] | Any, run_manager: Any, event_hub: Any | None = None):
        self.config = config_to_dict(config)
        self.run_manager = run_manager
        self.event_hub = event_hub

    def _approval_required(self) -> bool:
        return bool(self.config.get("workflow", {}).get("step_approval_required", True))

    def _emit(self, run_id: str, event: str, **payload: Any) -> None:
        if self.event_hub is not None:
            self.event_hub.emit(run_id, event, **payload)

    def _progress_emitter(self, run_id: str):
        def emitter(
            message: str,
            *,
            kind: str = "progress",
            agent: int | None = None,
            run_id: str | None = None,
            **_: Any,
        ) -> None:
            self._emit(
                run_id,
                "agent_progress",
                agent=agent,
                message=message,
                kind=kind,
            )

        return emitter

    def _item_count(self, state: PipelineState, step: int) -> int:
        if step == 0:
            return len(state.news_items)
        if step == 2:
            return len(state.bottlenecks)
        if step == 3:
            return len(state.validations)
        if step == 4:
            return len(state.suppliers)
        return 0

    async def run_single_step(self, run_id: str, step: int) -> PipelineState:
        validate_step(step)
        state = self.run_manager.load_state(run_id)
        state = normalize_state_models(state)
        agent = step + 1
        state.status = "running"
        state.rerun_from_step = step
        self.run_manager.save_state(state)

        self._emit(
            run_id,
            "agent_start",
            agent=agent,
            agent_name=AGENT_NAMES[step],
        )
        tokens = bind_progress_context(run_id, agent, self._progress_emitter(run_id))

        try:
            result = await self._execute_agent(state, step)
            self._apply_agent_result(state, step, result)
            self._apply_gates(state, step, result)
        except Exception as exc:
            state.errors.append(f"agent_error step{step}: {exc}")
            state.approval_hints = build_approval_hints(state, step, degraded=True)
            state.status = "awaiting_step_approval"
            state.pending_approval_step = step
            self.run_manager.save_state(state)
            self._emit(run_id, "agent_error", agent=agent, error=str(exc))
            raise
        finally:
            reset_progress_context(tokens)

        if self._approval_required():
            state.status = "awaiting_step_approval"
            state.pending_approval_step = step
        else:
            state.status = "running"
            state.pending_approval_step = None

        self.run_manager.save_state(state)
        if hasattr(self.run_manager, "append_log"):
            self.run_manager.append_log(run_id, f"step{step} completed -> {state.status}")

        self._emit(
            run_id,
            "agent_complete",
            agent=agent,
            agent_name=AGENT_NAMES[step],
            summary=state.step_output_summary or "",
            item_count=self._item_count(state, step),
        )

        if state.status == "awaiting_step_approval":
            hints = state.approval_hints or ApprovalHints()
            self._emit(
                run_id,
                "step_approval_required",
                step=step,
                agent=agent,
                agent_name=AGENT_NAMES[step],
                step_output_summary=state.step_output_summary or "",
                output=build_step_output(state, step),
                approval_hints=as_json(hints),
            )
        elif state.status == "completed":
            self._emit(
                run_id,
                "run_complete",
                report_output_path=state.report_output_path,
                confidence=as_json(state.confidence),
            )

        return state

    def _max_deepen_retries(self) -> int:
        return int(self.config.get("workflow", {}).get("max_deepen_retries", 1))

    def _should_deepen_on_rerun(self, state: PipelineState) -> bool:
        hints = state.approval_hints
        if hints is None:
            return False
        suggest = hints.suggest_deepen_bom if hasattr(hints, "suggest_deepen_bom") else bool(
            hints.get("suggest_deepen_bom")
        )
        return bool(suggest) and state.bom_deepen_count < self._max_deepen_retries()

    async def _run_agent_internal(self, run_id: str, step: int) -> PipelineState:
        """仅执行 Agent 逻辑（不触发 step 确认），用于加深 BOM 后衔接瓶颈识别。"""
        state = self.run_manager.load_state(run_id)
        state = normalize_state_models(state)
        agent = step + 1
        tokens = bind_progress_context(run_id, agent, self._progress_emitter(run_id))
        try:
            result = await self._execute_agent(state, step)
            self._apply_agent_result(state, step, result)
            self._apply_gates(state, step, result)
        finally:
            reset_progress_context(tokens)
        self.run_manager.save_state(state)
        return state

    async def _execute_agent(self, state: PipelineState, step: int) -> dict[str, Any]:
        from manus.pipeline.constants import AGENT_STEP_MODULES

        module_path = AGENT_STEP_MODULES[step]
        module = importlib.import_module(module_path)
        runner_name = f"run_agent{step + 1}"
        fn = getattr(module, runner_name)
        state_dict = state.model_dump(mode="json")
        if state.bom_deepen_count > 0:
            state_dict["deepen_bom"] = True
            state_dict["bom_deepen_count"] = state.bom_deepen_count
        return await fn(state_dict, config=self.config)

    def _apply_agent_result(self, state: PipelineState, step: int, result: dict[str, Any]) -> None:
        if result.get("step_output_summary"):
            state.step_output_summary = result["step_output_summary"]
        for key in (
            "news_items",
            "component_node",
            "gate_outlook_result",
            "bottlenecks",
            "ripple_notes",
            "validations",
            "red_team",
            "checklist_gate",
            "confidence",
            "suppliers",
            "suppliers_excluded",
            "final_report_md",
            "report_output_path",
            "agent6_mode",
            "bom_fallback_used",
            "a_share_candidates",
            "rag_contexts",
        ):
            if key in result and result[key] is not None:
                setattr(state, key, result[key])
        normalize_state_models(state)

        if step == 5 and state.final_report_md and state.status != "failed":
            state.status = "completed"
            from datetime import datetime, timezone

            state.completed_at = datetime.now(timezone.utc).isoformat()

    def _apply_gates(self, state: PipelineState, step: int, result: dict[str, Any]) -> None:
        hints: ApprovalHints | None = None
        if step == 1:
            hints = gate_outlook(state)
        elif step == 3 and state.checklist_gate:
            hints = gate_checklist(state, state.checklist_gate)

        extra_flags = {}
        if result.get("approval_hints"):
            ah = result["approval_hints"]
            if isinstance(ah, dict):
                extra_flags = ah
            else:
                extra_flags = ah.model_dump() if hasattr(ah, "model_dump") else {}
        if result.get("suggest_deepen_bom"):
            extra_flags["suggest_deepen_bom"] = True

        base = hints or ApprovalHints()
        if extra_flags:
            merged = base.model_dump()
            merged.update({k: v for k, v in extra_flags.items() if v is not None})
            state.approval_hints = ApprovalHints.model_validate(merged)
        else:
            state.approval_hints = base

        if result.get("errors"):
            for e in result["errors"]:
                if e not in state.errors:
                    state.errors.append(e)

    async def resolve_step(
        self,
        run_id: str,
        step: int,
        action: str,
        news_id: str | None = None,
    ) -> PipelineState:
        validate_step(step)
        state = self.run_manager.load_state(run_id)

        if state.status == "running":
            if state.pending_approval_step is None:
                raise StepNotAwaitingError(f"run {run_id} 正在执行，请稍候")
            if state.pending_approval_step != step:
                raise DuplicateResolveError(
                    f"run {run_id} 正在执行 step{state.pending_approval_step}，拒绝 step{step} resolve"
                )
        elif state.status == "awaiting_step_approval":
            if state.pending_approval_step is not None and state.pending_approval_step != step:
                raise ValueError(f"当前待确认 step={state.pending_approval_step}，与请求 step={step} 不一致")
            state.status = "running"
            self.run_manager.save_state(state)
        else:
            raise StepNotAwaitingError(f"run {run_id} 状态为 {state.status}，非 awaiting_step_approval")

        self._emit(run_id, "step_resolved", step=step, action=action)

        if action == "proceed":
            hints = state.approval_hints
            block = False
            if hints is not None:
                block = hints.block_proceed if hasattr(hints, "block_proceed") else bool(hints.get("block_proceed"))
            if block:
                raise ValueError("block_proceed=true，禁止 proceed")

            if step == 0:
                if not news_id:
                    raise ValueError("step0 proceed 必须提供 news_id")
                selected = None
                for item in state.news_items:
                    iid = item.id if isinstance(item, NewsItem) else item.get("id")
                    if iid == news_id:
                        selected = item
                        break
                if selected is None:
                    raise ValueError(f"news_id 不存在: {news_id}")
                state.selected_news_id = news_id
                if isinstance(selected, NewsItem):
                    state.selected_news_item = selected
                elif isinstance(selected, dict):
                    state.selected_news_item = _normalize_news(selected)
                else:
                    state.selected_news_item = NewsItem.model_validate(selected)
                state.phase = "research"
                state.pending_approval_step = None
                self.run_manager.save_state(state)
                return await self.run_single_step(run_id, step=1)

            state.pending_approval_step = None
            self.run_manager.save_state(state)
            next_step = step + 1
            if next_step > 5:
                state.status = "completed"
                self.run_manager.save_state(state)
                self._emit(
                    run_id,
                    "run_complete",
                    report_output_path=state.report_output_path,
                    confidence=as_json(state.confidence),
                )
                return state
            return await self.run_single_step(run_id, step=next_step)

        if action == "rerun":
            apply_field_clear(state, step=step, action="rerun")
            state.pending_approval_step = None
            deepen = step == 2 and self._should_deepen_on_rerun(state)
            if deepen:
                state.bom_deepen_count += 1
                self.run_manager.save_state(state)
                self._emit(
                    run_id,
                    "agent_progress",
                    agent=2,
                    message=f"瓶颈不足，自动加深 BOM（第 {state.bom_deepen_count} 次）…",
                    kind="progress",
                )
                await self._run_agent_internal(run_id, step=1)
            else:
                self.run_manager.save_state(state)
            return await self.run_single_step(run_id, step=step)

        if action == "change_direction":
            if step == 0:
                raise ValueError("step0 不支持 change_direction，请重选新闻或重跑本步")
            apply_field_clear(state, step=step, action="change_direction")
            self.run_manager.save_state(state)
            if step == 1:
                return state
            return await self.run_single_step(run_id, step=state.pending_approval_step or step - 1)

        raise ValueError(f"未知 action: {action}")
