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

const primaryPageScenarios = [
  {
    username: 'e2e_applicant',
    role: 'APPLICANT',
    roleText: '申请人',
    pages: [
      ['/', '资源大盘与看板'],
      ['/apply/', '资源申请'],
      ['/assets/', '物料管理'],
      ['/statistics/', '累计使用看板'],
      ['/feedback/', '问题反馈中心'],
    ],
  },
  {
    username: 'e2e_approver',
    role: 'APPROVER',
    roleText: '预审人',
    pages: [
      ['/', '资源大盘与看板'],
      ['/approve/', '待办审批'],
      ['/statistics/', '累计使用看板'],
      ['/feedback/', '问题反馈中心'],
    ],
  },
  {
    username: 'e2e_dept',
    role: 'DEPT_HEAD',
    roleText: '部门负责人',
    pages: [
      ['/', '资源大盘与看板'],
      ['/approve/', '待办审批'],
      ['/statistics/', '累计使用看板'],
      ['/feedback/', '问题反馈中心'],
    ],
  },
  {
    username: 'e2e_executor',
    role: 'EXECUTOR',
    roleText: '执行人',
    pages: [
      ['/', '资源大盘与看板'],
      ['/execute/', '执行管理'],
      ['/assets/', '物料管理'],
      ['/statistics/', '累计使用看板'],
      ['/feedback/', '问题反馈中心'],
    ],
  },
  {
    username: 'e2e_admin',
    role: 'ADMIN',
    roleText: '管理员',
    pages: [
      ['/', '资源大盘与看板'],
      ['/apply/', '资源申请'],
      ['/approve/', '待办审批'],
      ['/execute/', '执行管理'],
      ['/assets/', '物料管理'],
      ['/statistics/', '累计使用看板'],
      ['/feedback/', '问题反馈中心'],
    ],
  },
];

test.describe('Resource management smoke and regression flows', () => {
  test('login role API loads roles and applicant reaches dashboard', async ({ page }) => {
    const errors = collectClientErrors(page);

    await login(page, 'e2e_applicant', 'APPLICANT', '申请人');

    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator('body')).toContainText('资源看板');
    expect(errors).toEqual([]);
  });

  for (const scenario of primaryPageScenarios) {
    test(`${scenario.role} primary pages render without client errors`, async ({ page }) => {
      const errors = collectClientErrors(page);

      await login(page, scenario.username, scenario.role, scenario.roleText);

      for (const [path, heading] of scenario.pages) {
        await page.goto(`${baseURL}${path}`);
        await expect(page.locator('body')).toContainText(heading);
      }

      expect(errors).toEqual([]);
    });
  }

  test('mobile applicant apply page keeps main content usable', async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    const errors = collectClientErrors(page);

    await login(page, 'e2e_applicant', 'APPLICANT', '申请人');
    await page.goto(`${baseURL}/apply/`);

    await expect(page.locator('body')).toContainText('资源申请');
    await expect(page.locator('body')).toContainText('新建申请单');

    const mainBox = await page.locator('.main-content').boundingBox();
    expect(mainBox.width).toBeGreaterThan(340);
    expect(errors).toEqual([]);

    await context.close();
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

  test('applicant can reveal password for an executed allocated bare-metal asset', async ({ page }) => {
    const errors = collectClientErrors(page);

    await login(page, 'e2e_applicant', 'APPLICANT', '申请人');
    await page.goto(`${baseURL}/apply/`);
    await page.locator('#tab-btn-history').click();

    const row = page.locator('#tab-content-history tbody tr', { hasText: 'E2E-Password' }).first();
    await expect(row).toBeVisible();
    await row.locator('button[onclick^="showAppDetails"]').click();

    const modal = page.locator('#app-details-modal');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('E2E-Password-Node-1');

    const revealButton = modal.locator('button[onclick^="togglePasswordVisibility"]').first();
    await expect(revealButton).toBeVisible();
    await revealButton.click();
    await expect(modal.locator('[id^="pwd-"]').first()).toHaveText('bare-metal-secret-1');

    expect(errors).toEqual([]);
  });

  test('application details escapes user-provided text before rendering', async ({ page }) => {
    const errors = collectClientErrors(page);

    await page.addInitScript(() => {
      window.__e2e_xss_triggered = 0;
    });

    await login(page, 'e2e_applicant', 'APPLICANT', '申请人');
    await page.goto(`${baseURL}/apply/`);
    await page.locator('#tab-btn-history').click();

    const row = page.locator('#tab-content-history tbody tr', { hasText: 'E2E-XSS' }).first();
    await expect(row).toBeVisible();
    await row.locator('button[onclick^="showAppDetails"]').click();

    const modal = page.locator('#app-details-modal');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('<img src=x onerror="window.__e2e_xss_triggered=1">');
    await expect(modal.locator('img[src="x"]')).toHaveCount(0);
    expect(await page.evaluate(() => window.__e2e_xss_triggered)).toBe(0);

    expect(errors).toEqual([]);
  });

  test('executor can filter assets and reveal asset management password', async ({ page }) => {
    const errors = collectClientErrors(page);

    await login(page, 'e2e_executor', 'EXECUTOR', '执行人');
    await page.goto(`${baseURL}/assets/`);

    const passwordRow = page.locator('#assets-table-body tr', { hasText: 'E2E-Password-Node-1' }).first();
    await expect(passwordRow).toBeVisible();

    await page.locator('#search-query').fill('Password-Node');
    await expect(passwordRow).toBeVisible();
    await expect(page.locator('#assets-table-body tr', { hasText: 'E2E-H100-Node-1' })).toBeHidden();

    await passwordRow.locator('button[onclick^="togglePassword"]').click();
    await expect(passwordRow.locator('[id^="pwd-text-"]')).toHaveText('bare-metal-secret-1');

    expect(errors).toEqual([]);
  });

  test('asset edit preserves password when placeholder is submitted before async password load', async ({ page }) => {
    const errors = collectClientErrors(page);

    await page.route('**/assets/password/?asset_id=*', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'simulated password load failure' }),
    }));

    await login(page, 'e2e_executor', 'EXECUTOR', '执行人');
    await page.goto(`${baseURL}/assets/`);

    const passwordRow = page.locator('#assets-table-body tr', { hasText: 'E2E-Password-Node-1' }).first();
    await expect(passwordRow).toBeVisible();
    await passwordRow.locator('button', { hasText: '编辑' }).click();

    const modal = page.locator('#edit-modal');
    await expect(modal).toBeVisible();
    await expect(page.locator('#edit-password')).toHaveValue('••••••');
    await modal.locator('button[type="submit"]').click();
    await expect(page.locator('body')).toContainText('物料资产已成功更新');

    await page.unroute('**/assets/password/?asset_id=*');
    const updatedRow = page.locator('#assets-table-body tr', { hasText: 'E2E-Password-Node-1' }).first();
    await updatedRow.locator('button[onclick^="togglePassword"]').click();
    await expect(updatedRow.locator('[id^="pwd-text-"]')).toHaveText('bare-metal-secret-1');

    expect(errors).toEqual([]);
  });

  test('feedback can be submitted by applicant and resolved by executor', async ({ page }) => {
    const errors = collectClientErrors(page);
    const title = 'E2E feedback lifecycle';

    await login(page, 'e2e_applicant', 'APPLICANT', '申请人');
    await page.goto(`${baseURL}/feedback/`);
    await page.locator('#feedback-title').fill(title);
    await page.locator('#feedback-content').fill('E2E feedback content for smoke testing.');
    await page.locator('button[type="submit"]', { hasText: '提交反馈问题' }).click();
    await expect(page.locator('.feedback-card', { hasText: title })).toBeVisible();

    await login(page, 'e2e_executor', 'EXECUTOR', '执行人');
    await page.goto(`${baseURL}/feedback/`);
    const card = page.locator('.feedback-card', { hasText: title }).first();
    await expect(card).toBeVisible();
    await card.locator('button', { hasText: '标记为已解决' }).click();
    await expect(page.locator('.feedback-card', { hasText: title })).toContainText('已解决');

    expect(errors).toEqual([]);
  });
});
