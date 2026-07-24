/** 桌面购入的卡通食物图标（public/icons/food/001.svg ~ 990.svg） */

const FOOD_ICON_COUNT = 990

/** 已人工识别的关键词 → 图标编号（1-based） */
const KEYWORD_ICON_MAP: Array<{ words: string[]; ids: number[] }> = [
  { words: ['咖啡', '拿铁', '美式', 'espresso', 'latte', 'coffee'], ids: [6, 8, 56, 600, 750] },
  { words: ['茶', '奶茶', '红茶', '绿茶', '花茶'], ids: [56, 61, 62, 750] },
  { words: ['蜂蜜', 'honey'], ids: [7, 55] },
  { words: ['牛奶', '鲜奶', '酸奶', '奶昔'], ids: [57] },
  { words: ['松饼', '煎饼', 'pancake', '华夫'], ids: [58] },
  { words: ['三明治', 'sandwich', '汉堡', 'burger'], ids: [59, 800] },
  { words: ['香肠', '热狗', '肠'], ids: [60] },
  { words: ['曲奇', '饼干', 'cookie', '馒头', '包子'], ids: [650] },
  { words: ['吐司', '面包', 'toast', 'baguette', '法棍'], ids: [700, 850] },
  { words: ['蛋', '鸡蛋', '蒸蛋', '煎蛋'], ids: [900] },
  { words: ['饮', '果汁', '饮料', 'bubble', '柠檬水', '苏打'], ids: [6, 9, 56, 600, 750] },
]

/** 对不上具体图标时，按类别做稳定随机 */
const CATEGORY_WORDS: Array<{ words: string[]; salt: string }> = [
  { words: ['汤', '煲', '粥', '火锅'], salt: 'soup' },
  { words: ['面', '粉', '米线', '意面', '拉面'], salt: 'noodle' },
  { words: ['饭', '盖浇', '炒饭', '盖饭'], salt: 'rice' },
  { words: ['鱼', '虾', '蟹', '海鲜'], salt: 'seafood' },
  { words: ['鸡', '鸭', '肉', '牛', '猪', '羊'], salt: 'meat' },
  { words: ['豆腐', '素', '蔬', '菜'], salt: 'veg' },
  { words: ['甜', '糖', '糕', '饼', '布丁', '冰淇淋'], salt: 'sweet' },
  { words: ['茶', '咖啡', '饮', '奶'], salt: 'drink' },
]

function getSeed(text: string): number {
  let hash = 0
  for (let i = 0; i < text.length; i++) {
    hash = (hash << 5) - hash + text.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

function buildText(
  title?: string | null,
  ingredients?: Array<string | { name?: string }> | null,
): string {
  const parts: string[] = [title || '']
  for (const item of ingredients || []) {
    parts.push(typeof item === 'string' ? item : String(item?.name || ''))
  }
  return parts.join(' ')
}

function pickFromIds(ids: number[], seedText: string): number {
  if (!ids.length) return (getSeed(seedText) % FOOD_ICON_COUNT) + 1
  return ids[getSeed(seedText) % ids.length]
}

/** 返回 1-based 图标编号；优先关键词匹配，否则稳定随机 */
function resolveFoodIconId(
  title?: string | null,
  ingredients?: Array<string | { name?: string }> | null,
): number {
  const text = buildText(title, ingredients)
  const seedText = title || text || 'food'

  for (const rule of KEYWORD_ICON_MAP) {
    if (rule.words.some(w => text.toLowerCase().includes(w.toLowerCase()))) {
      return pickFromIds(rule.ids, seedText)
    }
  }

  for (const cat of CATEGORY_WORDS) {
    if (cat.words.some(w => text.includes(w))) {
      return (getSeed(`${seedText}|${cat.salt}`) % FOOD_ICON_COUNT) + 1
    }
  }

  return (getSeed(seedText) % FOOD_ICON_COUNT) + 1
}

/** 柔和背景色盘，按图标编号轮换，制造差异感 */
const ICON_BG_COLORS = [
  'linear-gradient(145deg, #FFE8D6 0%, #FFD0B0 100%)',
  'linear-gradient(145deg, #FFD6E0 0%, #FFB8C9 100%)',
  'linear-gradient(145deg, #D8F3DC 0%, #B7E4C7 100%)',
  'linear-gradient(145deg, #D6EAF8 0%, #AED6F1 100%)',
  'linear-gradient(145deg, #FFF3CD 0%, #FFE69C 100%)',
  'linear-gradient(145deg, #E8DAEF 0%, #D2B4DE 100%)',
  'linear-gradient(145deg, #FDEBD0 0%, #F5CBA7 100%)',
  'linear-gradient(145deg, #D5F5E3 0%, #ABEBC6 100%)',
  'linear-gradient(145deg, #FADBD8 0%, #F5B7B1 100%)',
  'linear-gradient(145deg, #D4E6F1 0%, #A9CCE3 100%)',
  'linear-gradient(145deg, #FCF3CF 0%, #F9E79F 100%)',
  'linear-gradient(145deg, #E8F8F5 0%, #D1F2EB 100%)',
  'linear-gradient(145deg, #F5EEF8 0%, #E8DAEF 100%)',
  'linear-gradient(145deg, #FEF5E7 0%, #FDEBD0 100%)',
  'linear-gradient(145deg, #EBF5FB 0%, #D4E6F1 100%)',
  'linear-gradient(145deg, #EAFAF1 0%, #D5F5E3 100%)',
]

export function getRecipeFoodIcon(
  title?: string | null,
  ingredients?: Array<string | { name?: string }> | null,
): { id: number; src: string; bg: string } {
  const id = resolveFoodIconId(title, ingredients)
  return {
    id,
    src: `/icons/food/${String(id).padStart(3, '0')}.svg`,
    bg: ICON_BG_COLORS[(id - 1) % ICON_BG_COLORS.length],
  }
}
