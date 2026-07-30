/**
 * session Store 单元测试
 * 重点：解析意图写入、标签重建、我的食谱本地收藏。
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useSessionStore } from '@/stores/session'
import type { ParsedIntent, RecommendItem } from '@/api/client'

function sampleItem(id: string, title = '测试菜'): RecommendItem {
  return {
    id,
    title,
    decision_summary: '摘要',
    cuisine_main: '家常',
    spicy_level: 0,
    estimated_time: 15,
  }
}

describe('useSessionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('applyParsedIntent 写入 query/filters 并重建标签', () => {
    const session = useSessionStore()
    const parsed: ParsedIntent = {
      query_text: '番茄炒蛋',
      filters: {
        spicy_level_max: 0,
        cuisine_main: '家常',
        estimated_time_max: 20,
        exclude_allergens: ['花生'],
      },
      form: {
        mood: '想吃热乎的',
        taste: ['咸鲜'],
        spice_level: 0,
        ingredients: ['鸡蛋', '番茄'],
        health_goal: '无',
      },
    } as ParsedIntent

    session.applyParsedIntent(parsed)

    expect(session.queryText).toBe('番茄炒蛋')
    expect(session.filters.cuisine_main).toBe('家常')
    expect(session.filters.exclude_allergens).toEqual(['花生'])
    expect(session.filterForm.mood).toBe('想吃热乎的')
    expect(session.excludedIds).toEqual([])

    const categories = session.recognizedTags.map((t) => t.category)
    expect(categories).toContain('心情')
    expect(categories).toContain('食材')
    expect(categories).toContain('菜系')
    expect(categories).toContain('忌口')
  })

  it('setRecommendations 更新列表与 hasResults', () => {
    const session = useSessionStore()
    expect(session.hasResults).toBe(false)
    session.setRecommendations([sampleItem('r1')], '为你找到 1 道')
    expect(session.hasResults).toBe(true)
    expect(session.recommendations).toHaveLength(1)
    expect(session.recommendMessage).toBe('为你找到 1 道')
  })

  it('我的食谱：添加去重、移除、清空，并写入 localStorage', () => {
    const session = useSessionStore()
    const a = sampleItem('a1', '红烧肉')
    const b = sampleItem('b2', '清蒸鱼')

    expect(session.addToMyRecipes(a)).toBe(true)
    expect(session.addToMyRecipes(a)).toBe(false)
    expect(session.isInMyRecipes('a1')).toBe(true)
    expect(session.hasMyRecipes).toBe(true)

    session.addToMyRecipes(b)
    expect(session.myRecipes).toHaveLength(2)

    session.removeFromMyRecipes('a1')
    expect(session.isInMyRecipes('a1')).toBe(false)
    expect(session.myRecipes).toHaveLength(1)

    const raw = localStorage.getItem('shike_my_recipes')
    expect(raw).toBeTruthy()
    expect(JSON.parse(raw!)).toHaveLength(1)

    session.clearMyRecipes()
    expect(session.myRecipes).toEqual([])
    expect(session.hasMyRecipes).toBe(false)
  })

  it('removeTag 清除对应 form 字段并刷新标签', () => {
    const session = useSessionStore()
    session.applyParsedIntent({
      query_text: '随便',
      filters: {},
      form: { mood: '开心', taste: [], spice_level: 0, ingredients: [] },
    } as ParsedIntent)

    const moodTag = session.recognizedTags.find((t) => t.field === 'mood')
    expect(moodTag).toBeTruthy()
    session.removeTag(moodTag!)
    expect(session.filterForm.mood).toBe('')
    expect(session.recognizedTags.some((t) => t.field === 'mood')).toBe(false)
  })
})
