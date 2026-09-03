import { expect, test } from '@playwright/test'
import { pickPlace, searchSample, skipOnboarding } from './helpers'

test.describe('길찾기', () => {
  test.beforeEach(async ({ page }) => { await skipOnboarding(page) })

  test('검색 → 추천 3개 → 상세 → 공유 링크로 다시 열기', async ({ page, context, browserName }) => {
    await page.goto('/')
    await searchSample(page)
    await expect(page.locator('.row')).toHaveCount(3)
    await expect(page.locator('.sr-only[aria-live]')).toContainText('경로 3개')
    // 상세
    await page.locator('.row').first().click()
    await expect(page.getByRole('button', { name: '경로 목록으로' })).toBeVisible()
    await expect(page.getByRole('button', { name: '경로 읽어주기' })).toBeVisible()
    await expect(page.getByRole('button', { name: /제보/ }).first()).toBeVisible()
    // 공유 링크
    if (browserName === 'chromium') await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await page.getByRole('button', { name: '경로 공유' }).first().click()
    const url = await page.evaluate(() => navigator.clipboard.readText().catch(() => ''))
    expect(url).toMatch(/\/r\/[0-9a-f-]{36}$/)
    const shared = await context.newPage()
    await shared.goto(url)
    await expect(shared.locator('.row')).toHaveCount(3)
    await expect(shared.locator('.results__tag', { hasText: '공유됨' })).toBeVisible()
    await expect(shared.getByRole('combobox', { name: '출발지' })).toHaveValue(/서면역/)
  })

  test('격자 밖 목적지는 결과 없음 안내와 대안을 보여 준다', async ({ page }) => {
    await page.goto('/')
    await pickPlace(page, '출발지', '서면', /서면역\(1호선\)/)
    await pickPlace(page, '도착지', '하단', /^하단역/)
    await page.getByRole('button', { name: '길찾기' }).click()
    await expect(page.locator('.noroute')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByRole('button', { name: '출발·도착 바꿔서 찾기' })).toBeVisible()
    await page.getByRole('button', { name: '고령자 기준으로 보기' }).click()
    await expect(page.getByRole('radio', { name: '고령자' })).toHaveAttribute('aria-checked', 'true')
    await expect(page.locator('.noroute')).toBeVisible({ timeout: 30_000 })
  })

  test('접근성 설정이 <html> 클래스와 저장소에 반영된다', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: '접근성 설정' }).click()
    await page.getByLabel('큰 글씨').check()
    await page.getByLabel('고대비').check()
    await expect(page.locator('html')).toHaveClass(/a11y-large/)
    await expect(page.locator('html')).toHaveClass(/a11y-contrast/)
    await page.reload()
    await expect(page.locator('html')).toHaveClass(/a11y-large/)
  })

  test('즐겨찾기·최근 검색이 게스트 브라우저에 남는다', async ({ page }) => {
    await page.goto('/')
    await pickPlace(page, '출발지', '서면', /서면역\(1호선\)/)
    await pickPlace(page, '도착지', '전포', /^전포역/)
    await page.getByRole('button', { name: '☆ 도착지 저장' }).click()
    await page.getByRole('button', { name: '병원', exact: true }).click()
    await expect(page.locator('.quick__chip', { hasText: '병원' })).toBeVisible()
    await page.getByRole('button', { name: '길찾기' }).click()
    await expect(page.locator('.row').first()).toBeVisible({ timeout: 30_000 })
    const recent = await page.evaluate(() => JSON.parse(localStorage.getItem('pf.recent') || '[]'))
    expect(recent).toHaveLength(1)
  })
})
