"""
抓取 X (Twitter) 用户 Super Follows / 时间线内容（完整版）

功能:
  1. 深度滚动时间线，尽可能多收集帖子 ID
  2. 逐条打开详情页，点击「显示更多」并抓取长文/Article 全文
  3. 输出 posts/{id}.md、汇总.md、汇总2.md（RAG 蒸馏用单文档）

用法:
  python scrape_x_superfollows.py --mode cdp --max-scrolls 150 --fetch-detail
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

TARGET_USER = "aleabitoreddit"
TARGET_URL = f"https://x.com/{TARGET_USER}/superfollows"
FALLBACK_URL = f"https://x.com/{TARGET_USER}"
STATUS_URL = f"https://x.com/{TARGET_USER}/status/{{tweet_id}}"

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output" / TARGET_USER
POSTS_DIR = OUTPUT_DIR / "posts"
STORAGE_STATE = SCRIPT_DIR / ".x_auth_state.json"
CDP_URL = "http://127.0.0.1:9222"


@dataclass
class PostItem:
    tweet_id: str
    url: str
    author: str
    created_at: str
    text: str
    is_subscriber_only: bool = False
    media_urls: list[str] = field(default_factory=list)
    scraped_at: str = ""
    is_article: bool = False
    char_count: int = 0


def setup_logging() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(OUTPUT_DIR / "scrape.log", encoding="utf-8", mode="a"),
        ],
    )


def sanitize_filename(tweet_id: str) -> str:
    return re.sub(r"[^\w\-]", "_", tweet_id)


def post_to_markdown(item: PostItem) -> str:
    type_label = "长文/Article" if item.is_article else "推文"
    lines = [
        f"# @{TARGET_USER} 发言存档",
        "",
        f"- **帖子 ID**: {item.tweet_id}",
        f"- **类型**: {type_label}",
        f"- **作者**: {item.author or TARGET_USER}",
        f"- **发布时间**: {item.created_at or '未知'}",
        f"- **原文链接**: {item.url}",
        f"- **是否订阅专享**: {'是' if item.is_subscriber_only else '否'}",
        f"- **字符数**: {item.char_count}",
        f"- **抓取时间**: {item.scraped_at}",
        "",
        "## 正文内容（完整）",
        "",
        item.text or "（无文本内容）",
        "",
    ]
    if item.media_urls:
        lines.extend(["## 图片/媒体链接", ""])
        lines.extend(f"- {u}" for u in item.media_urls)
        lines.append("")
    return "\n".join(lines)


def save_post(item: PostItem) -> Path:
    path = POSTS_DIR / f"{sanitize_filename(item.tweet_id)}.md"
    path.write_text(post_to_markdown(item), encoding="utf-8")
    return path


def save_index(posts: list[PostItem]) -> None:
    payload = {
        "user": TARGET_USER,
        "source_url": TARGET_URL,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "total": len(posts),
        "posts": [asdict(p) for p in posts],
    }
    (OUTPUT_DIR / "index.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_summary_md(posts: list[PostItem]) -> None:
    lines = [
        f"# @{TARGET_USER} 内容抓取汇总",
        "",
        f"- **来源页面**: {TARGET_URL}",
        f"- **抓取时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"- **帖子总数**: {len(posts)}",
        "",
        "## 目录",
        "",
    ]
    for i, p in enumerate(sorted(posts, key=lambda x: x.created_at or "", reverse=True), 1):
        preview = (p.text or "").replace("\n", " ")[:100]
        sub = "（订阅专享）" if p.is_subscriber_only else ""
        art = "（长文）" if p.is_article else ""
        fname = sanitize_filename(p.tweet_id)
        lines.append(
            f"{i}. [{p.created_at or p.tweet_id}](posts/{fname}.md) {sub}{art} "
            f"[{p.char_count}字] — {preview}…"
        )
    lines.append("")
    (OUTPUT_DIR / "汇总.md").write_text("\n".join(lines), encoding="utf-8")


def save_summary2_md(posts: list[PostItem]) -> None:
    """RAG/蒸馏用：全部完整正文合并为单文档。"""
    sorted_posts = sorted(posts, key=lambda x: x.created_at or "", reverse=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# @{TARGET_USER} 全文汇总（RAG / 蒸馏专用）",
        "",
        "> 本文档由爬虫自动合并生成，包含订阅页可访问的全部帖子完整正文。",
        "",
        f"- **来源**: {TARGET_URL}",
        f"- **生成时间**: {now}",
        f"- **帖子总数**: {len(sorted_posts)}",
        f"- **总字符数**: {sum(p.char_count for p in sorted_posts):,}",
        "",
        "## 使用说明",
        "",
        "- 每条帖子以 `---` 分隔，含元数据块 + 正文块",
        "- 可直接用于 RAG 分块、摘要蒸馏或知识库入库",
        "- 单帖详情见 `posts/` 目录下对应 md 文件",
        "",
        "---",
        "",
    ]
    for i, p in enumerate(sorted_posts, 1):
        sub = "是" if p.is_subscriber_only else "否"
        art = "长文/Article" if p.is_article else "推文"
        lines.extend([
            f"## 帖子 {i:03d} | {p.created_at or p.tweet_id}",
            "",
            f"- **帖子 ID**: `{p.tweet_id}`",
            f"- **类型**: {art}",
            f"- **作者**: {p.author or TARGET_USER}",
            f"- **发布时间**: {p.created_at or '未知'}",
            f"- **订阅专享**: {sub}",
            f"- **字符数**: {p.char_count}",
            f"- **链接**: {p.url}",
            "",
            "### 正文",
            "",
            p.text or "（无文本内容）",
            "",
        ])
        if p.media_urls:
            lines.append("### 媒体链接")
            lines.append("")
            lines.extend(f"- {u}" for u in p.media_urls)
            lines.append("")
        lines.extend(["---", ""])
    (OUTPUT_DIR / "汇总2.md").write_text("\n".join(lines), encoding="utf-8")


def extract_posts_from_timeline(page) -> list[PostItem]:
    raw_items = page.evaluate(
        """
        () => {
            const articles = document.querySelectorAll('article[data-testid="tweet"]');
            const results = [];
            for (const article of articles) {
                const linkEl = article.querySelector('a[href*="/status/"]');
                if (!linkEl) continue;
                const href = linkEl.getAttribute('href') || '';
                const idMatch = href.match(/\\/status\\/(\\d+)/);
                const tweetId = idMatch ? idMatch[1] : href;
                const textEl = article.querySelector('[data-testid="tweetText"]');
                const text = textEl ? textEl.innerText : '';
                const timeEl = article.querySelector('time');
                const createdAt = timeEl
                    ? (timeEl.getAttribute('datetime') || timeEl.innerText || '')
                    : '';
                const userEl = article.querySelector('[data-testid="User-Name"]');
                const author = userEl ? userEl.innerText.split('\\n')[0] : '';
                const inner = article.innerText || '';
                const subBadge = article.querySelector('[data-testid="superfollower"]')
                    || inner.includes('Subscriber')
                    || inner.includes('订阅');
                const media = [];
                for (const img of article.querySelectorAll('img[src*="pbs.twimg.com"]')) {
                    const src = img.getAttribute('src');
                    if (src && !src.includes('profile_images') && !src.includes('emoji')) {
                        media.push(src);
                    }
                }
                results.push({
                    tweet_id: tweetId,
                    url: href.startsWith('http') ? href : ('https://x.com' + href),
                    author, created_at: createdAt, text,
                    is_subscriber_only: !!subBadge,
                    media_urls: [...new Set(media)],
                });
            }
            return results;
        }
        """
    )
    scraped_at = datetime.now(timezone.utc).isoformat()
    return [
        PostItem(
            tweet_id=str(r.get("tweet_id", "")),
            url=r.get("url", ""),
            author=r.get("author", TARGET_USER),
            created_at=r.get("created_at", ""),
            text=r.get("text", ""),
            is_subscriber_only=bool(r.get("is_subscriber_only")),
            media_urls=list(r.get("media_urls") or []),
            scraped_at=scraped_at,
            char_count=len(r.get("text", "") or ""),
        )
        for r in raw_items
        if r.get("tweet_id")
    ]


def scroll_and_collect_ids(page, max_scrolls: int, pause_sec: float, stale_limit: int) -> dict[str, PostItem]:
    seen: dict[str, PostItem] = {}
    stale_rounds = 0
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(1500)

    for i in range(max_scrolls):
        batch = extract_posts_from_timeline(page)
        before = len(seen)
        for item in batch:
            if item.tweet_id not in seen:
                seen[item.tweet_id] = item
        added = len(seen) - before
        logging.info("滚动 %s/%s，新增 %s，累计 %s 条 ID", i + 1, max_scrolls, added, len(seen))

        if added == 0:
            stale_rounds += 1
            if stale_rounds >= stale_limit:
                logging.info("连续 %s 轮无新帖，停止滚动", stale_limit)
                break
        else:
            stale_rounds = 0

        page.evaluate("window.scrollBy(0, Math.max(window.innerHeight * 1.5, 800))")
        page.wait_for_timeout(int(pause_sec * 1000))

    return seen


def expand_all_show_more(page, max_clicks: int = 15) -> None:
    for _ in range(max_clicks):
        clicked = False
        for selector in (
            '[data-testid="tweet-text-show-more-link"]',
            'button:has-text("Show more")',
            'button:has-text("显示更多")',
            'span:has-text("Show more")',
            'span:has-text("显示更多")',
        ):
            try:
                loc = page.locator(selector).first
                if loc.count() and loc.is_visible(timeout=400):
                    loc.click(timeout=2000)
                    page.wait_for_timeout(400)
                    clicked = True
            except Exception:
                continue
        if not clicked:
            break


def fetch_full_post(page, stub: PostItem, detail_pause: float) -> PostItem:
    url = STATUS_URL.format(tweet_id=stub.tweet_id)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(int(detail_pause * 1000))
        expand_all_show_more(page)
        page.wait_for_timeout(500)

        detail = page.evaluate(
            """
            () => {
                const articles = document.querySelectorAll('article[data-testid="tweet"]');
                const main = articles.length ? articles[0] : null;
                let tweetTexts = [];
                if (main) {
                    tweetTexts = [...main.querySelectorAll('[data-testid="tweetText"]')]
                        .map(el => el.innerText.trim())
                        .filter(Boolean);
                }
                const articleSelectors = [
                    '[data-testid="twitterArticleReadBody"]',
                    '[data-testid="article-cover-container"] + div',
                    'div[data-testid="tweetText"]',
                ];
                let articleText = '';
                for (const sel of articleSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText.trim().length > articleText.length) {
                        articleText = el.innerText.trim();
                    }
                }
                const articleReader = document.querySelector('[data-testid="twitterArticleRichTextView"]');
                if (articleReader && articleReader.innerText.trim().length > articleText.length) {
                    articleText = articleReader.innerText.trim();
                }
                const timeEl = main ? main.querySelector('time') : document.querySelector('time');
                const createdAt = timeEl
                    ? (timeEl.getAttribute('datetime') || timeEl.innerText || '')
                    : '';
                const userEl = main ? main.querySelector('[data-testid="User-Name"]') : null;
                const author = userEl ? userEl.innerText.split('\\n')[0] : '';
                const inner = main ? (main.innerText || '') : '';
                const isSub = inner.includes('Subscriber') || inner.includes('订阅')
                    || !!document.querySelector('[data-testid="superfollower"]');
                const media = [];
                const scope = main || document;
                for (const img of scope.querySelectorAll('img[src*="pbs.twimg.com"]')) {
                    const src = img.getAttribute('src');
                    if (src && !src.includes('profile_images') && !src.includes('emoji')) {
                        media.push(src.replace('&name=small', '&name=large')
                                     .replace('&name=360x360', '&name=large'));
                    }
                }
                let fullText = tweetTexts.join('\\n\\n');
                if (articleText.length > fullText.length) {
                    fullText = articleText;
                }
                const isArticle = articleText.length > 0 && articleText.length >= fullText.length * 0.8;
                return {
                    text: fullText,
                    created_at: createdAt,
                    author,
                    is_subscriber_only: isSub,
                    media_urls: [...new Set(media)],
                    is_article: isArticle,
                };
            }
            """
        )
        text = detail.get("text") or stub.text
        scraped_at = datetime.now(timezone.utc).isoformat()
        return PostItem(
            tweet_id=stub.tweet_id,
            url=stub.url or url,
            author=detail.get("author") or stub.author,
            created_at=detail.get("created_at") or stub.created_at,
            text=text,
            is_subscriber_only=detail.get("is_subscriber_only", stub.is_subscriber_only),
            media_urls=list(detail.get("media_urls") or stub.media_urls),
            scraped_at=scraped_at,
            is_article=bool(detail.get("is_article")),
            char_count=len(text),
        )
    except Exception as exc:
        logging.warning("详情页抓取失败 %s: %s", stub.tweet_id, exc)
        stub.scraped_at = datetime.now(timezone.utc).isoformat()
        stub.char_count = len(stub.text)
        return stub


def fetch_all_details(page, stubs: dict[str, PostItem], detail_pause: float) -> list[PostItem]:
    items = sorted(stubs.values(), key=lambda x: x.created_at or "", reverse=True)
    total = len(items)
    full_posts: list[PostItem] = []
    for i, stub in enumerate(items, 1):
        logging.info("抓取详情 %s/%s: %s", i, total, stub.tweet_id)
        full_posts.append(fetch_full_post(page, stub, detail_pause))
        if i % 20 == 0:
            logging.info("详情进度 %s/%s", i, total)
    return full_posts


def navigate_target(page, url: str) -> None:
    logging.info("打开页面: %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(3000)
    if page.locator('text="Something went wrong"').count() > 0:
        logging.warning("页面异常，尝试 %s", FALLBACK_URL)
        page.goto(FALLBACK_URL, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(3000)


def run_pipeline(
    mode: str,
    max_scrolls: int,
    pause_sec: float,
    stale_limit: int,
    fetch_detail: bool,
    detail_pause: float,
    cdp_url: str,
    headless: bool,
) -> list[PostItem]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        if mode == "cdp":
            logging.info("连接 CDP: %s", cdp_url)
            browser = p.chromium.connect_over_cdp(cdp_url)
            if not browser.contexts:
                raise RuntimeError("未找到浏览器上下文，请确认 Edge/Chrome 调试端口已开启")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
            if TARGET_USER not in page.url or "superfollows" not in page.url:
                navigate_target(page, TARGET_URL)
            else:
                logging.info("使用当前页面: %s", page.url)
        else:
            browser = p.chromium.launch(headless=headless)
            if STORAGE_STATE.exists():
                context = browser.new_context(storage_state=str(STORAGE_STATE))
            else:
                context = browser.new_context()
                login_page = context.new_page()
                login_page.goto("https://x.com/login", wait_until="domcontentloaded")
                input("登录完成后按 Enter 继续...")
                context.storage_state(path=str(STORAGE_STATE))
            page = context.new_page()
            navigate_target(page, TARGET_URL)

        logging.info("阶段1: 深度滚动收集帖子 ID（max_scrolls=%s）", max_scrolls)
        stubs = scroll_and_collect_ids(page, max_scrolls, pause_sec, stale_limit)
        logging.info("阶段1 完成，共 %s 条 ID", len(stubs))

        if fetch_detail:
            logging.info("阶段2: 逐条打开详情页抓取完整正文")
            posts = fetch_all_details(page, stubs, detail_pause)
        else:
            posts = list(stubs.values())

        if mode == "login":
            context.storage_state(path=str(STORAGE_STATE))
        browser.close()
        return posts


def persist_posts(posts: list[PostItem]) -> None:
    for item in posts:
        save_post(item)
    save_index(posts)
    save_summary_md(posts)
    save_summary2_md(posts)
    logging.info("已写入 posts/ (%s 个)、汇总.md、汇总2.md、index.json", len(posts))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取 X Super Follows 完整内容")
    parser.add_argument("--mode", choices=["cdp", "login"], default="cdp")
    parser.add_argument("--max-scrolls", type=int, default=150, help="最大滚动次数")
    parser.add_argument("--pause", type=float, default=2.5, help="滚动间隔秒")
    parser.add_argument("--stale-limit", type=int, default=8, help="连续无新帖停止轮数")
    parser.add_argument("--fetch-detail", action="store_true", default=True, help="逐条抓详情全文")
    parser.add_argument("--no-fetch-detail", dest="fetch_detail", action="store_false")
    parser.add_argument("--detail-pause", type=float, default=2.0, help="详情页加载等待秒")
    parser.add_argument("--cdp-url", default=CDP_URL)
    parser.add_argument("--headless", action="store_true")
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()
    logging.info("=== 开始完整抓取 @%s ===", TARGET_USER)
    try:
        posts = run_pipeline(
            mode=args.mode,
            max_scrolls=args.max_scrolls,
            pause_sec=args.pause,
            stale_limit=args.stale_limit,
            fetch_detail=args.fetch_detail,
            detail_pause=args.detail_pause,
            cdp_url=args.cdp_url,
            headless=args.headless,
        )
    except Exception as exc:
        logging.exception("抓取失败: %s", exc)
        raise SystemExit(1) from exc

    if not posts:
        logging.warning("未抓到帖子，请确认已登录且页面可访问")
        raise SystemExit(2)

    persist_posts(posts)
    total_chars = sum(p.char_count for p in posts)
    logging.info("完成: %s 帖, 总字符 %s, 汇总2: %s", len(posts), total_chars, OUTPUT_DIR / "汇总2.md")


if __name__ == "__main__":
    main()
