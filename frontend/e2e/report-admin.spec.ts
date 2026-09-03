import { expect, test } from '@playwright/test'
import { adminLogin, searchSample, skipOnboarding } from './helpers'

test.describe('제보 → 관리자 검토 → 데이터 품질·알림', () => {
  test('사용자 제보가 관리자 화면에 보이고 반영/알림 평가가 동작한다', async ({ page }) => {
    await skipOnboarding(page)
    await page.goto('/')
    await searchSample(page)
    await page.locator('.row').first().click()
    await page.getByRole('button', { name: /제보/ }).first().click()
    await page.getByRole('radio', { name: '엘리베이터 고장' }).click()
    const note = `e2e-${Date.now()}`
    await page.getByPlaceholder(/예:/).fill(note)
    await page.getByRole('button', { name: '제보하기' }).click()
    await expect(page.locator('.toast', { hasText: '제보했어요' })).toBeVisible()

    await adminLogin(page)
    await page.getByRole('link', { name: '제보 검토' }).click()
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('제보 검토·오버라이드')
    const row = page.locator('tr', { hasText: note })
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '반영…' }).click()
    await page.getByRole('button', { name: '반영', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('반영했어요')
    await expect(page.locator('h2', { hasText: '활성 오버라이드' })).toBeVisible()
    await expect(page.locator('.adm-card', { hasText: '활성 오버라이드' }).locator('tbody tr').first()).toBeVisible()

    await page.getByRole('link', { name: '데이터 품질' }).click()
    await expect(page.getByText('경사 정보 커버리지')).toBeVisible()
    await expect(page.getByText('보행망 연결성')).toBeVisible()

    await page.getByRole('link', { name: '알림', exact: true }).click()
    await page.getByRole('button', { name: '지금 평가' }).click()
    await expect(page.getByRole('status')).toContainText(/정상|임계/)
  })
})
