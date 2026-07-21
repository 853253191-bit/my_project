# -*- coding: utf-8 -*-
"""扫描暂存目录，将 txt 归档为 Obsidian Markdown。"""

from __future__ import annotations

import os
import re
import traceback
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from run_digest import load_config, log_line, today_str

# ---------------------------------------------------------------------------
# 配置与路径
# ---------------------------------------------------------------------------


def staging_dir(cfg: dict) -> Path:
    return Path(cfg["staging_dir"])


def vault_dir(cfg: dict) -> Path:
    return Path(cfg["vault_dir"])


def digest_inbox_rel(cfg: dict) -> Path:
    return Path(cfg["digest_folder"]) / cfg["digest_inbox"]


def diary_folder_name(cfg: dict) -> str:
    return cfg["diary_folder"]


def diary_inbox_rel(cfg: dict) -> Path:
    return Path(cfg["diary_folder"]) / cfg["diary_inbox"]


def is_blank_txt(path: Path) -> bool:
    if not path.is_file():
        return True
    return path.read_text(encoding="utf-8").strip() == ""


def rel_staging_path(txt_path: Path, cfg: dict) -> Path:
    return txt_path.relative_to(staging_dir(cfg))


def vault_md_path(txt_path: Path, cfg: dict) -> Path:
    rel = rel_staging_path(txt_path, cfg)
    return vault_dir(cfg) / rel.with_suffix(".md")


def is_digest_inbox(txt_path: Path, cfg: dict) -> bool:
    try:
        return rel_staging_path(txt_path, cfg) == digest_inbox_rel(cfg)
    except ValueError:
        return False


def is_diary_folder(txt_path: Path, cfg: dict) -> bool:
    try:
        rel = rel_staging_path(txt_path, cfg)
    except ValueError:
        return False
    parts = rel.parts
    return len(parts) >= 1 and parts[0] == diary_folder_name(cfg)


def is_diary_inbox(txt_path: Path, cfg: dict) -> bool:
    try:
        return rel_staging_path(txt_path, cfg) == diary_inbox_rel(cfg)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# 日记块解析
# ---------------------------------------------------------------------------

BLOCK_RE = re.compile(
    r"---\s*\n(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*\n([\s\S]*?)\n---",
    re.MULTILINE,
)


def parse_blocks(text: str) -> list[tuple[str, str]]:
    """返回 [(时间戳, 正文), ...]"""
    blocks: list[tuple[str, str]] = []
    for m in BLOCK_RE.finditer(text):
        ts = m.group(1).strip()
        body = m.group(2).strip()
        if body:
            blocks.append((ts, body))
    return blocks


def blocks_for_date(text: str, date_str: str) -> list[tuple[str, str]]:
    return [(ts, body) for ts, body in parse_blocks(text) if ts.startswith(date_str)]


def rebuild_inbox_without_date(text: str, date_str: str) -> str:
    """移除指定日期的块，保留其余块；无剩余时返回空字符串。"""
    remaining = [(ts, body) for ts, body in parse_blocks(text) if not ts.startswith(date_str)]
    if not remaining:
        return ""
    parts: list[str] = []
    for ts, body in remaining:
        parts.append(f"---\n{ts}\n{body}\n---")
    return "\n".join(parts) + "\n"


def diary_md_from_inbox(text: str, date_str: str) -> str:
    """日记暂存：只取当天块，不改写，直接生成 Markdown。"""
    blocks = blocks_for_date(text, date_str)
    if blocks:
        sections = []
        for ts, body in blocks:
            sections.append(f"## {ts}\n\n{body}")
        body = "\n\n".join(sections)
    else:
        body = text.strip()
        if not body:
            return ""
    now = datetime.now().strftime("%H:%M")
    return f"# {date_str} 日记\n\n> 来源：日记暂存 | 整理时间：{now}\n\n{body}\n"


def direct_md_from_txt(text: str, title: str) -> str:
    """日记目录内其它 txt：标题 + 原文，不改写。"""
    body = text.strip()
    if not body:
        return ""
    return f"# {title}\n\n{body}\n"


def strip_md_fence(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


# ---------------------------------------------------------------------------
# LLM 改写
# ---------------------------------------------------------------------------


def rewrite_with_llm(content: str, filename: str, cfg: dict) -> str:
    skill_path = Path(cfg["archive_skill_path"])
    if not skill_path.is_file():
        raise RuntimeError(f"找不到归档 Skill: {skill_path}")
    skill_text = skill_path.read_text(encoding="utf-8")

    api_key_env = cfg.get("api_key_env", "DASHSCOPE_API_KEY")
    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"环境变量 {api_key_env} 未设置或为空")

    client = OpenAI(
        api_key=api_key,
        base_url=cfg.get(
            "model_server",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
    )
    resp = client.chat.completions.create(
        model=cfg.get("model", "qwen-flash"),
        messages=[
            {"role": "system", "content": skill_text},
            {
                "role": "user",
                "content": (
                    f"请将下列暂存 txt 改写成 Markdown 笔记。\n"
                    f"文件名：{filename}\n\n"
                    f"原文：\n{content}"
                ),
            },
        ],
        temperature=0.3,
    )
    md = resp.choices[0].message.content or ""
    md = strip_md_fence(md)
    if not md.strip():
        raise RuntimeError("大模型返回空内容")
    return md.strip() + "\n"


# ---------------------------------------------------------------------------
# 单文件归档
# ---------------------------------------------------------------------------


def write_md(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def archive_diary_inbox(txt_path: Path, cfg: dict) -> bool:
    text = txt_path.read_text(encoding="utf-8")
    date_str = today_str()
    today_blocks = blocks_for_date(text, date_str)
    all_blocks = parse_blocks(text)

    if today_blocks:
        md_content = diary_md_from_inbox(text, date_str)
        remaining = rebuild_inbox_without_date(text, date_str)
    elif not all_blocks and text.strip():
        # 无时间戳块时，整份视为当日内容
        md_content = diary_md_from_inbox(text, date_str)
        remaining = ""
    else:
        log_line(f"跳过日记暂存：今日无内容 ({txt_path.name})")
        return True

    if not md_content.strip():
        log_line(f"跳过日记暂存：今日无内容 ({txt_path.name})")
        return True

    target = vault_dir(cfg) / diary_folder_name(cfg) / f"{date_str}-日记.md"
    write_md(target, md_content)
    txt_path.write_text(remaining, encoding="utf-8")
    log_line(f"日记归档成功（已清除当日内容，保留文件）：{target}")
    return True


def archive_diary_other(txt_path: Path, cfg: dict) -> bool:
    text = txt_path.read_text(encoding="utf-8")
    title = txt_path.stem
    md_content = direct_md_from_txt(text, title)
    if not md_content.strip():
        log_line(f"跳过空日记文件：{txt_path}")
        return True

    target = vault_md_path(txt_path, cfg)
    write_md(target, md_content)
    log_line(f"日记归档成功（保留 txt）：{target}")
    return True


def archive_llm_txt(txt_path: Path, cfg: dict) -> bool:
    text = txt_path.read_text(encoding="utf-8")
    md_content = rewrite_with_llm(text, txt_path.name, cfg)
    target = vault_md_path(txt_path, cfg)
    write_md(target, md_content)
    txt_path.unlink()
    log_line(f"归档成功（已删 txt）：{target}")
    return True


def collect_txt_files(cfg: dict) -> list[Path]:
    """扫描暂存目录下所有非空 txt；除 digest_inbox 外均参与归档（含 05/06 等分类文件夹）。"""
    root = staging_dir(cfg)
    if not root.is_dir():
        return []
    files: list[Path] = []
    for txt in sorted(root.rglob("*.txt")):
        if is_digest_inbox(txt, cfg):
            continue
        if is_blank_txt(txt):
            continue
        files.append(txt)
    return files


def sync_staging_dirs_to_vault(cfg: dict) -> int:
    """把暂存文件下的目录结构同步到仓库：只创建缺失目录，不删除仓库目录与文件。"""
    root = staging_dir(cfg)
    vault = vault_dir(cfg)
    if not root.is_dir():
        return 0

    vault.mkdir(parents=True, exist_ok=True)
    created = 0
    for d in sorted(root.rglob("*")):
        if not d.is_dir():
            continue
        rel = d.relative_to(root)
        target = vault / rel
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            created += 1
            log_line(f"已同步新建目录到仓库：{rel}")
    return created


def archive_one(txt_path: Path, cfg: dict) -> bool:
    rel = rel_staging_path(txt_path, cfg)
    log_line(f"归档开始：{rel}")

    try:
        if is_diary_inbox(txt_path, cfg):
            return archive_diary_inbox(txt_path, cfg)
        if is_diary_folder(txt_path, cfg):
            return archive_diary_other(txt_path, cfg)
        return archive_llm_txt(txt_path, cfg)
    except Exception as exc:  # noqa: BLE001
        log_line(f"归档失败：{rel} -> {exc}")
        log_line(traceback.format_exc())
        return False


def main() -> int:
    cfg = load_config()
    log_line("=== run_archive 开始 ===")

    created_dirs = sync_staging_dirs_to_vault(cfg)
    if created_dirs:
        log_line(f"目录同步完成：新建 {created_dirs} 个")
    else:
        log_line("目录同步：无新增目录")

    files = collect_txt_files(cfg)
    if not files:
        log_line("跳过：暂存目录无待归档 txt")
        log_line("=== run_archive 结束 exit=0 ===")
        return 0

    log_line(f"待归档 txt 数量：{len(files)}")
    failed = 0
    for txt_path in files:
        if not archive_one(txt_path, cfg):
            failed += 1

    if failed:
        log_line(f"=== run_archive 结束 exit=1（失败 {failed} 个）===")
        return 1

    log_line("=== run_archive 结束 exit=0 ===")
    return 0


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
