# -*- coding: utf-8 -*-
"""配置加载测试（SPEC §7.1 / §7.2）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from manus.config import ConfigError, load_config


class TestLoadConfig:
    def test_load_from_dict(self, minimal_config_dict):
        cfg = load_config(config_dict=minimal_config_dict)
        assert cfg.workflow.step_approval_required is True
        assert cfg.supplier_screen.market == "CN"
        assert cfg.supplier_screen.min_listing_days == 60

    def test_missing_config_file_raises(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="config"):
            load_config(config_path=tmp_path / "missing.toml")

    def test_env_fallback_for_api_key(self, minimal_config_dict, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key-123")
        minimal_config_dict["llm"]["api_key"] = ""
        cfg = load_config(config_dict=minimal_config_dict)
        assert cfg.llm.api_key == "env-key-123"
