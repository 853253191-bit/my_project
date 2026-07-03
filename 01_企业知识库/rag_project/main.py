"""
企业知识库 RAG 命令行入口（main.py）

主要功能：
- 提供离线建库、预处理、向量索引校验、批量问答等 Click CLI 子命令
- 工作目录须为 data/项目知识库（命令内使用 Path.cwd() 作为数据根目录）

如何调用（在 data/项目知识库 目录下执行）：
  cd data/项目知识库
  python ../../main.py build-all --skip-download    # 一键建库（跳过模型下载）
  python ../../main.py download-models              # 首次下载 Docling 模型
  python ../../main.py parse-pdfs                   # 仅解析 PDF
  python ../../main.py process-reports              # 预处理 + 建向量库
  python ../../main.py build-index                  # 仅从 chunked 建 FAISS
  python ../../main.py resume-build                 # 从 merge 之后断点续跑
  python ../../main.py resume-build --from-step index  # 仅建库 + 校验
  python ../../main.py verify-index                 # 校验索引完整性
  python ../../main.py process-questions            # 批量处理 questions.json
  python ../../main.py --help                       # 查看全部子命令
"""
from __future__ import annotations

from pathlib import Path

import click

from src.index_verifier import verify_indexes
from src.pipeline import Pipeline, configs, preprocess_configs


@click.group()
def cli():
    """企业知识库 RAG 流水线 CLI。"""


@cli.command("download-models")
def download_models():
    """下载 Docling 所需模型（首次运行）。"""
    click.echo("正在下载 Docling 模型...")
    pipeline = Pipeline(Path.cwd())
    pipeline.download_docling_models()
    click.echo("完成。")


@cli.command("parse-pdfs")
@click.option("--parallel/--sequential", default=True, help="并行或串行解析")
@click.option("--chunk-size", default=2, help="每个 worker 处理的 PDF 数")
@click.option("--max-workers", default=1, help="并行 worker 数（EasyOCR 占内存大，默认 1）")
def parse_pdfs(parallel, chunk_size, max_workers):
    """解析 pdf_reports/ 下的 PDF。"""
    root_path = Path.cwd()
    pipeline = Pipeline(root_path)
    click.echo(
        f"解析 PDF (parallel={parallel}, chunk_size={chunk_size}, "
        f"max_workers={max_workers})"
    )
    pipeline.parse_pdf_reports(
        parallel=parallel,
        chunk_size=chunk_size,
        max_workers=max_workers,
    )


@cli.command("export-images")
def export_images():
    """从 PDF 导出页图至 debug_data/04_page_images/。"""
    pipeline = Pipeline(Path.cwd())
    click.echo("导出页图...")
    pipeline.export_page_images()
    click.echo("完成。")


@cli.command("preprocess-reports")
@click.option(
    "--config",
    type=click.Choice(["no_ser_tab"]),
    default="no_ser_tab",
    help="预处理配置",
)
def preprocess_reports_cmd(config):
    """合并、导出 Markdown、页图、分块（不含建库）。"""
    pipeline = Pipeline(Path.cwd(), run_config=preprocess_configs[config])
    click.echo(f"预处理报告 (config={config})...")
    pipeline.preprocess_reports()
    click.echo("完成。")


@cli.command("build-index")
def build_index():
    """从 chunked_reports 构建 FAISS 向量库。"""
    pipeline = Pipeline(Path.cwd())
    click.echo("构建向量库...")
    pipeline.build_index()
    click.echo("完成。")


@cli.command("process-reports")
@click.option(
    "--config",
    type=click.Choice(["no_ser_tab"]),
    default="no_ser_tab",
    help="预处理配置",
)
def process_reports(config):
    """预处理 + 建向量库（全量建库）。"""
    pipeline = Pipeline(Path.cwd(), run_config=preprocess_configs[config])
    click.echo(f"处理报告并建库 (config={config})...")
    pipeline.process_parsed_reports()
    click.echo("完成。")


@cli.command("build-all")
@click.option("--skip-download", is_flag=True, help="跳过 Docling 模型下载（已下载过时使用）")
@click.option("--parallel/--sequential", default=True, help="并行或串行解析 PDF")
@click.option("--chunk-size", default=2, help="每个 worker 处理的 PDF 数")
@click.option("--max-workers", default=1, help="并行 worker 数（EasyOCR 占内存大，默认 1）")
@click.option(
    "--config",
    type=click.Choice(["no_ser_tab"]),
    default="no_ser_tab",
    help="预处理配置",
)
def build_all(skip_download, parallel, chunk_size, max_workers, config):
    """一键离线建库：download-models → parse-pdfs → process-reports → verify-index。"""
    root_path = Path.cwd()
    pipeline = Pipeline(root_path, run_config=preprocess_configs[config])
    click.echo(
        f"开始一键离线建库 (config={config}, skip_download={skip_download})..."
    )
    try:
        pipeline.build_offline_knowledge_base(
            skip_download=skip_download,
            parallel=parallel,
            chunk_size=chunk_size,
            max_workers=max_workers,
        )
    except RuntimeError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1) from e
    indexed, total = pipeline.count_indexed_documents()
    click.echo(f"完成。已索引 {indexed}/{total} 份文档。")


@cli.command("resume-build")
@click.option(
    "--config",
    type=click.Choice(["no_ser_tab"]),
    default="no_ser_tab",
    help="预处理配置",
)
@click.option(
    "--from-step",
    type=click.Choice(["markdown", "index"]),
    default="markdown",
    help="从哪一步续跑（markdown=导出MD起，index=仅建库校验）",
)
def resume_build(config, from_step):
    """从 merge 完成后续跑：跳过模型下载、PDF 解析与 merge。"""
    root_path = Path.cwd()
    pipeline = Pipeline(root_path, run_config=preprocess_configs[config])
    click.echo(f"从 merge 完成后续跑建库 (config={config}, from={from_step})...")
    try:
        if from_step == "index":
            pipeline.create_vector_dbs()
            from src.index_verifier import verify_indexes
            report = verify_indexes(root_path)
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
        else:
            pipeline.resume_offline_knowledge_base()
    except RuntimeError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1) from e
    indexed, total = pipeline.count_indexed_documents()
    click.echo(f"完成。已索引 {indexed}/{total} 份文档。")


@cli.command("verify-index")
def verify_index():
    """校验 FAISS 索引完整性。"""
    report = verify_indexes(Path.cwd())
    click.echo(f"总计 {report.total}，通过 {report.passed}")
    for item in report.items:
        status = "OK" if item.passed else "FAIL"
        click.echo(f"  [{status}] {item.doc_id} ({item.sha1[:8]}...)")
        for err in item.errors:
            click.echo(f"       - {err}")
    if not report.all_passed:
        raise SystemExit(1)


@cli.command("process-questions")
@click.option(
    "--config",
    type=click.Choice(["enterprise"]),
    default="enterprise",
    help="问答配置",
)
def process_questions(config):
    """批量处理 questions.json。"""
    pipeline = Pipeline(Path.cwd(), run_config=configs[config])
    click.echo(f"批量问答 (config={config})...")
    output = pipeline.process_questions()
    click.echo(f"答案已保存至 {output}")


if __name__ == "__main__":
    cli()
