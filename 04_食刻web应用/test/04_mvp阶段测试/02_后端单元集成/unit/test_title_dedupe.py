# -*- coding: utf-8 -*-
"""标题去重单元测试。"""

from __future__ import annotations

from shike.services.title_dedupe import (
    dedupe_by_fuzzy,
    normalize_title_core,
    title_similarity,
)


def test_normalize_title_core_strips_noise():
    assert "番茄炒蛋" in normalize_title_core("【家常】番茄炒蛋的做法")
    assert normalize_title_core("番茄炒蛋教程")


def test_title_similarity_same_core():
    assert title_similarity("番茄炒蛋", "番茄炒蛋") == 1.0
    assert title_similarity("番茄炒蛋的做法", "番茄炒蛋教程") >= 0.9


def test_dedupe_by_fuzzy_keeps_first():
    items = [
        {"id": "1", "title": "番茄炒蛋"},
        {"id": "2", "title": "番茄炒蛋的做法"},
        {"id": "3", "title": "红烧肉"},
    ]
    kept = dedupe_by_fuzzy(items, keep=5, threshold=0.85)
    titles = [x["title"] for x in kept]
    assert titles[0] == "番茄炒蛋"
    assert "红烧肉" in titles
    assert len(kept) == 2
