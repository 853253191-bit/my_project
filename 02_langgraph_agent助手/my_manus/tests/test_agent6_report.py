# -*- coding: utf-8 -*-
"""Agent6 报告生成测试（SPEC §4.6 / §8.2，P3）。"""

from __future__ import annotations

from pathlib import Path

from manus.pipeline.state import PipelineState
from manus.steps.agent6_report import REPORT_SECTIONS, render_report_template, write_report_files


class TestReportSections:
    def test_ten_sections_defined(self):
        assert len(REPORT_SECTIONS) >= 10
        titles = " ".join(REPORT_SECTIONS)
        assert "检查清单" in titles or "Checklist" in titles.lower()
        assert "Red" in titles or "red" in titles or "证伪" in titles


class TestRenderReportTemplate:
    def test_regenerate_mode_no_llm(self, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        md = render_report_template(state)
        assert "# " in md or "## " in md
        for section in REPORT_SECTIONS[:3]:
            assert section.split()[0] in md or section in md

    def test_contains_disclaimer(self, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        md = render_report_template(state)
        assert "不构成投资建议" in md or "研究辅助" in md


class TestWriteReportFiles:
    def test_writes_to_output_and_runs(self, filled_pipeline_state_dict, tmp_path: Path):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        state.final_report_md = "# 测试报告\n\n内容"
        reports_dir = tmp_path / "reports"
        runs_dir = tmp_path / "runs" / state.run_id
        runs_dir.mkdir(parents=True)
        path = write_report_files(
            state,
            reports_dir=reports_dir,
            runs_dir=runs_dir,
            filename_max_slug=40,
        )
        assert path is not None
        assert path.exists()
        assert (runs_dir / "report.md").exists()
