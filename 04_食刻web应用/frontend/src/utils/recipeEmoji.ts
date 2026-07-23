/** 根据菜名 / 食材生成展示用 Emoji（最多 2 个） */

const RULES: Array<{ keyword: string; emoji: string }> = [
  { keyword: '番茄', emoji: '🍅' },
  { keyword: '西红柿', emoji: '🍅' },
  { keyword: '蛋', emoji: '🥚' },
  { keyword: '肉', emoji: '🥩' },
  { keyword: '鱼', emoji: '🐟' },
  { keyword: '虾', emoji: '🦐' },
  { keyword: '豆腐', emoji: '🫕' },
  { keyword: '汤', emoji: '🥣' },
  { keyword: '面', emoji: '🍜' },
  { keyword: '饭', emoji: '🍚' },
  { keyword: '菜', emoji: '🥬' },
]

const DEFAULT_EMOJI = '🍳'

/**
 * 根据标题与食材文本匹配 Emoji，最多返回 2 个组合。
 */
export function getEmoji(
  title: string,
  ingredients?: string | string[] | null,
): string {
  const parts: string[] = [title || '']
  if (Array.isArray(ingredients)) {
    parts.push(ingredients.join(' '))
  } else if (ingredients) {
    parts.push(String(ingredients))
  }
  const text = parts.join(' ')

  const matched: string[] = []
  for (const rule of RULES) {
    if (text.includes(rule.keyword) && !matched.includes(rule.emoji)) {
      matched.push(rule.emoji)
      if (matched.length >= 2) break
    }
  }
  return matched.length ? matched.join('') : DEFAULT_EMOJI
}
