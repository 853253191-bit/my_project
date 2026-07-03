"""
阶段一：文本分块测试（tests/phase1/test_text_splitter.py）

主要功能：
- 测试 merged report 按页分块、chunk schema 校验
- 测试空页跳过、image_paths 关联
- 测试 validate_chunked_report 结构检查

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase1/test_text_splitter.py -v
"""
from __future__ import annotations

import pytest

from src.text_splitter import (
    attach_image_paths_to_chunks,
    split_merged_report_to_chunks,
    validate_chunked_report,
)


@pytest.mark.phase1
class TestSplitMergedReport:
    def test_split_produces_chunks_with_required_fields(
        self, sample_merged_report, tmp_data_root
    ):
        metainfo = sample_merged_report["metainfo"]

        report = split_merged_report_to_chunks(
            merged_report=sample_merged_report,
            metainfo=metainfo,
            data_root=tmp_data_root,
            chunk_size=400,
            chunk_overlap=50,
        )

        assert "metainfo" in report
        assert "content" in report
        chunks = report["content"]["chunks"]
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "chunk_index" in chunk
            assert "page" in chunk
            assert "text" in chunk
            assert "image_paths" in chunk
            assert isinstance(chunk["image_paths"], list)

    def test_empty_text_pages_are_skipped(self, tmp_data_root):
        merged = {
            "metainfo": {"sha1": "x", "doc_id": "2021-KS-0017"},
            "content": {
                "pages": [
                    {"page": 1, "text": "   "},
                    {"page": 2, "text": "有效内容"},
                ]
            },
        }
        report = split_merged_report_to_chunks(
            merged_report=merged,
            metainfo=merged["metainfo"],
            data_root=tmp_data_root,
        )
        texts = [c["text"] for c in report["content"]["chunks"]]
        assert all(t.strip() for t in texts)


@pytest.mark.phase1
class TestAttachImagePaths:
    def test_attach_image_paths(self, tmp_data_root):
        sha1 = "abc123"
        img_dir = tmp_data_root / f"debug_data/04_page_images/{sha1}"
        img_dir.mkdir(parents=True)
        (img_dir / "page_005.png").write_bytes(b"png")

        chunks = [{"chunk_index": 0, "page": 5, "text": "hello"}]
        updated = attach_image_paths_to_chunks(chunks, data_root=tmp_data_root, sha1=sha1)

        assert updated[0]["image_paths"] == [
            f"debug_data/04_page_images/{sha1}/page_005.png"
        ]


@pytest.mark.phase1
class TestValidateChunkedReport:
    def test_valid_sample_chunked_report(self, sample_chunked_report):
        ok, errors = validate_chunked_report(sample_chunked_report)
        assert ok, errors

    def test_missing_image_paths_field_fails(self, sample_chunked_report):
        broken = sample_chunked_report.copy()
        broken["content"]["chunks"][0].pop("image_paths")
        ok, errors = validate_chunked_report(broken)
        assert not ok
        assert any("image_paths" in e for e in errors)
