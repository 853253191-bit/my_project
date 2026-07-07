# -*- coding: utf-8 -*-
"""Agent6：研究报告生成与落盘（SPEC §4.6 / §8.2）。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from manus.api.step_output import as_json, as_json_list
from manus.llm import invoke_llm_json
from manus.pipeline.progress import emit_progress
from manus.pipeline.state import PipelineState

REPORT_SECTIONS = [
    "1. 执行摘要",
    "2. 终端需求与 outlook",
    "3. 产业链拆解",
    "4. 瓶颈与供需错配",
    "5. 断供测试与定量验证",
    "6. 检查清单（Checklist）",
    "7. Red-team 证伪与风险",
    "8. A 股主板供应商候选",
    "9. 节奏与仓位提示",
    "10. 附录与免责声明",
]


def _field(obj: Any, name: str, default: str = "") -> str:
    if obj is None:
        return default
    if isinstance(obj, dict):
        val = obj.get(name, default)
    else:
        val = getattr(obj, name, default)
    return str(val) if val is not None else default


def build_report_context(state: PipelineState) -> dict[str, Any]:
    """压缩 pipeline state 供 LLM 生成报告，避免超长原始 JSON。"""
    news = state.selected_news_item
    node = state.component_node
    return {
        "run_date": state.run_date,
        "news_title": _field(news, "title"),
        "news_summary": _field(news, "summary"),
        "gate_outlook": state.gate_outlook_result,
        "confidence": state.confidence,
        "component_node": as_json(node),
        "bottlenecks": as_json_list(state.bottlenecks),
        "ripple_notes": state.ripple_notes,
        "validations": as_json_list(state.validations),
        "red_team": as_json(state.red_team),
        "checklist_gate": as_json(state.checklist_gate),
        "suppliers": as_json_list(state.suppliers),
        "suppliers_excluded": as_json_list(state.suppliers_excluded),
        "step_output_summary": state.step_output_summary,
        "errors": state.errors,
    }


def _section_executive_summary(state: PipelineState) -> list[str]:
    lines: list[str] = []
    news = _field(state.selected_news_item, "title", "未选择研究方向")
    lines.append(f"- **研究方向**：{news}")
    lines.append(f"- **置信度**：{state.confidence}")
    if state.bottlenecks:
        names = [_field(b, "bottleneck_name") for b in state.bottlenecks[:5]]
        lines.append(f"- **核心瓶颈（{len(state.bottlenecks)} 个）**：{', '.join(names)}")
    else:
        lines.append("- **核心瓶颈**：本轮未识别到足够瓶颈，结论偏初步")
    if state.suppliers:
        lines.append(f"- **A 股主板候选**：{len(state.suppliers)} 家")
    else:
        lines.append("- **A 股主板候选**：暂无合格标的")
    if state.step_output_summary:
        lines.append(f"- **流程摘要**：{state.step_output_summary}")
    return lines


def _section_outlook(state: PipelineState) -> list[str]:
    lines: list[str] = []
    outlook = state.gate_outlook_result or "unknown"
    lines.append(f"- **outlook 门控结果**：{outlook}")
    if state.component_node:
        td = state.component_node.terminal_demand
        lines.append(f"- **终端需求**：{_field(td, 'description')}")
        lines.append(f"- **2～3 年 outlook**：{_field(td, 'outlook_2_3y')}")
        lines.append(f"- **依据**：{_field(td, 'backing')}")
    else:
        lines.append("- 暂无产业链拆解数据")
    return lines


def _section_bom(state: PipelineState) -> list[str]:
    lines: list[str] = []
    if not state.component_node:
        lines.append("（暂无拆解数据）")
        return lines
    node = state.component_node
    lines.append(f"- **拆解深度**：{node.decomposition_depth}")
    for comp in node.components:
        lines.append(
            f"- **{_field(comp, 'name')}**（{_field(comp, 'category')}，价值量 {_field(comp, 'value_share')}）"
            f"：{_field(comp, 'growth_driver')}；上游 {_field(comp, 'upstream_hints')}"
        )
    for br in node.horizontal_branches:
        lines.append(f"- 横向分支 [{_field(br, 'type')}] {_field(br, 'node')}：{_field(br, 'rationale')}")
    return lines


def _section_bottlenecks(state: PipelineState) -> list[str]:
    lines: list[str] = []
    if not state.bottlenecks:
        lines.append("（本轮未识别瓶颈，建议回到 step2 重跑或加深 BOM）")
        return lines
    for bn in state.bottlenecks:
        traits = bn.traits if hasattr(bn, "traits") else bn.get("traits", {})
        lines.append(
            f"- **{_field(bn, 'bottleneck_name')}**（{_field(bn, 'component')} / {_field(bn, 'layer')}）"
        )
        lines.append(f"  - 错配假设：{_field(bn, 'mismatch_hypothesis')}")
        lines.append(f"  - 四特征：{as_json(traits)}")
        ev = bn.evidence if hasattr(bn, "evidence") else bn.get("evidence", [])
        if ev:
            lines.append(f"  - 证据：{'; '.join(str(x) for x in ev[:3])}")
    if state.ripple_notes:
        lines.append(f"- **连带影响（ripple）**：{state.ripple_notes}")
    return lines


def _section_validations(state: PipelineState) -> list[str]:
    lines: list[str] = []
    if not state.validations:
        lines.append("（暂无定量验证结果）")
        return lines
    for v in state.validations:
        st = v.supply_test if hasattr(v, "supply_test") else v.get("supply_test", {})
        lines.append(
            f"- **瓶颈 {_field(v, 'bottleneck_id')}**：不可替代性 {_field(v, 'irreplaceability_score')}/5"
        )
        lines.append(
            f"  - 断供测试：改架构 {_field(st, 'architecture_change_required')}，"
            f"切换 {_field(st, 'switching_time_months')} 月，切换成本 {_field(st, 'switching_cost')}"
        )
        if _field(v, "gap_ratio"):
            lines.append(
                f"  - 供需缺口比 {_field(v, 'gap_ratio')}，持续 {_field(v, 'duration_quarters')} 季度"
            )
        if _field(v, "price_elasticity"):
            lines.append(f"  - 价格弹性：{_field(v, 'price_elasticity')}")
    return lines


def _section_checklist(state: PipelineState) -> list[str]:
    if not state.checklist_gate:
        return ["（暂无检查清单结果）"]
    gate = state.checklist_gate
    lines = [f"- **总结果**：{gate.result}"]
    for item in gate.hard_items:
        mark = "通过" if item.passed else "未通过"
        lines.append(f"- 硬项 {item.id}：{mark}（{item.note or '-'}）")
    for item in gate.soft_items:
        mark = "通过" if item.passed else "未通过"
        lines.append(f"- 软项 {item.item}：{mark}")
    return lines


def _section_red_team(state: PipelineState) -> list[str]:
    if not state.red_team:
        return ["（暂无 red-team 报告）"]
    rt = state.red_team
    lines = [f"- **供给响应风险**：{rt.supply_response_risk}"]
    lines.append("- **替代路线**：")
    for route in rt.alternative_routes:
        lines.append(f"  - {route}")
    lines.append("- **证伪所需数据**：")
    for item in rt.falsification_data_needed:
        lines.append(f"  - {item}")
    if rt.needs_human_review:
        lines.append("- **需人工复核**：是")
    return lines


def _section_suppliers(state: PipelineState) -> list[str]:
    lines: list[str] = []
    if state.suppliers:
        for s in state.suppliers:
            lines.append(
                f"- **{_field(s, 'company_name')}**（{_field(s, 'ticker')}）"
                f" 覆盖度 {_field(s, 'coverage_level')}，业务占比 {_field(s, 'business_focus_pct')}%"
            )
            risks = s.risks if hasattr(s, "risks") else s.get("risks", [])
            if risks:
                lines.append(f"  - 风险：{'; '.join(str(r) for r in risks[:2])}")
    else:
        lines.append("本瓶颈无合格 A 股主板标的")
    if state.suppliers_excluded:
        lines.append("- **排除标的**：")
        for ex in state.suppliers_excluded:
            lines.append(f"  - {_field(ex, 'ticker')}：{_field(ex, 'reason')}")
    return lines


def _section_timing(state: PipelineState) -> list[str]:
    lines: list[str] = []
    conf = state.confidence
    if conf == "high":
        lines.append("- 置信度较高，可按研究节奏分批验证，关注催化剂与财报节点。")
    elif conf == "low":
        lines.append("- 置信度偏低，建议小仓位试探或等待更多验证数据。")
    else:
        lines.append("- 置信度中等，建议结合门控结果与 red-team 风险动态调整。")
    hints = state.approval_hints
    if hints and hints.messages:
        for msg in hints.messages:
            lines.append(f"- 提示：{msg}")
    return lines


def _section_appendix(state: PipelineState) -> list[str]:
    lines = [
        "- 本报告由 Manus 产业链投研 Agent 自动生成，整合 Agent1～5 的结构化输出。",
        f"- run_id：`{state.run_id}`，生成日期：{state.run_date}。",
    ]
    if state.errors:
        lines.append("- **运行告警/降级记录**：")
        for err in state.errors[-5:]:
            lines.append(f"  - {err}")
    lines.append("- 本输出为研究辅助，不构成投资建议。")
    return lines


_SECTION_RENDERERS = {
    "1. 执行摘要": _section_executive_summary,
    "2. 终端需求与 outlook": _section_outlook,
    "3. 产业链拆解": _section_bom,
    "4. 瓶颈与供需错配": _section_bottlenecks,
    "5. 断供测试与定量验证": _section_validations,
    "6. 检查清单（Checklist）": _section_checklist,
    "7. Red-team 证伪与风险": _section_red_team,
    "8. A 股主板供应商候选": _section_suppliers,
    "9. 节奏与仓位提示": _section_timing,
    "10. 附录与免责声明": _section_appendix,
}


def render_report_template(state: PipelineState) -> str:
    """基于 pipeline 全量 state 渲染十章节报告（LLM 失败时的结构化兜底）。"""
    lines = [f"# 产业链投研报告 — {state.run_date}", ""]
    news = _field(state.selected_news_item, "title", "未选择")
    lines.append(f"**研究方向**: {news}")
    lines.append(f"**置信度**: {state.confidence}")
    lines.append("")

    for section in REPORT_SECTIONS:
        lines.append(f"## {section}")
        renderer = _SECTION_RENDERERS.get(section)
        if renderer:
            lines.extend(renderer(state))
        else:
            lines.append("（暂无数据）")
        lines.append("")

    return "\n".join(lines)


def _slug(text: str, max_len: int) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text).strip("-")
    return s[:max_len] if s else "report"


def write_report_files(
    state: PipelineState,
    reports_dir: Path | str,
    runs_dir: Path | str,
    filename_max_slug: int = 40,
) -> Path | None:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    runs_path = Path(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)

    title = state.selected_news_item.title if state.selected_news_item else state.run_id
    slug = _slug(title, filename_max_slug)
    filename = f"{state.run_date}_{state.run_id}_{slug}.md"
    main_path = reports_path / filename
    main_path.write_text(state.final_report_md, encoding="utf-8")

    run_report = runs_path / "report.md"
    run_report.write_text(state.final_report_md, encoding="utf-8")
    return main_path


async def run_agent6(state: dict[str, Any], config: dict[str, Any] | Any) -> dict[str, Any]:
    ps = PipelineState.model_validate(state)
    output_cfg = config.get("output", {}) if isinstance(config, dict) else {}
    context = build_report_context(ps)
    md = ""

    try:
        emit_progress("调用大模型生成研究报告…")
        payload = json.dumps(context, ensure_ascii=False, indent=2)
        data = await invoke_llm_json(
            config,
            [
                {
                    "role": "system",
                    "content": (
                        "你是产业链投研报告编辑。根据输入 JSON 生成完整 Markdown 报告，"
                        "必须包含十个章节（执行摘要、终端需求、产业链拆解、瓶颈、断供验证、"
                        "Checklist、Red-team、A股供应商、节奏提示、附录）。"
                        "输出 JSON：{\"final_report_md\": \"...\"}，不得留空章节。"
                    ),
                },
                {"role": "user", "content": f"请基于以下研究数据生成报告：\n{payload}"},
            ],
        )
        md = (data.get("final_report_md") or "").strip()
    except Exception as exc:
        emit_progress(f"大模型报告生成失败，改用结构化模板：{exc}", kind="progress")

    if not md or "待补充" in md:
        emit_progress("使用结构化模板渲染报告（含 Agent1～5 全量结果）…")
        md = render_report_template(ps)
        ps.agent6_mode = "regenerate"
    else:
        ps.agent6_mode = "generate"

    ps.final_report_md = md

    from manus.config import PROJECT_ROOT

    reports_dir = PROJECT_ROOT / output_cfg.get("reports_dir", "output/reports")
    runs_dir = PROJECT_ROOT / "runs" / ps.run_id
    path = write_report_files(
        ps,
        reports_dir=reports_dir,
        runs_dir=runs_dir,
        filename_max_slug=int(output_cfg.get("filename_max_slug", 40)),
    )

    return {
        "final_report_md": md,
        "report_output_path": str(path) if path else None,
        "agent6_mode": ps.agent6_mode,
        "step_output_summary": "报告生成完成",
    }
