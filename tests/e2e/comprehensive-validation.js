const assert = require('assert');
const { chromium } = require('playwright');

const baseURL = process.env.BASE_URL || 'http://127.0.0.1:8001';
const password = process.env.E2E_PASSWORD || 'TestPass123!';

const normalApplications = [
  { user: 'e2ec_alpha_applicant_01', team: 'E2EC-Alpha团队', project: 'E2EC-Normal-Alpha-01', form: '裸机', type: 'A100', count: 2, leader: 'e2ec_alpha_leader', leaderRoleText: '组长' },
  { user: 'e2ec_alpha_applicant_02', team: 'E2EC-Alpha团队', project: 'E2EC-Normal-Alpha-02', form: '推理池', type: 'A800', count: 2, leader: 'e2ec_alpha_leader', leaderRoleText: '组长' },
  { user: 'e2ec_alpha_applicant_03', team: 'E2EC-Alpha团队', project: 'E2EC-Normal-Alpha-03', form: '训练池', type: 'H100', count: 2, leader: 'e2ec_alpha_leader', leaderRoleText: '组长' },
  { user: 'e2ec_beta_applicant_01', team: 'E2EC-Beta团队', project: 'E2EC-Normal-Beta-01', form: '裸机', type: 'H200', count: 2, leader: 'e2ec_beta_leader', leaderRoleText: '组长' },
  { user: 'e2ec_beta_applicant_02', team: 'E2EC-Beta团队', project: 'E2EC-Normal-Beta-02', form: '开发池', type: 'L40S', count: 2, leader: 'e2ec_beta_leader', leaderRoleText: '组长' },
  { user: 'e2ec_beta_applicant_03', team: 'E2EC-Beta团队', project: 'E2EC-Normal-Beta-03', form: '推理池', type: 'A800', count: 2, leader: 'e2ec_beta_leader', leaderRoleText: '组长' },
  { user: 'e2ec_gamma_applicant_01', team: 'E2EC-Gamma团队', project: 'E2EC-Normal-Gamma-01', form: '训练池', type: 'H100', count: 2, leader: 'e2ec_gamma_leader', leaderRoleText: '组长' },
  { user: 'e2ec_gamma_applicant_02', team: 'E2EC-Gamma团队', project: 'E2EC-Normal-Gamma-02', form: '开发池', type: 'L40S', count: 2, leader: 'e2ec_gamma_leader', leaderRoleText: '组长' },
  { user: 'e2ec_delta_applicant_01', team: 'E2EC-Delta团队', project: 'E2EC-Normal-Delta-01', form: '裸机', type: 'A100', count: 2, leader: 'e2ec_delta_leader', leaderRoleText: '组长' },
  { user: 'e2ec_delta_applicant_02', team: 'E2EC-Delta团队', project: 'E2EC-Normal-Delta-02', form: '开发池', type: 'L40S', count: 2, leader: 'e2ec_delta_leader', leaderRoleText: '组长' },
];

const emergencyApplication = {
  user: 'e2ec_delta_applicant_01',
  team: 'E2EC-Delta团队',
  project: 'E2EC-Emergency-Urgent',
  form: '裸机',
  type: 'A100',
  count: 2,
  leader: 'e2ec_delta_leader',
  leaderRoleText: '组长',
};

function log(message) {
  process.stdout.write(`${message}\n`);
}

async function withUser(browser, username, role, roleText, fn) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));
  page.on('dialog', dialog => dialog.accept());
  await login(page, username, role, roleText);
  try {
    await fn(page);
    assert.deepStrictEqual(errors, [], `${username} browser errors: ${errors.join('\n')}`);
  } finally {
    await context.close();
  }
}

async function login(page, username, role, roleText) {
  await page.goto(`${baseURL}/login/`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="username"]').blur();
  await page.waitForFunction(
    ({ expected }) => document.querySelector('select[name="login_role"]')?.innerText.includes(expected),
    { expected: roleText },
    { timeout: 10000 },
  );
  await page.locator('select[name="login_role"]').selectOption(role);
  await page.locator('input[name="password"]').fill(password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.locator('button[type="submit"]').click(),
  ]);
  assert(!page.url().includes('/login/'), `login failed for ${username}`);
}

async function submitApplication(page, app, priority = 'MEDIUM') {
  await page.goto(`${baseURL}/apply/`, { waitUntil: 'domcontentloaded' });
  await page.locator('select[name="team"]').selectOption(app.team);
  await page.locator('select[name="cardForm"]').selectOption(app.form);
  await page.locator('select[name="cardType"]').selectOption(app.type);
  await page.locator('#project-search-input').fill(app.project);
  await page.locator('#project-search-input').click();
  await page.locator(`.project-item[data-value="${app.project}"]`).click();
  await page.locator('select[name="priority"]').selectOption(priority);
  await page.locator('input[name="count"]').fill(String(app.count));
  await page.locator('input[name="minCount"]').fill('1');
  await page.locator(`input.user-cb[value="${app.user}"]`).check();
  await page.locator('input[name="model_used"]').fill(`${app.project}-model`);
  await page.locator('textarea[name="purpose"]').fill(`${app.project} validation purpose`);
  await page.locator('textarea[name="priorityReason"]').fill(`${app.project} priority`);
  await page.locator('textarea[name="note"]').fill(`${app.project} note`);
  await page.locator('#input-startDate').fill('2026-06-05');
  await page.locator('#input-endDate').fill('2026-06-19');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.locator('button[type="submit"]', { hasText: '提交申请' }).click(),
  ]);
  await assertBodyContains(page, '申请已成功提交');
}

async function assertBodyContains(page, text) {
  await page.waitForFunction(
    ({ expected }) => document.body.innerText.includes(expected),
    { expected: text },
    { timeout: 10000 },
  );
}

async function getApproveCard(page, project, applicant) {
  await page.goto(`${baseURL}/approve/?tab=pending&filter_project=${encodeURIComponent(project)}`, { waitUntil: 'domcontentloaded' });
  const card = page.locator('.app-card-item').filter({ hasText: project }).filter({ hasText: applicant }).first();
  await card.waitFor({ state: 'visible', timeout: 10000 });
  return card;
}

async function getAppIdFromApprove(page, project, applicant) {
  const card = await getApproveCard(page, project, applicant);
  return card.locator('input[name="app_id"]').first().inputValue();
}

async function submitCurrentPageForm(page, fields, path = '/approve/') {
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.evaluate(({ fields, path }) => {
      const form = document.createElement('form');
      form.method = 'POST';
      form.action = path;
      const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
      const add = (name, value) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = name;
        input.value = value;
        form.appendChild(input);
      };
      if (csrf) add('csrfmiddlewaretoken', csrf);
      for (const [name, value] of Object.entries(fields)) {
        if (Array.isArray(value)) {
          value.forEach(item => add(name, item));
        } else {
          add(name, value);
        }
      }
      document.body.appendChild(form);
      form.submit();
    }, { fields, path }),
  ]);
}

async function teamApprove(page, app) {
  const appId = await getAppIdFromApprove(page, app.project, app.user);
  await submitCurrentPageForm(page, {
    action: 'team_approve',
    app_id: appId,
    team_leader_note: `team approved ${app.project}`,
  });
  await assertBodyContains(page, '已同意');
  return appId;
}

async function preApprove(page, app, appId, preempt = {}) {
  await getApproveCard(page, app.project, app.user);
  const fields = {
    action: 'pre_allocate',
    app_id: appId,
    allocatedCount: String(app.count),
    allocatedCardType: app.type,
    allocatedCardForm: app.form,
    pre_approver_note: `pre approved ${app.project}`,
    ...preempt,
  };
  await submitCurrentPageForm(page, fields);
  await assertBodyContains(page, '终审');
}

async function finalApprove(page, app, appId) {
  await getApproveCard(page, app.project, app.user);
  await submitCurrentPageForm(page, {
    action: 'final_approve',
    app_id: appId,
    final_approver_note: `final approved ${app.project}`,
  });
  await assertBodyContains(page, '终审已批准');
}

async function executeApplication(page, app, appId) {
  await page.goto(`${baseURL}/execute/`, { waitUntil: 'domcontentloaded' });
  const form = page.locator(`form:has(input[name="app_id"][value="${appId}"])`).first();
  await form.waitFor({ state: 'visible', timeout: 10000 });
  const assetId = await form.evaluate(formElement => {
    const candidates = [...formElement.querySelectorAll('input[name="selected_assets"]')].map(input => ({
      input,
      text: input.closest('div')?.innerText || '',
    }));
    const preferred = candidates.find(candidate => candidate.text.includes('E2EC-FULL')) || candidates[0];
    return preferred?.input.value;
  });
  assert(assetId, `no executable asset found for ${app.project}`);
  await submitCurrentPageForm(page, {
    action: 'execute',
    app_id: appId,
    selected_assets: [assetId],
    [`asset_card_${assetId}`]: String(app.count),
    executionResult: `executed ${app.project}`,
  }, '/execute/');
  await assertBodyContains(page, '已标记');
}

async function executeEmergency(page, urgentAppId, donorAppId) {
  await page.goto(`${baseURL}/execute/`, { waitUntil: 'domcontentloaded' });
  const form = page.locator(`form:has(input[name="app_id"][value="${urgentAppId}"])`).first();
  await form.waitFor({ state: 'visible', timeout: 10000 });
  const preemptAssetId = await form.locator(`input[name="preempted_assets_${donorAppId}"]`).first().getAttribute('value');
  assert(preemptAssetId, 'no preemptable donor asset found for emergency execution');
  await submitCurrentPageForm(page, {
    action: 'execute',
    app_id: urgentAppId,
    [`preempted_assets_${donorAppId}`]: [preemptAssetId],
    [`preempt_card_${donorAppId}_${preemptAssetId}`]: String(emergencyApplication.count),
    executionResult: 'executed emergency transfer',
  }, '/execute/');
  await assertBodyContains(page, '已标记');
}

async function getApplicationDetails(page, appId) {
  const response = await page.goto(`${baseURL}/api/application/details/?app_id=${appId}`, { waitUntil: 'domcontentloaded' });
  assert.strictEqual(response.status(), 200);
  return JSON.parse(await page.locator('body').innerText());
}

async function getAssetPassword(page, assetId) {
  const response = await page.goto(`${baseURL}/assets/password/?asset_id=${assetId}`, { waitUntil: 'domcontentloaded' });
  assert.strictEqual(response.status(), 200);
  return JSON.parse(await page.locator('body').innerText());
}

async function releaseApplication(page, appId, releaseCount) {
  await page.goto(`${baseURL}/execute/?tab=history`, { waitUntil: 'domcontentloaded' });
  await submitCurrentPageForm(page, {
    action: 'release',
    app_id: appId,
    release_count: String(releaseCount),
  }, '/execute/');
  await assertBodyContains(page, '已成功释放');
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const appIds = new Map();

  try {
    log('Phase A: 系统配置和角色验证');
    await withUser(browser, 'e2ec_admin_full', 'ADMIN', '管理员', async page => {
      await page.goto(`${baseURL}/apply/`, { waitUntil: 'domcontentloaded' });
      for (const team of ['E2EC-Alpha团队', 'E2EC-Beta团队', 'E2EC-Gamma团队', 'E2EC-Delta团队']) {
        await assertBodyContains(page, team);
      }
      for (const form of ['裸机', '推理池', '训练池', '开发池']) {
        await assertBodyContains(page, form);
      }
      for (const model of ['A100', 'A800', 'H100', 'H200', 'L40S']) {
        await assertBodyContains(page, model);
      }
    });

    log('Phase B: 10 个申请人提交申请');
    for (const app of normalApplications) {
      await withUser(browser, app.user, 'APPLICANT', '申请人', async page => {
        await submitApplication(page, app);
      });
    }

    log('Phase C: 组长审批');
    for (const leader of ['e2ec_alpha_leader', 'e2ec_beta_leader', 'e2ec_gamma_leader', 'e2ec_delta_leader']) {
      const apps = normalApplications.filter(app => app.leader === leader);
      await withUser(browser, leader, 'TEAM_LEADER', '组长', async page => {
        for (const app of apps) {
          const appId = await teamApprove(page, app);
          appIds.set(app.project, appId);
        }
      });
    }

    log('Phase D: 资源预审');
    await withUser(browser, 'e2ec_pre_approver', 'APPROVER', '预审人', async page => {
      for (const app of normalApplications) {
        await preApprove(page, app, appIds.get(app.project));
      }
    });

    log('Phase E: 部门终审');
    await withUser(browser, 'e2ec_dept_head', 'DEPT_HEAD', '部门负责人', async page => {
      for (const app of normalApplications) {
        await finalApprove(page, app, appIds.get(app.project));
      }
    });

    log('Phase F: 执行绑定');
    await withUser(browser, 'e2ec_executor_full', 'EXECUTOR', '执行人', async page => {
      for (const app of normalApplications) {
        await executeApplication(page, app, appIds.get(app.project));
      }
    });

    log('Phase G: 裸机密码和部分释放验证');
    await withUser(browser, 'e2ec_alpha_applicant_01', 'APPLICANT', '申请人', async page => {
      const details = await getApplicationDetails(page, appIds.get('E2EC-Normal-Alpha-01'));
      assert.strictEqual(details.status, 'EXECUTED');
      assert.strictEqual(details.allocatedCount, 2);
      const assetWithPassword = details.assets.find(asset => asset.has_password_permission);
      assert(assetWithPassword, 'bare-metal applicant cannot view own password permission');
      const passwordData = await getAssetPassword(page, assetWithPassword.id);
      assert(passwordData.password, 'bare-metal applicant password endpoint returned empty password');
    });
    await withUser(browser, 'e2ec_executor_full', 'EXECUTOR', '执行人', async page => {
      await releaseApplication(page, appIds.get('E2EC-Normal-Alpha-01'), 1);
      const details = await getApplicationDetails(page, appIds.get('E2EC-Normal-Alpha-01'));
      assert.strictEqual(details.status, 'EXECUTED');
      assert.strictEqual(details.allocatedCount, 1);
      assert.strictEqual(details.assets.reduce((sum, asset) => sum + asset.allocated_cards, 0), 1);
    });

    log('Phase H: 紧急协调全流程');
    await withUser(browser, emergencyApplication.user, 'APPLICANT', '申请人', async page => {
      await submitApplication(page, emergencyApplication, 'HIGH');
    });
    await withUser(browser, emergencyApplication.leader, 'TEAM_LEADER', '组长', async page => {
      const urgentId = await teamApprove(page, emergencyApplication);
      appIds.set(emergencyApplication.project, urgentId);
    });
    await withUser(browser, 'e2ec_pre_approver', 'APPROVER', '预审人', async page => {
      const urgentCard = await getApproveCard(page, emergencyApplication.project, emergencyApplication.user);
      await assertBodyContains(page, 'E2EC-Emergency-Donor');
      const donorRow = urgentCard.locator('tr').filter({ hasText: 'E2EC-Emergency-Donor' }).first();
      await donorRow.waitFor({ state: 'visible', timeout: 10000 });
      const preemptInputName = await donorRow
        .locator(`input[name^="preempt_${appIds.get(emergencyApplication.project)}_"]`)
        .first()
        .getAttribute('name');
      assert(preemptInputName, 'emergency preempt input was not rendered');
      const donorId = preemptInputName.split('_').pop();
      appIds.set('E2EC-Emergency-Donor', donorId);
      await preApprove(page, emergencyApplication, appIds.get(emergencyApplication.project), {
        [`preempt_${appIds.get(emergencyApplication.project)}_${donorId}`]: String(emergencyApplication.count),
      });
    });
    await withUser(browser, 'e2ec_dept_head', 'DEPT_HEAD', '部门负责人', async page => {
      await finalApprove(page, emergencyApplication, appIds.get(emergencyApplication.project));
    });
    await withUser(browser, 'e2ec_executor_full', 'EXECUTOR', '执行人', async page => {
      await executeEmergency(page, appIds.get(emergencyApplication.project), appIds.get('E2EC-Emergency-Donor'));
      const urgentDetails = await getApplicationDetails(page, appIds.get(emergencyApplication.project));
      assert.strictEqual(urgentDetails.status, 'EXECUTED');
      assert.strictEqual(urgentDetails.allocatedCount, emergencyApplication.count);
      const donorDetails = await getApplicationDetails(page, appIds.get('E2EC-Emergency-Donor'));
      assert.strictEqual(donorDetails.allocatedCount, 0);
    });

    log('Comprehensive validation passed');
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
