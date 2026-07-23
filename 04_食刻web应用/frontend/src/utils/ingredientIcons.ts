/** 食材名 → 展示用 Unicode 图标（无额外网络请求） */
const INGREDIENT_ICON_RULES: Array<{ keywords: string[]; icon: string }> = [
  { keywords: ['番茄', '西红柿'], icon: '🍅' },
  { keywords: ['鸡蛋', '蛋黄', '蛋清', '鸭蛋'], icon: '🥚' },
  { keywords: ['牛肉', '牛腩', '牛排', '牛里脊'], icon: '🥩' },
  { keywords: ['猪肉', '五花肉', '排骨', '肋排', '火腿', '培根'], icon: '🥓' },
  { keywords: ['鸡肉', '鸡胸', '鸡翅', '鸡腿', '鸡丁'], icon: '🍗' },
  { keywords: ['鱼', '鲈鱼', '带鱼', '鳕鱼', '三文鱼'], icon: '🐟' },
  { keywords: ['虾', '河虾', '基围虾', '虾仁'], icon: '🦐' },
  { keywords: ['豆腐', '豆皮', '腐竹'], icon: '🫕' },
  { keywords: ['面条', '挂面', '意面', '拉面', '米粉', '河粉'], icon: '🍜' },
  { keywords: ['米饭', '大米', '糯米', '米饭'], icon: '🍚' },
  { keywords: ['西兰花'], icon: '🥦' },
  { keywords: ['白菜', '娃娃菜', '青菜', '生菜', '菠菜', '蔬菜', '时蔬'], icon: '🥬' },
  { keywords: ['玉米'], icon: '🌽' },
  { keywords: ['土豆', '马铃薯'], icon: '🥔' },
  { keywords: ['红薯', '地瓜', '紫薯'], icon: '🍠' },
  { keywords: ['蘑菇', '香菇', '平菇', '金针菇', '杏鲍菇'], icon: '🍄' },
  { keywords: ['洋葱'], icon: '🧅' },
  { keywords: ['大蒜', '蒜末', '蒜蓉', '蒜'], icon: '🧄' },
  { keywords: ['姜', '生姜'], icon: '🫚' },
  { keywords: ['辣椒', '朝天椒', '干辣椒', '小米椒', '花椒'], icon: '🌶️' },
  { keywords: ['花生'], icon: '🥜' },
  { keywords: ['牛奶', '鲜奶', '纯牛奶'], icon: '🥛' },
  { keywords: ['芝士', '奶酪', '马苏里拉'], icon: '🧀' },
  { keywords: ['面包'], icon: '🍞' },
  { keywords: ['蛋糕'], icon: '🧁' },
  { keywords: ['南瓜'], icon: '🎃' },
  { keywords: ['茄子'], icon: '🍆' },
  { keywords: ['黄瓜'], icon: '🥒' },
  { keywords: ['胡萝卜'], icon: '🥕' },
  { keywords: ['苹果', '水果'], icon: '🍎' },
  { keywords: ['香蕉'], icon: '🍌' },
  { keywords: ['柠檬'], icon: '🍋' },
  { keywords: ['橙子', '橘子', '柑橘'], icon: '🍊' },
  { keywords: ['草莓'], icon: '🍓' },
  { keywords: ['葡萄'], icon: '🍇' },
  { keywords: ['西瓜'], icon: '🍉' },
  { keywords: ['牛奶', '酸奶'], icon: '🥛' },
  { keywords: ['银耳', '木耳'], icon: '🍄' },
  { keywords: ['米饭', '饭'], icon: '🍚' },
]

export const DEFAULT_INGREDIENT_ICON = '🍳'

/** 根据单个食材名返回图标 */
export function getIngredientIcon(ingredient: string): string {
  const text = (ingredient || '').trim()
  if (!text) return DEFAULT_INGREDIENT_ICON
  for (const rule of INGREDIENT_ICON_RULES) {
    if (rule.keywords.some(k => text.includes(k))) {
      return rule.icon
    }
  }
  return DEFAULT_INGREDIENT_ICON
}

/**
 * 规范化食材列表：兼容 string[] 或 {name}[]，取前 max 个名称。
 */
export function pickIngredientNames(
  ingredients?: Array<string | { name?: string }> | null,
  max = 3,
): string[] {
  if (!ingredients?.length) return []
  const names: string[] = []
  for (const item of ingredients) {
    const name = typeof item === 'string'
      ? item.trim()
      : String(item?.name || '').trim()
    if (name && !names.includes(name)) {
      names.push(name)
    }
    if (names.length >= max) break
  }
  return names
}
