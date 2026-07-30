import { expect, test } from '@playwright/test'

/**
 * 未登录访问需登录页：应跳到登录并带 redirect。
 * 注册/登录页互跳。
 */
test.describe('鉴权入口', () => {
  test('访问收藏页会被重定向到登录', async ({ page }) => {
    await page.goto('/favorites')
    await expect(page).toHaveURL(/\/login/)
    expect(page.url()).toMatch(/redirect=/)
    await expect(page.getByTestId('login-page')).toBeVisible()
    await expect(page.getByTestId('login-username')).toBeVisible()
    await expect(page.getByTestId('login-password')).toBeVisible()
    await expect(page.getByTestId('login-submit')).toBeVisible()
  })

  test('登录页可跳转到注册页，再回到登录', async ({ page }) => {
    await page.goto('/login')
    await page.getByTestId('login-to-register').click()
    await expect(page.getByTestId('register-page')).toBeVisible()
    await page.getByTestId('register-to-login').click()
    await expect(page.getByTestId('login-page')).toBeVisible()
  })

  test('空登录提交显示错误提示', async ({ page }) => {
    await page.goto('/login')
    await page.getByTestId('login-submit').click()
    await expect(page.getByTestId('login-error')).toContainText('请输入用户名和密码')
  })
})
