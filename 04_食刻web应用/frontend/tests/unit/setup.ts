/** Vitest 全局初始化：清空 localStorage，避免 Store 用例互相污染。 */
import { beforeEach } from 'vitest'

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})
