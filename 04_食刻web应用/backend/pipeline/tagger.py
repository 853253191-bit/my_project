# -*- coding: utf-8 -*-
"""菜谱批量打标签脚本：读取 SQLite，调用兼容 OpenAI 的 LLM，写入 ai_tags。

依赖安装:
  pip install openai python-dotenv

环境变量（可写在项目根目录 .env）:
  OPENAI_API_KEY   - API Key（必填）
  OPENAI_BASE_URL  - API Base URL，如 https://api.deepseek.com/v1
  OPENAI_MODEL     - 模型名，如 qwen-flash / qwen-turbo / qwen-plus

用法:
  cd backend
  python -m pipeline.tagger --limit 5
  python -m pipeline.tagger --workers 8
  python -m pipeline.tagger
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------------------------------------------------------
# 请在此处手动配置本地 SQLite 路径（相对路径相对于 backend 目录）
# ---------------------------------------------------------------------------
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "sqlite" / "recipes.db"

SYSTEM_PROMPT = """
你是一位专业的美食专家和数据标注员。请分析给定的菜谱，并只输出符合以下 JSON Schema 的合法 JSON 对象。

严格标注规则（必须遵守）
meta.cuisine（菜系）
必须从以下列表中选 1-3 个：鲁菜, 川菜, 粤菜, 苏菜, 浙菜, 闽菜, 湘菜, 徽菜, 东北菜, 西北菜, 云南菜, 贵州菜, 日式, 韩式, 西式, 东南亚, 其他。

绝对禁止使用："家常菜"、"中式"、"地方菜"、"妈妈菜"。如果实在无法归类，只能填 ["其他"]。

### sensory.taste_profiles（口味）
- **"咸鲜"使用限制（铁律）**：只有当菜肴风味**纯粹依赖盐和味精**，且没有酱料、蒜、醋、糖、辣椒、香料等任何明显特征时，才允许填入"咸鲜"。绝大多数家常菜都有更准确的风味标签。
- **强制优先映射（必须遵守）**：
  - 红烧肉 → 必须优先写 ["酱香"]（可搭配"咸鲜"，但绝不能只有"咸鲜"）
  - 番茄炒蛋 / 糖醋排骨 → 必须优先写 ["酸甜"]
  - 麻婆豆腐 / 水煮鱼 → 必须优先写 ["麻辣"] 或 ["香辣"]
  - 酸菜鱼 / 酸辣汤 → 必须优先写 ["酸辣"]
  - 清炒时蔬（蒜蓉） → 必须优先写 ["蒜香"]
  - 葱烧海参 / 葱油拌面 → 必须优先写 ["葱香"]
  - 咖喱鸡 / 泰式咖喱 → 必须优先写 ["咖喱"]
- 可选口味词表：咸鲜, 酸甜, 麻辣, 酸辣, 蒜香, 咖喱, 鱼香, 葱香, 黑椒, 奶香, 酱香, 香辣, 甜香, 清香。
- **输出要求**：每道菜必须输出 2 个风味标签（数组长度 ≥ 2）。如果使用了"咸鲜"，第二个标签必须是上述具体风味之一（如 ["酱香", "咸鲜"] 可以，但 ["咸鲜"] 单独出现视为违规）。

sensory.greasiness（油腻度，整数 1-5）
使用绝对锚定标准：

1 = 水煮青菜、清汤。

2 = 少油清炒蔬菜。

3 = 普通家常炒肉。

4 = 红烧肉级别。

5 = 油炸酥肉、重油焖炖。

不要总是给 2-3 分，要按真实情况分布。

### logistics.difficulty（难度）
参照家常菜相对标准：
- "easy"：单次烹饪、无需焯水/过油、准备+烹饪 ≤ 30 分钟（如炒青菜、凉拌、紫菜蛋花汤）。
- "medium"：需要焯水、过油、炒糖色、长时间炖煮（30-60分钟）或简单蒸制（如红烧肉、炖牛腩、清蒸鲈鱼、可乐鸡翅）。
- "hard"：满足以下任一条件：① 总烹饪时间 > 60 分钟；② 涉及发酵（如发面做包子）；③ 刀工要求极高（如文思豆腐）；④ 工序超过 5 步且包含多种预处理（如佛跳墙、自制烧卖）。
- **特别提示**：红烧肉、红烧排骨等经典硬菜，因为涉及炒糖色+长时间焖炖，**至少标为 "medium"**，如果菜谱描述中步骤复杂则标为 "hard"。

health.allergens（过敏原）
仅当菜谱明确含有以下八大类时，才填入对应具体名称：麸质（小麦）、甲壳类（虾蟹）、蛋、鱼、花生、大豆、乳制品、坚果。

使用具体名词，如 "花生"、"虾"。没有则留空数组 []。

decision_summary（决策摘要）
15-20 个中文字符。语气要平静、具体、生活化，描述「适合什么时候吃/谁吃」。

禁止：感叹号、夸张词（"超级"、"绝绝子"、"好吃到飞起"）。

好例子："加班后暖胃的快手汤"。坏例子："超级美味的麻辣锅！"

输出 JSON Schema（请严格遵循）：
{
"meta": {
"cuisine": ["string"],
"meal_type": ["string"],
"cooking_method": ["string"]
},
"sensory": {
"taste_profiles": ["string"],
"spicy_level": 0-5,
"greasiness": 1-5,
"texture": ["string"]
},
"health": {
"diet_labels": ["string"],
"allergens": ["string"]
},
"logistics": {
"estimated_time_minutes": 0,
"difficulty": "easy|medium|hard",
"serving_size": 0
},
"decision_summary": "string"
}
"""

logger = logging.getLogger("tagger")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def connect_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite 文件不存在: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_table_columns(conn: sqlite3.Connection, table: str = "recipes") -> list[str]:
    """探查表结构，返回列名列表。"""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if not rows:
        raise RuntimeError(f"未找到表: {table}")
    cols = [r["name"] for r in rows]
    logger.info("表 %s 列: %s", table, ", ".join(cols))
    return cols


def ensure_tag_columns(conn: sqlite3.Connection, table: str = "recipes") -> None:
    """确保 ai_tags / ai_tags_old / ai_tags_v2 列存在。"""
    cols = get_table_columns(conn, table)
    for col in ("ai_tags", "ai_tags_old", "ai_tags_v2"):
        if col not in cols:
            logger.info("添加列 %s (TEXT) ...", col)
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
            conn.commit()
            cols.append(col)
        else:
            logger.info("列 %s 已存在", col)


def backup_ai_tags_once(conn: sqlite3.Connection, table: str = "recipes") -> int:
    """将尚未备份的 ai_tags 复制到 ai_tags_old（仅空 old 时）。"""
    cur = conn.execute(
        f"""
        UPDATE {table}
        SET ai_tags_old = ai_tags
        WHERE ai_tags IS NOT NULL
          AND trim(ai_tags) != ''
          AND (ai_tags_old IS NULL OR trim(ai_tags_old) = '')
        """
    )
    conn.commit()
    n = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
    logger.info("已备份 ai_tags -> ai_tags_old: %d 条", n)
    return n


def snapshot_ai_tags_v2(conn: sqlite3.Connection, table: str = "recipes") -> int:
    """将当前 ai_tags 快照为第二版（ai_tags_v2），仅空 v2 时写入。"""
    cur = conn.execute(
        f"""
        UPDATE {table}
        SET ai_tags_v2 = ai_tags
        WHERE ai_tags IS NOT NULL
          AND trim(ai_tags) != ''
          AND (ai_tags_v2 IS NULL OR trim(ai_tags_v2) = '')
        """
    )
    conn.commit()
    n = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
    logger.info("已快照 ai_tags -> ai_tags_v2: %d 条", n)
    return n


def clear_ai_tags_for_sample(
    conn: sqlite3.Connection,
    limit: int = 50,
    table: str = "recipes",
) -> list[str]:
    """清空对比样本的 ai_tags（优先已有 ai_tags_old 的前 N 条），返回 id 列表。"""
    rows = conn.execute(
        f"""
        SELECT id FROM {table}
        WHERE ai_tags_old IS NOT NULL AND trim(ai_tags_old) != ''
        ORDER BY rowid ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    ids = [r["id"] for r in rows]
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE {table} SET ai_tags = NULL WHERE id IN ({placeholders})",
        ids,
    )
    conn.commit()
    logger.info("已清空 ai_tags: %d 条（保留 ai_tags_old / ai_tags_v2）", len(ids))
    return ids


def _flatten_value(value: Any, depth: int = 0) -> str:
    """将任意嵌套结构展平为可读纯文本。"""
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        if (text.startswith("{") and text.endswith("}")) or (
            text.startswith("[") and text.endswith("]")
        ):
            try:
                return _flatten_value(json.loads(text), depth)
            except json.JSONDecodeError:
                return text
        return text
    if isinstance(value, dict):
        parts: list[str] = []
        for k, v in value.items():
            flat = _flatten_value(v, depth + 1)
            if not flat:
                continue
            if k == "name" and isinstance(value.get("amount"), (str, int, float)):
                continue
            parts.append(f"{k}: {flat}" if depth == 0 else f"{k}={flat}")
        if "name" in value:
            name = str(value.get("name", "")).strip()
            amount = str(value.get("amount", "") or "").strip()
            unit = str(value.get("unit", "") or "").strip()
            if name:
                qty = f"{amount}{unit}".strip()
                return f"{name}({qty})" if qty else name
        return "; ".join(parts)
    if isinstance(value, list):
        items = [_flatten_value(item, depth + 1) for item in value]
        items = [i for i in items if i]
        return ", ".join(items)
    return str(value)


def flatten_field(raw: Any) -> str:
    """解析可能为 JSON 字符串的字段并展平。"""
    if raw is None:
        return ""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return ""
        try:
            parsed = json.loads(text)
            return _flatten_value(parsed)
        except json.JSONDecodeError:
            return text
    return _flatten_value(raw)


def build_recipe_prompt(row: sqlite3.Row | dict[str, Any]) -> str:
    """将一行菜谱组装为结构化提示词文本块。"""
    data = dict(row)
    lines: list[str] = []

    title = (data.get("title") or "").strip()
    lines.append(f"Recipe Title: {title or '(untitled)'}")

    desc = (data.get("description") or "").strip()
    if desc:
        lines.append(f"Description: {desc}")

    cuisine = (data.get("cuisine") or "").strip()
    if cuisine:
        lines.append(f"Listed Cuisine: {cuisine}")

    difficulty = (data.get("difficulty") or "").strip()
    if difficulty:
        lines.append(f"Listed Difficulty: {difficulty}")

    if data.get("cook_minutes") is not None:
        lines.append(f"Listed Cook Minutes: {data.get('cook_minutes')}")
    if data.get("servings") is not None:
        lines.append(f"Listed Servings: {data.get('servings')}")

    ingredients = flatten_field(data.get("ingredients"))
    if ingredients:
        lines.append(f"Ingredients: {ingredients}")

    steps = flatten_field(data.get("steps"))
    if steps:
        lines.append(f"Steps: {steps}")

    for tag_key, label in (
        ("mood_tags", "Mood Tags"),
        ("taste_tags", "Taste Tags"),
        ("health_tags", "Health Tags"),
        ("weather_tags", "Weather Tags"),
        ("tags", "Tags"),
    ):
        if tag_key not in data:
            continue
        flat = flatten_field(data.get(tag_key))
        if flat:
            lines.append(f"{label}: {flat}")

    nutrition = flatten_field(data.get("nutrition"))
    if nutrition:
        lines.append(f"Nutrition: {nutrition}")

    source = (data.get("source_site") or "").strip()
    if source:
        lines.append(f"Source Site: {source}")

    lines.append("\n请分析该菜谱，并只返回符合 Schema 的 JSON 对象。")
    return "\n".join(lines)


def extract_json_object(text: str) -> dict[str, Any]:
    """从 LLM 返回文本中提取 JSON 对象。"""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("LLM 返回的不是 JSON 对象")
    return obj


def validate_tags(tags: dict[str, Any]) -> dict[str, Any]:
    """做基础结构校验与轻量规范化。"""
    required_top = ("meta", "sensory", "health", "logistics", "decision_summary")
    for key in required_top:
        if key not in tags:
            raise ValueError(f"缺少字段: {key}")

    sensory = tags["sensory"]
    spicy = int(sensory.get("spicy_level", 0))
    grease = int(sensory.get("greasiness", 1))
    if not 0 <= spicy <= 5:
        raise ValueError(f"spicy_level 超出范围: {spicy}")
    if not 1 <= grease <= 5:
        raise ValueError(f"greasiness 超出范围: {grease}")
    sensory["spicy_level"] = spicy
    sensory["greasiness"] = grease

    difficulty = str(tags["logistics"].get("difficulty", "")).lower().strip()
    if difficulty not in ("easy", "medium", "hard"):
        mapping = {
            "简单": "easy",
            "容易": "easy",
            "中等": "medium",
            "一般": "medium",
            "困难": "hard",
            "难": "hard",
        }
        difficulty = mapping.get(difficulty, difficulty)
    if difficulty not in ("easy", "medium", "hard"):
        raise ValueError(f"difficulty 非法: {tags['logistics'].get('difficulty')}")
    tags["logistics"]["difficulty"] = difficulty
    tags["logistics"]["estimated_time_minutes"] = int(
        tags["logistics"].get("estimated_time_minutes") or 0
    )
    tags["logistics"]["serving_size"] = int(tags["logistics"].get("serving_size") or 0)

    summary = str(tags.get("decision_summary") or "").strip().replace("！", "").replace("!", "")
    if len(summary) > 20:
        summary = summary[:20]
    tags["decision_summary"] = summary

    cuisine = tags["meta"].get("cuisine") or []
    if isinstance(cuisine, list):
        banned = {"家常菜", "中式", "地方菜", "妈妈菜"}
        cleaned = [c for c in cuisine if c not in banned]
        if not cleaned:
            cleaned = ["其他"]
        tags["meta"]["cuisine"] = cleaned[:3]

    # 口味：至少 2 个；禁止单独只有「咸鲜」
    tastes = sensory.get("taste_profiles") or []
    if not isinstance(tastes, list):
        raise ValueError("taste_profiles 必须是数组")
    tastes = [str(t).strip() for t in tastes if str(t).strip()]
    if len(tastes) < 2:
        raise ValueError(f"taste_profiles 至少需要 2 个标签，当前: {tastes}")
    if tastes == ["咸鲜"] or (len(tastes) == 1 and tastes[0] == "咸鲜"):
        raise ValueError('taste_profiles 不允许单独只有"咸鲜"')
    if len(tastes) == 1:
        raise ValueError(f"taste_profiles 至少需要 2 个标签，当前: {tastes}")
    sensory["taste_profiles"] = tastes[:3]

    return tags


def create_llm_client() -> tuple[OpenAI, str]:
    """从环境变量创建 OpenAI 兼容客户端。"""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip() or "qwen-plus"

    if not api_key:
        raise RuntimeError("请设置环境变量 OPENAI_API_KEY")
    if not base_url:
        raise RuntimeError("请设置环境变量 OPENAI_BASE_URL")

    client = OpenAI(api_key=api_key, base_url=base_url)
    logger.info("LLM: model=%s base_url=%s", model, base_url)
    return client, model


def call_llm_for_tags(client: OpenAI, model: str, recipe_text: str) -> dict[str, Any]:
    """调用 LLM，返回校验后的标签 JSON。"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": recipe_text},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or ""
    tags = extract_json_object(content)
    return validate_tags(tags)


def is_ai_tags_empty(value: Any) -> bool:
    """判断 ai_tags 是否视为空（需打标）。"""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def fetch_recipes(
    conn: sqlite3.Connection,
    limit: int | None,
    force: bool = False,
    table: str = "recipes",
) -> list[sqlite3.Row]:
    """读取待处理菜谱。

    - 默认：跳过已有 ai_tags 的行，按 rowid（入库顺序）取前 N 条
    - --force：优先取已有 ai_tags_old 的样本做新旧对比；
      若尚无备份，则按 rowid 取前 N 条强制重跑
      （不用字符串 id 排序，避免 douguo_104... 与首次样本错位）
    """
    params: list[Any] = []
    if force:
        # 优先重跑「已备份旧标签」的样本，保证对比报告有意义
        sql = (
            f"SELECT * FROM {table} "
            f"WHERE ai_tags_old IS NOT NULL AND trim(ai_tags_old) != '' "
            f"ORDER BY rowid ASC"
        )
        if limit is not None and limit > 0:
            sql += " LIMIT ?"
            params.append(limit)
        rows = list(conn.execute(sql, params).fetchall())
        if rows:
            return rows
        # 尚无备份时：按入库顺序取前 N 条
        params = []
        sql = f"SELECT * FROM {table} ORDER BY rowid ASC"
    else:
        sql = (
            f"SELECT * FROM {table} "
            f"WHERE ai_tags IS NULL OR trim(ai_tags) = '' "
            f"ORDER BY rowid ASC"
        )
    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return list(rows)


def update_ai_tags(
    conn: sqlite3.Connection,
    recipe_id: str,
    tags: dict[str, Any],
    table: str = "recipes",
    *,
    commit: bool = True,
) -> None:
    payload = json.dumps(tags, ensure_ascii=False)
    conn.execute(
        f"UPDATE {table} SET ai_tags = ? WHERE id = ?",
        (payload, recipe_id),
    )
    if commit:
        conn.commit()


def _tag_one_recipe(
    row: sqlite3.Row,
    client: OpenAI,
    model: str,
    db_path: Path,
    dry_run: bool,
    write_lock: threading.Lock,
) -> tuple[str, str, str | None, str | None]:
    """处理单条菜谱，返回 (recipe_id, title, summary, error)。"""
    recipe_id = row["id"]
    title = (row["title"] or "").strip() or recipe_id
    try:
        prompt = build_recipe_prompt(row)
        tags = call_llm_for_tags(client, model, prompt)
        summary = str(tags.get("decision_summary", ""))
        if not dry_run:
            with write_lock:
                conn = connect_db(db_path)
                try:
                    update_ai_tags(conn, recipe_id, tags, commit=True)
                finally:
                    conn.close()
        return recipe_id, title, summary, None
    except Exception as exc:  # noqa: BLE001
        return recipe_id, title, None, str(exc)


def _safe_load_tags(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, str) and not raw.strip():
        return None
    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _pct(count: int, total: int) -> str:
    if total <= 0:
        return "0%"
    return f"{count / total * 100:.1f}%".replace(".0%", "%")


def _format_greasiness_dist(counter: Counter, total: int) -> str:
    parts = []
    for level in range(1, 6):
        parts.append(f"{level}:{_pct(counter.get(level, 0), total)}")
    return "(" + ", ".join(parts) + ")"


def _format_difficulty_dist(counter: Counter, total: int) -> str:
    return (
        f"(easy:{_pct(counter.get('easy', 0), total)}, "
        f"medium:{_pct(counter.get('medium', 0), total)}, "
        f"hard:{_pct(counter.get('hard', 0), total)})"
    )


def _collect_stats(tag_list: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(tag_list)
    xianxian = 0
    jiachang = 0
    grease = Counter()
    difficulty = Counter()
    for tags in tag_list:
        tastes = (tags.get("sensory") or {}).get("taste_profiles") or []
        if any(t == "咸鲜" for t in tastes):
            xianxian += 1
        cuisines = (tags.get("meta") or {}).get("cuisine") or []
        if any(c == "家常菜" for c in cuisines):
            jiachang += 1
        g = (tags.get("sensory") or {}).get("greasiness")
        if g is not None:
            try:
                grease[int(g)] += 1
            except (TypeError, ValueError):
                pass
        d = (tags.get("logistics") or {}).get("difficulty")
        if d:
            difficulty[str(d).lower()] += 1
    return {
        "total": total,
        "xianxian": xianxian,
        "jiachang": jiachang,
        "grease": grease,
        "difficulty": difficulty,
    }


def print_comparison_report(
    conn: sqlite3.Connection,
    recipe_ids: list[str],
    table: str = "recipes",
) -> None:
    """打印三版 Prompt 对比：v1(ai_tags_old) → v2(ai_tags_v2) → v3(ai_tags)。"""
    if not recipe_ids:
        logger.info("无对比样本，跳过报告")
        return

    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    has_v2 = "ai_tags_v2" in cols
    select_cols = "id, ai_tags, ai_tags_old" + (", ai_tags_v2" if has_v2 else "")
    placeholders = ",".join("?" for _ in recipe_ids)
    rows = conn.execute(
        f"""
        SELECT {select_cols} FROM {table}
        WHERE id IN ({placeholders})
        """,
        recipe_ids,
    ).fetchall()

    v1_tags: list[dict[str, Any]] = []
    v2_tags: list[dict[str, Any]] = []
    v3_tags: list[dict[str, Any]] = []
    for row in rows:
        v1 = _safe_load_tags(row["ai_tags_old"])
        v3 = _safe_load_tags(row["ai_tags"])
        v2 = _safe_load_tags(row["ai_tags_v2"]) if has_v2 else None
        if v1 is not None:
            v1_tags.append(v1)
        if v2 is not None:
            v2_tags.append(v2)
        if v3 is not None:
            v3_tags.append(v3)

    if not v1_tags or not v3_tags:
        logger.warning(
            "对比样本不足（v1=%d, v2=%d, v3=%d），无法生成完整报告",
            len(v1_tags),
            len(v2_tags),
            len(v3_tags),
        )
        return

    s1 = _collect_stats(v1_tags)
    s3 = _collect_stats(v3_tags)
    s2 = _collect_stats(v2_tags) if v2_tags else None
    n1, n3 = s1["total"], s3["total"]
    n2 = s2["total"] if s2 else 0
    n_show = min(n1, n3, len(recipe_ids))

    def _chain_xianxian() -> str:
        parts = [f'v1 {_pct(s1["xianxian"], n1)}']
        if s2:
            parts.append(f'v2 {_pct(s2["xianxian"], n2)}')
        parts.append(f'v3 {_pct(s3["xianxian"], n3)}')
        return " → ".join(parts)

    def _chain_grease() -> str:
        parts = [f'v1 {_format_greasiness_dist(s1["grease"], n1)}']
        if s2:
            parts.append(f'v2 {_format_greasiness_dist(s2["grease"], n2)}')
        parts.append(f'v3 {_format_greasiness_dist(s3["grease"], n3)}')
        return " → ".join(parts)

    def _chain_diff() -> str:
        parts = [f'v1 {_format_difficulty_dist(s1["difficulty"], n1)}']
        if s2:
            parts.append(f'v2 {_format_difficulty_dist(s2["difficulty"], n2)}')
        parts.append(f'v3 {_format_difficulty_dist(s3["difficulty"], n3)}')
        return " → ".join(parts)

    def _chain_jiachang() -> str:
        parts = [f'v1 {_pct(s1["jiachang"], n1)}']
        if s2:
            parts.append(f'v2 {_pct(s2["jiachang"], n2)}')
        parts.append(f'v3 {_pct(s3["jiachang"], n3)}')
        return " → ".join(parts)

    hard_v3 = s3["difficulty"].get("hard", 0)
    lines = [
        f"========== Prompt 对比报告（前{n_show}条，v1→v2→v3） ==========",
        f'1. taste_profiles 包含"咸鲜"的比例：{_chain_xianxian()}',
        f"2. greasiness 分布：{_chain_grease()}",
        f"3. difficulty 分布：{_chain_diff()}",
        f'4. cuisine 包含"家常菜"的比例：{_chain_jiachang()}',
        f"5. v3 hard 数量：{hard_v3} / {n3}",
        "==================================================",
    ]
    report = "\n".join(lines)
    print(report)
    logger.info(
        "对比报告已输出（v1=%d, v2=%d, v3=%d）",
        n1,
        n2,
        n3,
    )


def process_recipes(
    db_path: Path,
    limit: int | None,
    dry_run: bool = False,
    force: bool = False,
    workers: int = 1,
) -> None:
    _, model = create_llm_client()
    conn = connect_db(db_path)
    try:
        ensure_tag_columns(conn)
        if not dry_run:
            backup_ai_tags_once(conn)

        rows = fetch_recipes(conn, limit=limit, force=force)
        total = len(rows)
        if total == 0:
            logger.info("没有需要打标的菜谱（可能已全部打过标签）")
            return

        # 过滤已打标（force 模式除外）
        pending: list[sqlite3.Row] = []
        skipped = 0
        for row in rows:
            if (not force) and (
                not is_ai_tags_empty(row["ai_tags"] if "ai_tags" in row.keys() else None)
            ):
                skipped += 1
                continue
            pending.append(row)

        mode = "force" if force else "normal"
        logger.info(
            "待处理: %d 条（跳过 %d，workers=%d，mode=%s）",
            len(pending),
            skipped,
            workers,
            mode,
        )

        ok = 0
        failed = 0
        processed_ids: list[str] = []
        write_lock = threading.Lock()
        counter_lock = threading.Lock()
        done = 0

        def _make_client() -> OpenAI:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            base_url = os.getenv("OPENAI_BASE_URL", "").strip()
            return OpenAI(api_key=api_key, base_url=base_url)

        if workers <= 1:
            client = _make_client()
            for idx, row in enumerate(pending, start=1):
                recipe_id = row["id"]
                title = (row["title"] or "").strip() or recipe_id
                logger.info("Processing %d/%d: %s", idx, len(pending), title)
                rid, _, summary, err = _tag_one_recipe(
                    row, client, model, db_path, dry_run, write_lock
                )
                if err:
                    failed += 1
                    logger.error("  失败 id=%s title=%s err=%s", rid, title, err)
                else:
                    ok += 1
                    processed_ids.append(rid)
                    if dry_run:
                        logger.info("  [dry-run] 完成")
                    else:
                        logger.info("  完成: %s", summary)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {}
                for row in pending:
                    client = _make_client()
                    fut = pool.submit(
                        _tag_one_recipe,
                        row,
                        client,
                        model,
                        db_path,
                        dry_run,
                        write_lock,
                    )
                    futures[fut] = row

                for fut in as_completed(futures):
                    row = futures[fut]
                    recipe_id = row["id"]
                    title = (row["title"] or "").strip() or recipe_id
                    rid, _, summary, err = fut.result()
                    with counter_lock:
                        done += 1
                        cur = done
                    if err:
                        failed += 1
                        logger.error(
                            "Processing %d/%d 失败 id=%s title=%s err=%s",
                            cur,
                            len(pending),
                            rid,
                            title,
                            err,
                        )
                    else:
                        ok += 1
                        processed_ids.append(rid)
                        logger.info(
                            "Processing %d/%d: %s -> %s",
                            cur,
                            len(pending),
                            title[:40],
                            summary,
                        )

        logger.info(
            "结束: 成功=%d 跳过=%d 失败=%d 合计=%d",
            ok,
            skipped,
            failed,
            total,
        )

        if force and processed_ids and (not dry_run):
            print_comparison_report(conn, processed_ids)
    finally:
        conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 SQLite 菜谱批量生成 AI 标签")
    parser.add_argument(
        "--db",
        type=str,
        default="",
        help="SQLite 路径（默认使用脚本内 DEFAULT_DB_PATH）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多处理 N 条（0 表示不限制；配合 --force 时优先重跑已备份旧标签的前 N 条）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="强制重跑：忽略已有 ai_tags，覆盖写入（旧值先备份到 ai_tags_old）",
    )
    parser.add_argument(
        "--prepare-round3",
        action="store_true",
        default=False,
        help="第三轮对比前准备：把当前 ai_tags 快照到 ai_tags_v2，再清空样本 ai_tags",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="并发 worker 数（建议 6~10，配合 qwen-turbo 可显著提速）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只调用 LLM 打印结果，不写库",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="调试日志")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    # 加载 .env：优先 backend/.env，再项目根目录 .env
    backend_root = Path(__file__).resolve().parents[1]
    project_root = backend_root.parent
    load_dotenv(backend_root / ".env")
    load_dotenv(project_root / ".env")

    args = parse_args(argv)
    setup_logging(args.verbose)

    # 手动配置入口：未传 --db 时使用此处路径
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    if not db_path.is_absolute():
        db_path = (backend_root / db_path).resolve()

    limit = args.limit if args.limit and args.limit > 0 else None

    if args.prepare_round3:
        conn = connect_db(db_path)
        try:
            ensure_tag_columns(conn)
            snapshot_ai_tags_v2(conn)
            clear_ai_tags_for_sample(conn, limit=limit or 50)
        finally:
            conn.close()
        if not args.force:
            logger.info("已完成第三轮准备。请继续执行: python -m pipeline.tagger --limit 50 --force")
            return

    process_recipes(
        db_path=db_path,
        limit=limit,
        dry_run=args.dry_run,
        force=args.force,
        workers=max(1, args.workers),
    )


if __name__ == "__main__":
    main()
