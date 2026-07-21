# -*- coding: utf-8 -*-
"""每日知识点整理入口：快检暂存后调用 Qwen-Agent，按 SKILL.md 执行整理。"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime
from pathlib import Path
from typing import Any, Union
from urllib.parse import quote_plus

import requests

# ---------------------------------------------------------------------------
# 路径与配置
# ---------------------------------------------------------------------------

RUNTIME_DIR = Path(__file__).resolve().parent
PROJECT_DIR = RUNTIME_DIR.parent
LOG_DIR = RUNTIME_DIR / "logs"
CONFIG_PATH = RUNTIME_DIR / "config.json"

DEFAULT_CONFIG = {
    "model": "qwen-flash",
    "model_server": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key_env": "DASHSCOPE_API_KEY",
    "timeout_minutes": 45,
    "staging_dir": str(PROJECT_DIR / "暂存文件"),
    "vault_dir": r"D:\陈总的ob仓库",
    "digest_folder": "04_每日知识点整理",
    "digest_inbox": "想法暂存.txt",
    "diary_folder": "11_小陈日记",
    "diary_inbox": "日记暂存.txt",
    "inbox_path": str(PROJECT_DIR / "暂存文件" / "04_每日知识点整理" / "想法暂存.txt"),
    "output_dir": r"D:\陈总的ob仓库\04_每日知识点整理",
    "skill_path": str(PROJECT_DIR / "skills" / "SKILL.md"),
    "archive_skill_path": str(PROJECT_DIR / "skills" / "SKILL-archive.md"),
}


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.is_file():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def output_md_path(output_dir: str) -> Path:
    return Path(output_dir) / f"{today_str()}-知识点整理.md"


def log_line(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}\n"
    log_file = LOG_DIR / f"{today_str()}.log"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(line)
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", errors="replace").decode("ascii", errors="replace"), flush=True)


def inbox_is_blank(inbox_path: Path) -> bool:
    if not inbox_path.is_file():
        return True
    text = inbox_path.read_text(encoding="utf-8")
    return text.strip() == ""


# ---------------------------------------------------------------------------
# Qwen-Agent 自定义工具
# ---------------------------------------------------------------------------

def _register_tools(inbox_path: str, output_dir: str) -> list:
    """注册读/写/清空/搜索工具，返回可供 Assistant 使用的工具实例列表。"""
    from qwen_agent.tools.base import BaseTool, register_tool

    @register_tool("read_inbox", allow_overwrite=True)
    class ReadInbox(BaseTool):
        description = "读取想法暂存.txt 的全部 UTF-8 内容。"
        parameters = {
            "type": "object",
            "properties": {
                "unused": {
                    "type": "string",
                    "description": "占位参数，可传空字符串",
                }
            },
            "required": [],
        }

        def call(self, params: Union[str, dict], **kwargs) -> str:
            if params:
                self._verify_json_format_args(params)
            path = Path(inbox_path)
            if not path.is_file():
                return "（文件不存在）"
            return path.read_text(encoding="utf-8")

    @register_tool("write_digest_md", allow_overwrite=True)
    class WriteDigestMd(BaseTool):
        description = (
            "将整理好的 Markdown 写入当日知识点文件（整文件覆盖）。"
            "参数 content 为完整 Markdown 正文。"
        )
        parameters = {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "完整 Markdown 内容",
                }
            },
            "required": ["content"],
        }

        def call(self, params: Union[str, dict], **kwargs) -> str:
            args = self._verify_json_format_args(params)
            content = args.get("content") or ""
            if not str(content).strip():
                return "错误：content 为空，未写入。"
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            target = output_md_path(output_dir)
            target.write_text(str(content), encoding="utf-8")
            return f"已写入: {target}"

    @register_tool("clear_inbox", allow_overwrite=True)
    class ClearInbox(BaseTool):
        description = (
            "仅在 Markdown 成功写出后调用：清空想法暂存.txt。"
            "写出失败时禁止调用。"
        )
        parameters = {
            "type": "object",
            "properties": {
                "unused": {
                    "type": "string",
                    "description": "占位参数，可传空字符串",
                }
            },
            "required": [],
        }

        def call(self, params: Union[str, dict], **kwargs) -> str:
            if params:
                self._verify_json_format_args(params)
            path = Path(inbox_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
            return "暂存已清空"

    @register_tool("knowledge_web_search", allow_overwrite=True)
    class WebSearchLite(BaseTool):
        description = "联网搜索知识点的简明解释。参数 query 为搜索词。"
        parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词",
                }
            },
            "required": ["query"],
        }

        def call(self, params: Union[str, dict], **kwargs) -> str:
            args = self._verify_json_format_args(params)
            query = (args.get("query") or "").strip()
            if not query:
                return "错误：query 为空"
            try:
                return _duckduckgo_search(query)
            except Exception as exc:  # noqa: BLE001
                return f"搜索失败: {exc}。请在说明中标明「暂未找到权威简述」。"

    return [ReadInbox(), WriteDigestMd(), ClearInbox(), WebSearchLite()]


def _duckduckgo_search(query: str, max_results: int = 5) -> str:
    """无第三方 API Key 的轻量搜索（DuckDuckGo HTML）。"""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    html = resp.text

    # 解析结果块：标题 + 摘要
    titles = re.findall(
        r'class="result__a"[^>]*>(.*?)</a>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    def _strip_tags(s: str) -> str:
        s = re.sub(r"<[^>]+>", "", s)
        return re.sub(r"\s+", " ", s).strip()

    lines: list[str] = []
    for i, title in enumerate(titles[:max_results], 1):
        snip = _strip_tags(snippets[i - 1]) if i - 1 < len(snippets) else ""
        lines.append(f"[{i}] {_strip_tags(title)}\n{snip}")

    if not lines:
        return "未检索到结果。请标明「暂未找到权威简述」。"
    return "\n\n".join(lines)


def run_agent(cfg: dict) -> str:
    """调用 Qwen-Agent 执行一次整理，返回最终回复文本。"""
    from qwen_agent.agents import Assistant

    api_key_env = cfg.get("api_key_env", "DASHSCOPE_API_KEY")
    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"环境变量 {api_key_env} 未设置或为空")

    skill_path = Path(cfg["skill_path"])
    if not skill_path.is_file():
        raise RuntimeError(f"找不到 SKILL.md: {skill_path}")
    skill_text = skill_path.read_text(encoding="utf-8")

    tools = _register_tools(cfg["inbox_path"], cfg["output_dir"])
    target = output_md_path(cfg["output_dir"])

    llm_cfg: dict[str, Any] = {
        "model": cfg.get("model", "qwen-plus"),
        "model_server": cfg.get(
            "model_server",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        "api_key": api_key,
        "generate_cfg": {
            "temperature": 0.3,
        },
    }

    system_message = (
        "你是无人值守的每日知识点整理 Agent。必须严格按下列 Skill 执行，"
        "不要改其它目录，不要创建备份文件。\n\n"
        f"{skill_text}\n\n"
        "工具约定：\n"
        "1. 用 read_inbox 读取暂存；\n"
        "2. 对每个知识点用 knowledge_web_search 检索后再写说明；\n"
        "3. 用 write_digest_md 写入完整 Markdown（一次写入完整文件）；\n"
        "4. 仅在写入成功后调用 clear_inbox；\n"
        "5. 若无实质内容，不要写 MD、不要清空。\n"
    )

    bot = Assistant(
        llm=llm_cfg,
        system_message=system_message,
        function_list=tools,
        name="daily-knowledge-digest",
    )

    user_msg = (
        "请立即执行今日知识点整理。"
        f"今日日期（本地时区）为 {today_str()}，"
        f"输出文件应为：{target}。"
        "完成后用两三句话说明：处理了几条、输出路径、暂存是否已清空。"
    )

    messages = [{"role": "user", "content": user_msg}]
    final_text = ""
    for response in bot.run(messages):
        if isinstance(response, list) and response:
            last = response[-1]
            if isinstance(last, dict) and last.get("content"):
                final_text = str(last["content"])
        elif isinstance(response, dict) and response.get("content"):
            final_text = str(response["content"])
    return final_text or "（Agent 无文本回复）"


def verify_output(cfg: dict, started_at: float) -> bool:
    """检查当日 MD 是否在本次运行中写出且非空。"""
    target = output_md_path(cfg["output_dir"])
    if not target.is_file():
        return False
    try:
        text = target.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not text:
        return False
    mtime = target.stat().st_mtime
    # 允许时钟误差：文件修改时间应不早于启动前 5 秒
    return mtime >= (started_at - 5)


def main() -> int:
    cfg = load_config()
    log_line("=== run_digest 开始 ===")
    inbox = Path(cfg["inbox_path"])

    if inbox_is_blank(inbox):
        log_line("跳过：无内容")
        log_line("=== run_digest 结束 exit=0 ===")
        return 0

    started_at = time.time()
    timeout_sec = int(cfg.get("timeout_minutes", 45)) * 60

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(run_agent, cfg)
            try:
                result_text = fut.result(timeout=timeout_sec)
            except FuturesTimeout:
                log_line(f"错误：超时（>{timeout_sec}s），不清空暂存")
                log_line("=== run_digest 结束 exit=1 ===")
                return 1
        log_line(f"Agent 回复摘要: {result_text[:500]}")
    except Exception as exc:  # noqa: BLE001
        log_line(f"错误：启动或运行失败: {exc}")
        log_line(traceback.format_exc())
        log_line("=== run_digest 结束 exit=1 ===")
        return 1

    if not verify_output(cfg, started_at):
        log_line("错误：未检测到有效的当日 MD 输出，不清空暂存（由脚本判定）")
        log_line("=== run_digest 结束 exit=2 ===")
        return 2

    log_line(f"成功：已写出 {output_md_path(cfg['output_dir'])}")
    log_line("=== run_digest 结束 exit=0 ===")
    return 0


if __name__ == "__main__":
    # Windows 控制台尽量用 UTF-8，避免中文日志乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
