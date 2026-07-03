"""
阶段二：多模态 Embedding 测试（tests/phase2/test_multimodal_embedding.py）

主要功能：
- 测试 build_multimodal_input、to_file_uri（含 Windows 路径）
- 测试 embed_chunk / embed_query（mock DashScope API）
- 测试未设置 DASHSCOPE_API_KEY 时抛出 ValueError

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase2/test_multimodal_embedding.py -v
"""
from __future__ import annotations

import numpy as np
import pytest

from src.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL
from src.multimodal_embedding import (
    build_multimodal_input,
    embed_chunk,
    embed_query,
    require_dashscope_api_key,
    to_file_uri,
)


@pytest.mark.phase2
class TestFileUri:
    def test_to_file_uri_windows_path(self, tmp_path):
        p = tmp_path / "img.png"
        p.write_bytes(b"x")
        uri = to_file_uri(p)
        assert uri.startswith("file:///")
        assert "img.png" in uri


@pytest.mark.phase2
class TestBuildMultimodalInput:
    def test_text_only(self):
        mm_input = build_multimodal_input("hello", [])
        assert mm_input == [{"text": "hello"}]

    def test_text_with_image(self, tmp_path):
        img = tmp_path / "page.png"
        img.write_bytes(b"x")
        mm_input = build_multimodal_input(
            "hello",
            [str(img)],
            data_root=tmp_path.parent,
        )
        assert len(mm_input) == 2
        assert mm_input[0]["text"] == "hello"
        assert mm_input[1]["image"].startswith("file:///")


@pytest.mark.phase2
class TestRequireApiKey:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
            require_dashscope_api_key()

    def test_api_key_present(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        assert require_dashscope_api_key() == "test-key"


@pytest.mark.phase2
class TestEmbedChunk:
    def test_embed_chunk_text_only_calls_multimodal_api(self, mocker, monkeypatch, tmp_path):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        mock_call = mocker.patch("src.multimodal_embedding.dashscope.MultiModalEmbedding.call")
        fake_vec = [0.1] * EMBEDDING_DIMENSION
        mock_call.return_value = {
            "output": {"embeddings": [{"embedding": fake_vec}]}
        }

        vec = embed_chunk("测试文本", [], data_root=tmp_path)

        mock_call.assert_called_once()
        call_kwargs = mock_call.call_args.kwargs
        assert call_kwargs["model"] == EMBEDDING_MODEL
        assert call_kwargs["parameters"]["dimension"] == EMBEDDING_DIMENSION
        assert call_kwargs["input"] == [{"text": "测试文本"}]
        assert len(vec) == EMBEDDING_DIMENSION

    def test_embed_chunk_with_image_includes_image_in_input(
        self, mocker, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        img_rel = "debug_data/04_page_images/x/page_001.png"
        img_path = tmp_path / img_rel
        img_path.parent.mkdir(parents=True)
        img_path.write_bytes(b"png")

        mock_call = mocker.patch("src.multimodal_embedding.dashscope.MultiModalEmbedding.call")
        mock_call.return_value = {
            "output": {"embeddings": [{"embedding": [0.0] * EMBEDDING_DIMENSION}]}
        }

        embed_chunk("文本", [img_rel], data_root=tmp_path)

        mm_input = mock_call.call_args.kwargs["input"]
        assert len(mm_input) == 2
        assert "image" in mm_input[1]


@pytest.mark.phase2
class TestEmbedQuery:
    def test_embed_query_returns_normalized_vector(self, mocker, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        mock_call = mocker.patch("src.multimodal_embedding.dashscope.MultiModalEmbedding.call")
        raw = np.ones(EMBEDDING_DIMENSION, dtype=np.float32)
        mock_call.return_value = {
            "output": {"embeddings": [{"embedding": raw.tolist()}]}
        }

        vec = embed_query("D06单元控规调整")

        assert vec.shape == (1, EMBEDDING_DIMENSION)
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-5
