# -*- coding: utf-8 -*-
"""step_output 序列化测试。"""

from __future__ import annotations

from manus.api.step_output import as_json, as_json_list, build_step_output
from manus.pipeline.state import create_initial_state


def test_as_json_accepts_dict():
    assert as_json({"id": "n1"}) == {"id": "n1"}


def test_build_step_output_with_dict_news_items():
    state = create_initial_state(run_id="r1", run_date="2026-07-07")
    state.news_items = [{"id": "news-1", "title": "t", "summary": "s"}]
    out = build_step_output(state, 0)
    assert out["news_items"][0]["id"] == "news-1"
