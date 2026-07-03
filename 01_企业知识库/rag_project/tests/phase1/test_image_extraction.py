"""
阶段一：页图导出测试（tests/phase1/test_image_extraction.py）

主要功能：
- 测试页图文件名规则 page_{nnn}.png、相对路径构建
- 测试 resolve_image_paths_for_chunk 在页图存在/不存在时的行为
- 测试 PageImageExporter 从 PDF 导出 PNG（mock）

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase1/test_image_extraction.py -v
"""
from __future__ import annotations

import pytest

from src.image_extraction import (
    PageImageExporter,
    build_page_image_relative_path,
    page_image_filename,
    resolve_image_paths_for_chunk,
)


@pytest.mark.phase1
class TestPageImageNaming:
    def test_page_image_filename(self):
        assert page_image_filename(5) == "page_005.png"
        assert page_image_filename(12) == "page_012.png"

    def test_build_page_image_relative_path(self):
        rel = build_page_image_relative_path("abc123", 5)
        assert rel == "debug_data/04_page_images/abc123/page_005.png"


@pytest.mark.phase1
class TestResolveImagePaths:
    def test_resolve_when_image_exists(self, tmp_data_root):
        sha1 = "abc123"
        img_dir = tmp_data_root / "debug_data/04_page_images/abc123"
        img_dir.mkdir(parents=True)
        img_file = img_dir / "page_005.png"
        img_file.write_bytes(b"\x89PNG\r\n")

        paths = resolve_image_paths_for_chunk(
            data_root=tmp_data_root,
            sha1=sha1,
            page=5,
        )
        assert paths == ["debug_data/04_page_images/abc123/page_005.png"]

    def test_resolve_when_image_missing(self, tmp_data_root):
        paths = resolve_image_paths_for_chunk(
            data_root=tmp_data_root,
            sha1="abc123",
            page=99,
        )
        assert paths == []


@pytest.mark.phase1
class TestExportPageImages:
    def test_export_creates_png_per_page(self, tmp_data_root, mocker):
        sha1 = "abc123"
        pages = [{"page": 1, "text": "a"}, {"page": 2, "text": "b"}]
        mock_render = mocker.patch.object(PageImageExporter, "_render_page_to_png")

        exporter = PageImageExporter(tmp_data_root)
        result = exporter.export_from_merged_report(sha1=sha1, pages=pages)

        assert len(result) == 2
        assert mock_render.call_count == 2
        for page_num in (1, 2):
            rel = build_page_image_relative_path(sha1, page_num)
            assert (tmp_data_root / rel).parent.exists()
