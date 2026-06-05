const { test, expect } = require('@playwright/test');

const baseURL = process.env.BASE_URL || 'http://127.0.0.1:8000';
const password = process.env.E2E_PASSWORD || 'TestPass123!';

async function login(page, username, role, roleText) {
  await page.goto(`${baseURL}/login/`);
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="username"]').blur();

  const roleSelect = page.locator('select[name="login_role"]');
  await expect(roleSelect).toContainText(roleText);
  await roleSelect.selectOption(role);

  await page.locator('input[name="password"]').fill(password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(url => !url.pathname.includes('/login/'));
}

function collectClientErrors(page) {
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(`console: ${msg.text()}`);
    }
  });
  page.on('pageerror', err => {
    errors.push(`pageerror: ${err.message}`);
  });
  return errors;
}

test.describe('Resource management smoke and regression flows', () => {
  test('login role API loads roles and applicant reaches dashboard', async ({ page }) => {
    const errors = collectClientErrors(page);

    await login(page, 'e2e_applicant', 'APPLICANT', '申请人');

    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator('body')).toContainText('资源看板');
    expect(errors).toEqual([]);
  });

  test('approver shortage validation renders without JavaScript errors', async ({ page }) => {
    const errors = collectClientErrors(page);

    await login(page, 'e2e_approver', 'APPROVER', '预审人');
    await page.goto(`${baseURL}/approve/`);

    await expect(page.locator('body')).toContainText('资源配置预审');
    await expect(page.locator('[id^="badge-"]').first()).toBeVisible();
    await expect(page.locator('[id^="badge-text-"]').first()).toContainText('库存不足');
    expect(errors).toEqual([]);
  });

  test('approver sees executed same-card applications as preempt candidates after project filtering', async ({ page }) => {
    const errors = collectClientErrors(page);

    await login(page, 'e2e_approver', 'APPROVER', '预审人');
    await page.goto(`${baseURL}/approve/?tab=pending&filter_project=E2E-Shortage`);

    const preemptPanel = page.locator('[id^="preempt-panel-"]').first();
    await expect(preemptPanel).toBeVisible();
    await expect(preemptPanel).toContainText('E2E-Donor');
    await expect(preemptPanel).not.toContainText('无法制定抽调方案');
    expect(errors).toEqual([]);
  });

  test('executor can bind an asset and mark an approved application executed', async ({ page }) => {
    const errors = collectClientErrors(page);

    await login(page, 'e2e_executor', 'EXECUTOR', '执行人');
    await page.goto(`${baseURL}/execute/`);

    await expect(page.locator('body')).toContainText('E2E-H100-Node-1');
    await page.locator('input[name="selected_assets"]').first().check();

    const cardInput = page.locator('input[name^="asset_card_"]').first();
    await expect(cardInput).toBeVisible();
    await expect(cardInput).toBeEnabled();

    await page.locator('input[name="executionResult"]').fill('E2E execution completed');
    await page.locator('button[type="submit"]', { hasText: '标记为已执行' }).click();
    await expect(page.locator('body')).toContainText('已标记');
    expect(errors).toEqual([]);
  });
});
