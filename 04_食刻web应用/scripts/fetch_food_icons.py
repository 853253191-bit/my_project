# -*- coding: utf-8 -*-
"""（可选）扩展本地食物图标库的说明脚本。

不要爬取 https://www.iconfont.cn/ ：
- 图标有版权，需登录后加入项目再官方导出
- 未经授权批量抓取违反服务条款

推荐做法：
1. 在 iconfont 创建项目，搜索「食物/食材/美食」，加入购物车后下载 SVG
2. 将导出的 svg 重命名后放入：
   frontend/src/assets/icons/food/
3. 在 frontend/src/utils/recipeFoodIcon.ts 的 RULES 中补关键词映射
4. 更新 frontend/src/assets/icons/food/manifest.json

项目已内置一套本地 SVG UI 图标，卡片通过 RecipeFoodIcon 每个菜谱显示 1 个。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "frontend" / "src" / "assets" / "icons" / "food"


def main() -> None:
    files = sorted(ICON_DIR.glob("*.svg")) if ICON_DIR.exists() else []
    print(f"本地图标目录: {ICON_DIR}")
    print(f"当前 SVG 数量: {len(files)}")
    for f in files:
        print(f"  - {f.name}")
    print("\n请从 iconfont 官方导出后手动放入上述目录，勿使用爬虫。")


if __name__ == "__main__":
    main()
