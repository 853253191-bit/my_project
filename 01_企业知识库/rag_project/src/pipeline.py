"""
预处理与问答流水线编排（src/pipeline.py）

主要功能：
- 统一管理 data/项目知识库 下各阶段路径（解析、merge、分块、向量库等）
- 串联离线建库：下载模型 → 解析 PDF → 预处理 → FAISS 建库 → 校验
- 提供单问/批量问答入口，供 main.py 与 app_streamlit.py 调用

如何调用：
  from pathlib import Path
  from src.pipeline import Pipeline
  from src.config import enterprise_config

  pipeline = Pipeline(Path("data/项目知识库"), run_config=enterprise_config())
  pipeline.build_offline_knowledge_base(skip_download=True)  # 一键建库
  answer = pipeline.answer_single_question("你的问题")          # 单问
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.config import EnterpriseRunConfig, enterprise_config


@dataclass
class PipelineConfig:
    root_path: Path
    config_suffix: str = ""

    @property
    def subset_path(self) -> Path:
        return self.root_path / "subset.csv"

    @property
    def questions_file_path(self) -> Path:
        return self.root_path / "questions.json"

    @property
    def answers_file_path(self) -> Path:
        return self.root_path / f"answers{self.config_suffix}.json"

    @property
    def pdf_reports_dir(self) -> Path:
        return self.root_path / "pdf_reports"

    @property
    def parsed_reports_path(self) -> Path:
        return self.root_path / "debug_data/01_parsed_reports"

    @property
    def parsed_reports_debug_path(self) -> Path:
        return self.root_path / "debug_data/01_parsed_reports_debug"

    @property
    def merged_reports_path(self) -> Path:
        return self.root_path / "debug_data/02_merged_reports"

    @property
    def reports_markdown_path(self) -> Path:
        return self.root_path / "debug_data/03_reports_markdown"

    @property
    def page_images_path(self) -> Path:
        return self.root_path / "debug_data/04_page_images"

    @property
    def documents_dir(self) -> Path:
        return self.root_path / "databases/chunked_reports"

    @property
    def vector_db_dir(self) -> Path:
        return self.root_path / "databases/vector_dbs"


class Pipeline:
    def __init__(
        self,
        root_path: Path,
        run_config: Optional[EnterpriseRunConfig] = None,
    ):
        self.run_config = run_config or enterprise_config()
        self.paths = PipelineConfig(
            root_path=root_path,
            config_suffix=self.run_config.config_suffix,
        )
        self._questions_processor = None
        self._convert_json_to_csv_if_needed()

    def _convert_json_to_csv_if_needed(self) -> None:
        json_path = self.paths.root_path / "subset.json"
        csv_path = self.paths.subset_path
        if json_path.exists() and not csv_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            pd.DataFrame(data).to_csv(csv_path, index=False, encoding="utf-8")

    def download_docling_models(self) -> None:
        """用 pdf_reports 中的样例 PDF 触发 Docling 模型下载。"""
        from src.pdf_parsing import PDFParser

        logging.basicConfig(level=logging.INFO)
        pdf_paths = sorted(self.paths.pdf_reports_dir.glob("*.pdf"))
        if not pdf_paths:
            raise FileNotFoundError(
                f"未找到 PDF 文件，请先运行 scripts/generate_subset.py："
                f"{self.paths.pdf_reports_dir}"
            )
        sample_pdf = pdf_paths[0]
        logging.info(f"使用样例 PDF 触发模型下载：{sample_pdf.name}")
        self.paths.parsed_reports_path.mkdir(parents=True, exist_ok=True)
        parser = PDFParser(output_dir=self.paths.parsed_reports_path)
        parser.parse_and_export(input_doc_paths=[sample_pdf])

    def parse_pdf_reports(
        self,
        parallel: bool = True,
        chunk_size: int = 2,
        max_workers: int = 1,
    ) -> None:
        from src.pdf_parsing import PDFParser

        self.paths.parsed_reports_path.mkdir(parents=True, exist_ok=True)
        self.paths.parsed_reports_debug_path.mkdir(parents=True, exist_ok=True)
        pdf_parser = PDFParser(
            output_dir=self.paths.parsed_reports_path,
            csv_metadata_path=self.paths.subset_path,
        )
        pdf_parser.debug_data_path = self.paths.parsed_reports_debug_path
        input_doc_paths = list(self.paths.pdf_reports_dir.glob("*.pdf"))
        if parallel:
            pdf_parser.parse_and_export_parallel(
                input_doc_paths=input_doc_paths,
                optimal_workers=max_workers,
                chunk_size=chunk_size,
            )
        else:
            pdf_parser.parse_and_export(input_doc_paths=input_doc_paths)

    def merge_reports(self) -> None:
        from src.parsed_reports_merging import PageTextPreparation

        prep = PageTextPreparation(
            use_serialized_tables=self.run_config.use_serialized_tables,
        )
        self.paths.merged_reports_path.mkdir(parents=True, exist_ok=True)
        prep.process_reports(
            reports_dir=self.paths.parsed_reports_path,
            output_dir=self.paths.merged_reports_path,
        )

    def export_reports_to_markdown(self) -> None:
        from src.parsed_reports_merging import PageTextPreparation

        prep = PageTextPreparation(
            use_serialized_tables=self.run_config.use_serialized_tables,
        )
        self.paths.reports_markdown_path.mkdir(parents=True, exist_ok=True)
        prep.export_to_markdown(
            self.paths.merged_reports_path,
            self.paths.reports_markdown_path,
        )

    def export_page_images(self) -> None:
        import csv

        from src.image_extraction import PageImageExporter

        exporter = PageImageExporter(self.paths.root_path)
        with self.paths.subset_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pdf_path = self.paths.pdf_reports_dir / row["file_name"]
                if pdf_path.exists():
                    exporter.export_from_pdf(pdf_path, row["sha1"])

    def chunk_reports(self) -> None:
        from src.text_splitter import TextSplitter

        splitter = TextSplitter()
        splitter.chunk_all_reports(
            merged_dir=self.paths.merged_reports_path,
            output_dir=self.paths.documents_dir,
            data_root=self.paths.root_path,
        )

    def create_vector_dbs(self) -> None:
        from src.ingestion import VectorDBIngestor

        ingestor = VectorDBIngestor(data_root=self.paths.root_path)
        ingestor.process_all_reports()

    def preprocess_reports(self) -> None:
        """阶段一预处理：合并、导出、分块，不含建库。"""
        self.merge_reports()
        self.export_reports_to_markdown()
        self.export_page_images()
        self.chunk_reports()

    def process_parsed_reports(self) -> None:
        """分块 + 建向量库。"""
        self.preprocess_reports()
        self.create_vector_dbs()

    def build_index(self) -> None:
        """仅建向量库（需已有 chunked_reports）。"""
        self.create_vector_dbs()

    def build_offline_knowledge_base(
        self,
        *,
        skip_download: bool = False,
        parallel: bool = True,
        chunk_size: int = 2,
        max_workers: int = 1,
    ) -> None:
        """一键离线建库：下载模型 → 解析 PDF → 预处理建库 → 校验索引。"""
        from src.index_verifier import verify_indexes

        if not skip_download:
            logging.info("[1/4] 下载 Docling 模型...")
            self.download_docling_models()
        else:
            logging.info("[1/4] 跳过 Docling 模型下载")

        logging.info("[2/4] 解析 PDF...")
        self.parse_pdf_reports(
            parallel=parallel,
            chunk_size=chunk_size,
            max_workers=max_workers,
        )

        logging.info("[3/4] 预处理并建向量库...")
        self.process_parsed_reports()

        logging.info("[4/4] 校验索引...")
        report = verify_indexes(self.paths.root_path)
        if not report.all_passed:
            lines = [
                f"  {item.doc_id}: {', '.join(item.errors)}"
                for item in report.items
                if not item.passed
            ]
            raise RuntimeError(
                f"索引校验失败 ({report.passed}/{report.total}):\n"
                + "\n".join(lines)
            )

        indexed, total = self.count_indexed_documents()
        logging.info(f"离线建库完成：{indexed}/{total} 份文档已索引")

    def resume_offline_knowledge_base(self) -> None:
        """从 merge 完成后续跑：Markdown → 页图 → 分块 → 建库 → 校验。"""
        from src.index_verifier import verify_indexes

        logging.info("[续跑 1/4] 导出 Markdown...")
        self.export_reports_to_markdown()
        logging.info("[续跑 2/4] 导出页图...")
        self.export_page_images()
        logging.info("[续跑 3/4] 分块...")
        self.chunk_reports()
        logging.info("[续跑 4/4] 建向量库...")
        self.create_vector_dbs()
        logging.info("[续跑] 校验索引...")
        report = verify_indexes(self.paths.root_path)
        if not report.all_passed:
            lines = [
                f"  {item.doc_id}: {', '.join(item.errors)}"
                for item in report.items
                if not item.passed
            ]
            raise RuntimeError(
                f"索引校验失败 ({report.passed}/{report.total}):\n"
                + "\n".join(lines)
            )

    def _get_next_available_filename(self, base_path: Path) -> Path:
        if not base_path.exists():
            return base_path
        stem = base_path.stem
        suffix = base_path.suffix
        parent = base_path.parent
        counter = 1
        while True:
            new_path = parent / f"{stem}_{counter:02d}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1

    def _get_questions_processor(self):
        if self._questions_processor is None:
            from src.questions_processing import QuestionsProcessor

            self._questions_processor = QuestionsProcessor(
                data_root=self.paths.root_path,
                run_config=self.run_config,
                questions_file_path=self.paths.questions_file_path,
            )
        return self._questions_processor

    def process_questions(self) -> Path:
        processor = self._get_questions_processor()
        output_path = self._get_next_available_filename(self.paths.answers_file_path)
        processor.process_all_questions(output_path)
        return output_path

    def answer_single_question(self, question: str) -> dict[str, Any]:
        return self._get_questions_processor().process_single_question(question)

    def count_indexed_documents(self) -> tuple[int, int]:
        """返回 (已索引数, subset 总数)。"""
        import csv

        if not self.paths.subset_path.exists():
            return 0, 0
        with self.paths.subset_path.open(encoding="utf-8") as f:
            total = sum(1 for _ in csv.DictReader(f))
        indexed = len(list(self.paths.vector_db_dir.glob("*.faiss")))
        return indexed, total


# CLI 配置预设
preprocess_configs = {
    "no_ser_tab": enterprise_config(),
}

configs = {
    "enterprise": enterprise_config(),
}
