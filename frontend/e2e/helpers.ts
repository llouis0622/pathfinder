import { expect, type Page } from '@playwright/test'

export const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin-demo-1234'

/** 장소 검색창에 입력하고 첫 후보를 고른다. */
export async function pickPlace(page: Page, field: '출발지' | '도착지', query: string, item: RegExp) {
  await page.getByRole('combobox', { name: field }).fill(query)
  await page.getByRole('option', { name: item }).first().click()
}

export async function skipOnboarding(page: Page) {
  await page.addInitScript(() => { try { localStorage.setItem('pf.onboarded', 'true') } catch { /* noop */ } })
}

/** 샘플 격자(서면역 → 전포역)로 검색해 결과 행이 뜰 때까지 기다린다. */
export async function searchSample(page: Page) {
  await pickPlace(page, '출발지', '서면', /서면역\(1호선\)/)
  await pickPlace(page, '도착지', '전포', /^전포역/)
  await page.getByRole('button', { name: '길찾기' }).click()
  await expect(page.locator('.row').first()).toBeVisible({ timeout: 30_000 })
}

export async function adminLogin(page: Page) {
  await page.goto('/admin')
  await page.getByLabel('관리자 비밀번호').fill(ADMIN_PASSWORD)
  await page.getByRole('button', { name: '로그인' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('대시보드')
}
