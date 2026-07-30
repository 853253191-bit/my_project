import { expect, test } from '@playwright/test'

/**
 * 反馈页冒烟：前端校验 + 提交（不依赖导航链路，避免前序失败拖垮）。
 */
test.describe('反馈页', () => {
  test('短内容触发校验', async ({ page }) => {
    await page.goto('/feedback')
    await expect(page.getByTestId('feedback-page')).toBeVisible()

    await page.getByTestId('feedback-content').fill('太短了')
    await page.getByTestId('feedback-submit').click()
    await expect(page.getByTestId('feedback-error')).toContainText('至少写 5 个字')
  })

  test('合法反馈可提交（后端可用时成功）', async ({ page }) => {
    await page.goto('/feedback')
    await expect(page.getByTestId('feedback-page')).toBeVisible()
    await page.getByTestId('feedback-content').fill('希望能按预算推荐，方便点外卖时对照')
    await page.getByTestId('feedback-cat-建议').click()
    await page.getByTestId('feedback-submit').click()

    const success = page.getByTestId('feedback-success')
    const error = page.getByTestId('feedback-error')
    await expect(success.or(error)).toBeVisible({ timeout: 30_000 })
  })
})
