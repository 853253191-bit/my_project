"""
页图导出与 chunk 关联（src/image_extraction.py）

主要功能：
- 用 PyMuPDF 将 PDF 各页渲染为 PNG
- 保存至 debug_data/04_page_images/{sha1}/page_{nnn}.png
- 分块时根据页码为 chunk 填充 image_paths，供多模态 Embedding 使用

如何调用：
  from pathlib import Path
  from src.image_extraction import PageImageExporter

  exporter = PageImageExporter(Path("data/项目知识库"))
  exporter.export_from_pdf(Path("pdf_reports/某文档.pdf"), sha1="abc123...")
  # 通常由 Pipeline.export_page_images() 按 subset.csv 批量调用
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz


def page_image_filename(page: int) -> str:
    return f"page_{page:03d}.png"


def build_page_image_relative_path(sha1: str, page: int) -> str:
    return f"debug_data/04_page_images/{sha1}/{page_image_filename(page)}"


def resolve_image_paths_for_chunk(
    data_root: Path,
    sha1: str,
    page: int,
) -> list[str]:
    """若页图存在则返回相对路径列表，否则返回空列表。"""
    rel = build_page_image_relative_path(sha1, page)
    if (data_root / rel).exists():
        return [rel]
    return []


class PageImageExporter:
    """从 PDF 或 merged report 导出页级 PNG。"""

    def __init__(self, data_root: Path):
        self.data_root = data_root

    def export_from_merged_report(
        self,
        sha1: str,
        pages: list[dict[str, Any]],
        pdf_path: Path | None = None,
    ) -> list[str]:
        if pdf_path and pdf_path.exists():
            return self.export_from_pdf(pdf_path, sha1, [p["page"] for p in pages])
        exported: list[str] = []
        for page_info in pages:
            page_num = page_info["page"]
            rel = build_page_image_relative_path(sha1, page_num)
            out_path = self.data_root / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            self._render_page_to_png(page_info, out_path)
            exported.append(rel)
        return exported

    def export_from_pdf(
        self,
        pdf_path: Path,
        sha1: str,
        page_numbers: list[int] | None = None,
        dpi: int = 150,
    ) -> list[str]:
        """使用 PyMuPDF 将 PDF 指定页渲染为 PNG。"""
        exported: list[str] = []
        doc = fitz.open(pdf_path)
        try:
            targets = page_numbers or list(range(1, doc.page_count + 1))
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            for page_num in targets:
                if page_num < 1 or page_num > doc.page_count:
                    continue
                rel = build_page_image_relative_path(sha1, page_num)
                out_path = self.data_root / rel
                out_path.parent.mkdir(parents=True, exist_ok=True)
                page = doc.load_page(page_num - 1)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                pix.save(str(out_path))
                exported.append(rel)
        finally:
            doc.close()
        return exported

    def export_all_from_subset(self, subset_path: Path, pdf_dir: Path) -> int:
        """根据 subset.csv 批量导出全部 PDF 页图。"""
        import csv

        count = 0
        with subset_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pdf_path = pdf_dir / row["file_name"]
                if not pdf_path.exists():
                    continue
                self.export_from_pdf(pdf_path, row["sha1"])
                count += 1
        return count

    def _render_page_to_png(self, page_info: dict[str, Any], out_path: Path) -> None:
        """占位渲染（测试用）。"""
        out_path.write_bytes(b"\x89PNG\r\n\x1a\n")
