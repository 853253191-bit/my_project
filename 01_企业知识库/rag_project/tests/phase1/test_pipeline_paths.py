"""
阶段一：Pipeline 路径配置测试（tests/phase1/test_pipeline_paths.py）

主要功能：
- 校验 PipelineConfig 各路径指向 data/项目知识库 下正确子目录
- 确认 preprocess_reports 不调用 create_vector_dbs
- 确认无 stock_data 等旧项目硬编码路径

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase1/test_pipeline_paths.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.pipeline import Pipeline, PipelineConfig


@pytest.mark.phase1
class TestPipelineConfigPaths:
    def test_paths_under_data_root(self, tmp_data_root):
        cfg = PipelineConfig(root_path=tmp_data_root)

        assert cfg.subset_path == tmp_data_root / "subset.csv"
        assert cfg.pdf_reports_dir == tmp_data_root / "pdf_reports"
        assert cfg.parsed_reports_path == tmp_data_root / "debug_data/01_parsed_reports"
        assert cfg.merged_reports_path == tmp_data_root / "debug_data/02_merged_reports"
        assert cfg.reports_markdown_path == tmp_data_root / "debug_data/03_reports_markdown"
        assert cfg.page_images_path == tmp_data_root / "debug_data/04_page_images"
        assert cfg.documents_dir == tmp_data_root / "databases/chunked_reports"
        assert cfg.vector_db_dir == tmp_data_root / "databases/vector_dbs"

    def test_no_stock_data_hardcode(self):
        source = Path(__file__).resolve().parents[2] / "src" / "pipeline.py"
        if source.exists():
            text = source.read_text(encoding="utf-8")
            assert "stock_data" not in text


@pytest.mark.phase1
class TestPreprocessPipeline:
    def test_preprocess_does_not_call_create_vector_dbs(self, tmp_data_root, mocker):
        pipeline = Pipeline(root_path=tmp_data_root)
        mocker.patch.object(pipeline, "merge_reports")
        mocker.patch.object(pipeline, "export_reports_to_markdown")
        mocker.patch.object(pipeline, "export_page_images")
        mocker.patch.object(pipeline, "chunk_reports")
        mock_vdb = mocker.patch.object(pipeline, "create_vector_dbs")

        pipeline.preprocess_reports()

        mock_vdb.assert_not_called()

    def test_preprocess_calls_expected_steps(self, tmp_data_root, mocker):
        pipeline = Pipeline(root_path=tmp_data_root)
        merge = mocker.patch.object(pipeline, "merge_reports")
        md = mocker.patch.object(pipeline, "export_reports_to_markdown")
        imgs = mocker.patch.object(pipeline, "export_page_images")
        chunk = mocker.patch.object(pipeline, "chunk_reports")

        pipeline.preprocess_reports()

        merge.assert_called_once()
        md.assert_called_once()
        imgs.assert_called_once()
        chunk.assert_called_once()
