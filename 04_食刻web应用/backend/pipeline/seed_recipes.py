# -*- coding: utf-8 -*-
"""种子食谱数据生成。"""

from __future__ import annotations

from uuid import uuid4

# 基础食谱模板
BASE_RECIPES = [
    {
        "title": "番茄鸡蛋面",
        "description": "经典家常面食，酸甜开胃，制作简单",
        "cuisine": "家常菜",
        "difficulty": "简单",
        "cook_minutes": 15,
        "servings": 2,
        "mood_tags": ["疲惫", "想治愈"],
        "taste_tags": ["酸甜", "咸鲜"],
        "health_tags": [],
        "weather_tags": ["雨天适宜"],
        "ingredients": [
            {"name": "面条", "amount": "200", "unit": "克"},
            {"name": "鸡蛋", "amount": "2", "unit": "个"},
            {"name": "番茄", "amount": "2", "unit": "个"},
            {"name": "葱花", "amount": "适量", "unit": ""},
        ],
        "steps": [
            {"order": 1, "text": "番茄切块，鸡蛋打散"},
            {"order": 2, "text": "热锅炒蛋盛出，再炒番茄出汁"},
            {"order": 3, "text": "加水煮开，下面条煮熟"},
            {"order": 4, "text": "倒入炒蛋，加盐调味，撒葱花"},
        ],
        "nutrition": {"calories": 450, "protein": 18},
        "source_site": "seed",
    },
    {
        "title": "清蒸鲈鱼",
        "description": "鲜嫩清淡的粤式蒸鱼",
        "cuisine": "粤菜",
        "difficulty": "中等",
        "cook_minutes": 25,
        "servings": 3,
        "mood_tags": ["想治愈", "开心"],
        "taste_tags": ["清淡", "咸鲜"],
        "health_tags": ["减脂", "高蛋白"],
        "weather_tags": ["夏季"],
        "ingredients": [
            {"name": "鲈鱼", "amount": "1", "unit": "条"},
            {"name": "姜丝", "amount": "适量", "unit": ""},
            {"name": "蒸鱼豉油", "amount": "2", "unit": "勺"},
            {"name": "料酒", "amount": "1", "unit": "勺"},
        ],
        "steps": [
            {"order": 1, "text": "鲈鱼处理干净，两面划刀"},
            {"order": 2, "text": "鱼身抹料酒，铺姜丝"},
            {"order": 3, "text": "水开后大火蒸8-10分钟"},
            {"order": 4, "text": "淋热油和蒸鱼豉油"},
        ],
        "nutrition": {"calories": 280, "protein": 35},
        "source_site": "seed",
    },
    {
        "title": "麻婆豆腐",
        "description": "川菜经典，麻辣鲜香",
        "cuisine": "川菜",
        "difficulty": "简单",
        "cook_minutes": 20,
        "servings": 2,
        "mood_tags": ["开心", "想尝鲜"],
        "taste_tags": ["麻辣", "咸鲜"],
        "health_tags": ["素食"],
        "weather_tags": ["冬季"],
        "ingredients": [
            {"name": "嫩豆腐", "amount": "1", "unit": "块"},
            {"name": "猪肉末", "amount": "100", "unit": "克"},
            {"name": "豆瓣酱", "amount": "1", "unit": "勺"},
            {"name": "花椒粉", "amount": "适量", "unit": ""},
        ],
        "steps": [
            {"order": 1, "text": "豆腐切小块，焯水备用"},
            {"order": 2, "text": "炒香肉末和豆瓣酱"},
            {"order": 3, "text": "加水煮开，下豆腐小火焖5分钟"},
            {"order": 4, "text": "勾芡，撒花椒粉和葱花"},
        ],
        "nutrition": {"calories": 320, "protein": 20},
        "source_site": "seed",
    },
    {
        "title": "蒜蓉西兰花",
        "description": "低脂高纤维素菜",
        "cuisine": "家常菜",
        "difficulty": "简单",
        "cook_minutes": 10,
        "servings": 2,
        "mood_tags": ["疲惫"],
        "taste_tags": ["清淡", "咸鲜"],
        "health_tags": ["减脂", "控糖", "素食"],
        "weather_tags": ["夏季"],
        "ingredients": [
            {"name": "西兰花", "amount": "1", "unit": "颗"},
            {"name": "大蒜", "amount": "5", "unit": "瓣"},
            {"name": "盐", "amount": "适量", "unit": ""},
        ],
        "steps": [
            {"order": 1, "text": "西兰花切小朵焯水"},
            {"order": 2, "text": "蒜末爆香"},
            {"order": 3, "text": "下西兰花翻炒，加盐调味"},
        ],
        "nutrition": {"calories": 80, "protein": 5},
        "source_site": "seed",
    },
    {
        "title": "红烧肉",
        "description": "经典硬菜，肥而不腻",
        "cuisine": "本帮菜",
        "difficulty": "中等",
        "cook_minutes": 60,
        "servings": 4,
        "mood_tags": ["开心", "想治愈"],
        "taste_tags": ["咸鲜", "酸甜"],
        "health_tags": ["增肌"],
        "weather_tags": ["冬季", "雨天适宜"],
        "ingredients": [
            {"name": "五花肉", "amount": "500", "unit": "克"},
            {"name": "冰糖", "amount": "30", "unit": "克"},
            {"name": "生抽", "amount": "2", "unit": "勺"},
            {"name": "老抽", "amount": "1", "unit": "勺"},
            {"name": "料酒", "amount": "2", "unit": "勺"},
        ],
        "steps": [
            {"order": 1, "text": "五花肉切块焯水"},
            {"order": 2, "text": "炒糖色，下肉块翻炒上色"},
            {"order": 3, "text": "加调料和热水，小火炖40分钟"},
            {"order": 4, "text": "大火收汁至浓稠"},
        ],
        "nutrition": {"calories": 520, "protein": 25},
        "source_site": "seed",
    },
    {
        "title": "酸辣土豆丝",
        "description": "爽脆开胃的下饭菜",
        "cuisine": "家常菜",
        "difficulty": "简单",
        "cook_minutes": 15,
        "servings": 2,
        "mood_tags": ["开心", "想尝鲜"],
        "taste_tags": ["酸甜", "麻辣"],
        "health_tags": ["素食", "减脂"],
        "weather_tags": ["夏季"],
        "ingredients": [
            {"name": "土豆", "amount": "2", "unit": "个"},
            {"name": "干辣椒", "amount": "3", "unit": "个"},
            {"name": "醋", "amount": "2", "unit": "勺"},
        ],
        "steps": [
            {"order": 1, "text": "土豆切丝泡水去淀粉"},
            {"order": 2, "text": "热油爆香干辣椒"},
            {"order": 3, "text": "大火快炒土豆丝"},
            {"order": 4, "text": "淋醋炒匀出锅"},
        ],
        "nutrition": {"calories": 150, "protein": 3},
        "source_site": "seed",
    },
    {
        "title": "冬瓜排骨汤",
        "description": "清热解暑的养生汤品",
        "cuisine": "家常菜",
        "difficulty": "简单",
        "cook_minutes": 45,
        "servings": 3,
        "mood_tags": ["疲惫", "想治愈"],
        "taste_tags": ["清淡", "咸鲜"],
        "health_tags": ["减脂", "控糖"],
        "weather_tags": ["夏季", "雨天适宜"],
        "ingredients": [
            {"name": "排骨", "amount": "300", "unit": "克"},
            {"name": "冬瓜", "amount": "400", "unit": "克"},
            {"name": "姜片", "amount": "3", "unit": "片"},
        ],
        "steps": [
            {"order": 1, "text": "排骨焯水洗净"},
            {"order": 2, "text": "砂锅加水放排骨和姜，大火烧开转小火炖30分钟"},
            {"order": 3, "text": "加冬瓜块炖15分钟"},
            {"order": 4, "text": "加盐调味即可"},
        ],
        "nutrition": {"calories": 220, "protein": 22},
        "source_site": "seed",
    },
    {
        "title": "宫保鸡丁",
        "description": "川菜代表，花生脆香",
        "cuisine": "川菜",
        "difficulty": "中等",
        "cook_minutes": 25,
        "servings": 2,
        "mood_tags": ["开心"],
        "taste_tags": ["麻辣", "酸甜", "咸鲜"],
        "health_tags": ["高蛋白", "增肌"],
        "weather_tags": [],
        "ingredients": [
            {"name": "鸡胸肉", "amount": "300", "unit": "克"},
            {"name": "花生米", "amount": "50", "unit": "克"},
            {"name": "干辣椒", "amount": "5", "unit": "个"},
            {"name": "黄瓜", "amount": "1", "unit": "根"},
        ],
        "steps": [
            {"order": 1, "text": "鸡肉切丁腌制，黄瓜切丁"},
            {"order": 2, "text": "调宫保汁：酱油、醋、糖、淀粉"},
            {"order": 3, "text": "炒花生米盛出，爆香干辣椒"},
            {"order": 4, "text": "快炒鸡丁，淋宫保汁，加花生炒匀"},
        ],
        "nutrition": {"calories": 380, "protein": 35},
        "source_site": "seed",
    },
    {
        "title": "蔬菜沙拉",
        "description": "低卡轻食，适合减脂",
        "cuisine": "西餐",
        "difficulty": "简单",
        "cook_minutes": 10,
        "servings": 1,
        "mood_tags": ["疲惫"],
        "taste_tags": ["清淡", "酸甜"],
        "health_tags": ["减脂", "控糖", "素食"],
        "weather_tags": ["夏季"],
        "ingredients": [
            {"name": "生菜", "amount": "100", "unit": "克"},
            {"name": "圣女果", "amount": "8", "unit": "个"},
            {"name": "黄瓜", "amount": "1", "unit": "根"},
            {"name": "橄榄油", "amount": "1", "unit": "勺"},
        ],
        "steps": [
            {"order": 1, "text": "蔬菜洗净沥干"},
            {"order": 2, "text": "切好装盘"},
            {"order": 3, "text": "淋橄榄油和柠檬汁拌匀"},
        ],
        "nutrition": {"calories": 120, "protein": 3},
        "source_site": "seed",
    },
    {
        "title": "皮蛋瘦肉粥",
        "description": "暖胃养胃的广式粥品",
        "cuisine": "粤菜",
        "difficulty": "中等",
        "cook_minutes": 40,
        "servings": 2,
        "mood_tags": ["疲惫", "想治愈"],
        "taste_tags": ["咸鲜"],
        "health_tags": [],
        "weather_tags": ["雨天适宜", "冬季"],
        "ingredients": [
            {"name": "大米", "amount": "100", "unit": "克"},
            {"name": "瘦肉", "amount": "100", "unit": "克"},
            {"name": "皮蛋", "amount": "2", "unit": "个"},
            {"name": "姜丝", "amount": "适量", "unit": ""},
        ],
        "steps": [
            {"order": 1, "text": "大米浸泡30分钟"},
            {"order": 2, "text": "大火煮开转小火熬20分钟"},
            {"order": 3, "text": "加肉丝和皮蛋丁继续熬10分钟"},
            {"order": 4, "text": "加盐调味，撒葱花"},
        ],
        "nutrition": {"calories": 350, "protein": 18},
        "source_site": "seed",
    },
]

# 用于扩展的变体前缀
VARIANT_PREFIXES = ["家常", "简易", "经典", "秘制", "快手", "营养", "低脂", "香辣", "清淡", "暖胃"]
VARIANT_SUFFIXES = ["做法", "升级版", "一人食", "宴客版", "便当版"]

MOODS = ["开心", "疲惫", "想治愈", "想尝鲜"]
TASTES = ["咸鲜", "酸甜", "麻辣", "清淡"]
HEALTH = ["减脂", "增肌", "控糖", "素食", "高蛋白"]
WEATHER = ["雨天适宜", "夏季", "冬季"]
CUISINES = ["家常菜", "川菜", "粤菜", "本帮菜", "湘菜", "鲁菜", "西餐", "日料"]


def generate_seed_recipes(target_count: int = 3000) -> list[dict]:
    """基于模板生成指定数量的食谱数据。"""
    recipes: list[dict] = []
    idx = 0

    # 先加入基础食谱
    for base in BASE_RECIPES:
        if len(recipes) >= target_count:
            break
        r = dict(base)
        r["id"] = str(uuid4())
        recipes.append(r)
        idx += 1

    # 通过变体扩展至目标数量
    while len(recipes) < target_count:
        base = BASE_RECIPES[idx % len(BASE_RECIPES)]
        variant_num = idx // len(BASE_RECIPES)
        prefix = VARIANT_PREFIXES[variant_num % len(VARIANT_PREFIXES)]
        suffix = VARIANT_SUFFIXES[(variant_num // len(VARIANT_PREFIXES)) % len(VARIANT_SUFFIXES)]

        r = dict(base)
        r["id"] = str(uuid4())
        r["title"] = f"{prefix}{base['title']}{suffix}({variant_num + 1})"
        r["mood_tags"] = [MOODS[idx % len(MOODS)]]
        r["taste_tags"] = [TASTES[idx % len(TASTES)]]
        r["health_tags"] = [HEALTH[idx % len(HEALTH)]] if idx % 3 == 0 else base.get("health_tags", [])
        r["weather_tags"] = [WEATHER[idx % len(WEATHER)]] if idx % 2 == 0 else base.get("weather_tags", [])
        r["cuisine"] = CUISINES[idx % len(CUISINES)]
        r["cook_minutes"] = base["cook_minutes"] + (idx % 5) * 5
        r["servings"] = 1 + (idx % 6)
        recipes.append(r)
        idx += 1

    return recipes
