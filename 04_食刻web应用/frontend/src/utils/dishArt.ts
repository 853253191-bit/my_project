/** 根据菜名生成确定性 seed，同一道菜永远同一套图形 */
export function getSeed(title: string): number {
  let hash = 0
  for (let i = 0; i < title.length; i++) {
    hash = (hash << 5) - hash + title.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

/** 菜系 → 渐变色 */
const COLOR_MAP: Record<string, string> = {
  川菜: 'linear-gradient(135deg, #FF6B6B, #EE5A24)',
  粤菜: 'linear-gradient(135deg, #A8E6CF, #55EFC4)',
  湘菜: 'linear-gradient(135deg, #F8A5C2, #F78FB3)',
  西北菜: 'linear-gradient(135deg, #FDCB6E, #E17055)',
  西北: 'linear-gradient(135deg, #FDCB6E, #E17055)',
  日料: 'linear-gradient(135deg, #DFE6E9, #B2BEC3)',
  西餐: 'linear-gradient(135deg, #FAB1A0, #FC5C65)',
  西式: 'linear-gradient(135deg, #FAB1A0, #FC5C65)',
}

const DEFAULT_GRADIENT = 'linear-gradient(135deg, #E8D5B7, #D4A373)'

export function getCuisineGradient(cuisine?: string | null): string {
  const key = (cuisine || '').trim()
  if (!key) return DEFAULT_GRADIENT
  if (COLOR_MAP[key]) return COLOR_MAP[key]
  // 模糊匹配：标题含川/粤等
  for (const name of Object.keys(COLOR_MAP)) {
    if (key.includes(name) || name.includes(key)) return COLOR_MAP[name]
  }
  return DEFAULT_GRADIENT
}

/** 形状组合变体 0~3 */
export function getArtVariant(title: string): 0 | 1 | 2 | 3 {
  return (getSeed(title) % 4) as 0 | 1 | 2 | 3
}
