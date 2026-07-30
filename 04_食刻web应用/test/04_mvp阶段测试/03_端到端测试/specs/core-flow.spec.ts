import { expect, test, type Page } from '@playwright/test'

/**
 * 食刻核心用户流程 — 端到端骨架测试
 *
 * 按真实用户可见结果逐步断言；任一步失败会标明卡在哪一步。
 * 不依赖内部 store / API 响应体断言。
 */

const USER_QUERY = '想吃火锅'

/** 步骤失败时抛出带步骤名的错误，方便报告定位 */
async function step(name: string, fn: () => Promise<void>) {
  try {
    await test.step(name, fn)
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err)
    throw new Error(`卡在步骤「${name}」: ${detail}`)
  }
}

async function expectVisible(page: Page, testId: string, hint: string) {
  const loc = page.getByTestId(testId)
  await expect(loc, hint).toBeVisible()
  return loc
}

test.describe('食刻核心用户流程', () => {
  test('对话推荐 → 看详情 → 关闭 → 重置', async ({ page }) => {
    // ----- 1. 打开首页 -----
    await step('1. 打开首页，看到对话区与精选', async () => {
      const resp = await page.goto('/')
      expect(resp, '首页 HTTP 应成功').not.toBeNull()
      expect(resp!.ok(), `首页 HTTP ${resp!.status()}`).toBeTruthy()

      await expect(page.getByRole('heading', { name: /今天想吃点啥/ })).toBeVisible()
      await expectVisible(page, 'home-hero', '应看到首页 Hero')
      await expectVisible(page, 'chat-section', '应看到对话区')
      await expectVisible(page, 'chat-input', '应看到输入框')
      await expectVisible(page, 'btn-send', '应看到发送按钮')
      await expectVisible(page, 'daily-section', '应看到今日主厨精选')
      await expectVisible(page, 'workflow-bar', '应看到状态机流转条')
      await expect(page.getByTestId('workflow-phase')).toHaveText('idle')
      await expect(page.getByTestId('workflow-phase-label')).toHaveText('待命')
    })

    // ----- 2. 输入需求并发送 -----
    await step('2. 输入需求并发送，看到用户气泡', async () => {
      const input = page.getByTestId('chat-input')
      await input.fill(USER_QUERY)
      await expect(input).toHaveValue(USER_QUERY)
      await page.getByTestId('btn-send').click()

      await expect(
        page.getByTestId('chat-bubble-user').filter({ hasText: USER_QUERY }),
        '发送后应出现用户气泡',
      ).toBeVisible()
    })

    // ----- 3. 等待推荐结果（用户可见） -----
    await step('3. 等待推荐列表出现（解析+检索完成）', async () => {
      // 若状态机已进入 error，立即失败并带上可见错误信息（避免空等 90s）
      const phase = page.getByTestId('workflow-phase')
      await expect
        .poll(async () => {
          const p = (await phase.textContent())?.trim() || ''
          if (p === 'error') {
            const err =
              (await page.locator('.wb-error').first().textContent())?.trim() ||
              '未知错误'
            throw new Error(`推荐流程出错: ${err}`)
          }
          return p
        }, { timeout: 120_000, message: '等待推荐完成或出错' })
        .toMatch(/results|empty/)

      // 无结果也算流程走通到可观测态；本用例要求有推荐卡片
      const results = page.getByTestId('results-section')
      await expect(results, '应出现推荐结果区「为你找到 N 道」').toBeVisible({
        timeout: 15_000,
      })
      await expect(page.getByTestId('results-title')).toContainText(/为你找到\s*\d+\s*道/)

      const cards = page.getByTestId('recommend-card')
      await expect(cards.first(), '至少应有一张推荐卡片').toBeVisible()
      const count = await cards.count()
      expect(count, '推荐卡片数量应 >= 1').toBeGreaterThanOrEqual(1)

      // AI 回复可见（找到 / 猜你想吃）
      await expect(
        page.getByTestId('chat-bubble-ai').last(),
        '应出现 AI 回复气泡',
      ).toBeVisible()
      await expect(page.getByTestId('chat-bubble-ai').last()).toContainText(/找到|合拍|小菜|想吃/)
    })

    // ----- 4. 状态机应进入有推荐 -----
    await step('4. 状态机显示有推荐', async () => {
      await expect(page.getByTestId('workflow-phase')).toHaveText('results')
      await expect(page.getByTestId('workflow-phase-label')).toHaveText('有推荐')
      await expect(page.getByTestId('workflow-bar').getByText('最近流转')).toBeVisible()
      await expect(page.locator('.wb-history-item').first()).toBeVisible()
    })

    // ----- 5. 打开第一道详情 -----
    let firstTitle = ''
    await step('5. 点击第一张卡「查看详情」，弹窗打开', async () => {
      const firstCard = page.getByTestId('recommend-card').first()
      firstTitle = (await firstCard.getByTestId('recommend-card-title').innerText()).trim()
      expect(firstTitle.length, '卡片标题不应为空').toBeGreaterThan(0)

      await firstCard.getByTestId('btn-detail').click()

      await expectVisible(page, 'detail-overlay', '应出现详情遮罩')
      await expectVisible(page, 'detail-modal', '应出现详情弹窗')
      await expect(page.getByTestId('detail-title')).toContainText('食谱详情')
      await expect(page.getByTestId('detail-title')).toContainText(firstTitle)
    })

    // ----- 6. 详情内容对用户可见 -----
    await step('6. 详情中出现可阅读的食谱正文', async () => {
      const content = page.getByTestId('recipe-content')
      await expect(content, '应出现食谱正文（非一直加载）').toBeVisible({
        timeout: 60_000,
      })

      // 失败文案对用户也可见，算流程未走通
      const text = (await content.innerText()).trim()
      expect(text.length, '食谱正文不应为空').toBeGreaterThan(10)
      expect(text, '详情不应显示「生成失败」').not.toContain('生成失败')

      // 加载提示应消失
      await expect(page.getByTestId('detail-loading')).toHaveCount(0)
    })

    // ----- 7. 关闭详情 -----
    await step('7. 关闭详情，回到列表', async () => {
      await page.getByTestId('detail-close').click()
      await expect(page.getByTestId('detail-modal')).toHaveCount(0)
      await expect(page.getByTestId('results-section')).toBeVisible()
      await expect(page.getByTestId('recommend-card').first()).toBeVisible()
    })

    // ----- 8. 重置 -----
    await step('8. 点击重置，回到待命', async () => {
      await page.getByTestId('btn-reset').click()

      await expect(page.getByTestId('chat-history')).toHaveCount(0)
      await expect(page.getByTestId('results-section')).toHaveCount(0)
      await expect(page.getByTestId('chat-input')).toHaveValue('')
      await expect(page.getByTestId('workflow-phase')).toHaveText('idle')
      await expect(page.getByTestId('workflow-phase-label')).toHaveText('待命')
    })
  })
})
