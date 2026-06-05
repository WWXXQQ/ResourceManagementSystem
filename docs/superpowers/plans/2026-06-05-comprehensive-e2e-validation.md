# Comprehensive E2E Validation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a comprehensive Playwright validation suite that proves every supported feature of the material resource management system works across configuration, authentication, application, approval, execution, release, assets, statistics, feedback, reminders, APIs, admin back office, and emergency coordination.

**Architecture:** Use the existing Django app and Playwright E2E framework. Seed deterministic baseline users/options/resources through `tests/e2e/seed_e2e_data.py`, then perform business workflows through the real UI and selected Django management/unit checks. Validate forms, permissions, state transitions, inventory changes, asset bindings, password visibility, partial release, reminders, feedback, dashboard/statistics integrity, admin import/reset/resend operations, and emergency coordination.

**Tech Stack:** Django, SQLite test/dev database, Playwright, existing `npm run test:e2e` command, PowerShell on Windows.

---

## Scope

This validation must cover every route, admin capability, API endpoint, workflow state transition, and scheduled command exposed by the current system. The three mandatory business scenarios remain the core acceptance suite, but the plan also includes all supporting functions that can affect production correctness.

1. System configuration through admin-equivalent setup:
   - Multiple resource forms: `裸机`, `推理池`, `训练池`, `开发池`.
   - Multiple card models: `A100`, `A800`, `H100`, `H200`, `L40S`.
   - Four teams.
   - Ten applicants distributed across teams.
   - Role accounts for team leaders, pre-approver, department head, executor, and admin.
   - Resource inventory and physical assets for normal and emergency scenarios.

2. Normal application workflow:
   - Ten applicants submit resource applications.
   - Team leaders approve according to team ownership.
   - Pre-approver performs pre-allocation.
   - Department head performs final approval.
   - Executor binds assets and marks applications executed.
   - Applicant sees execution result and bare-metal password where applicable.
   - Executor partially releases resources and inventory/assets update correctly.

3. Emergency coordination workflow:
   - One applicant submits an urgent request with insufficient idle resources.
   - The system displays same-card executed/approved candidate applications.
   - Approver chooses coordination/preemption plan.
   - Department head approves.
   - Executor completes resource transfer.
   - Donor and urgent applications both reflect correct post-coordination asset/card counts.

4. Supporting platform features:
   - Authentication, role selection, password change, logout, and unauthorized access handling.
   - Dashboard inventory/status cards and notification prompts.
   - Application form dynamic inventory, searchable project/user selectors, attachment upload/paste preview, validation, history, project overview, cancellation, reminders, and details modal.
   - Approval single/batch approve/reject/pre-allocate/final-approve/final-reject/recall/history/filter flows.
   - Execution binding, actual-card-count adjustment, full release, required partial release, auto-release toggle, and coordination execution.
   - Asset management view/filter/export/add/edit/delete/password permissions.
   - Statistics filters, ranking tables, empty states, and date quick filters.
   - Feedback submit/edit/delete/resolve/image permissions.
   - Reminder API receiver selection, notification log persistence, mock endpoint, and admin resend.
   - Public JSON APIs: inventory, application details, asset password, and user roles.
   - Admin back office: bulk import options/users/history applications/assets, password reset, inventory validation, application status correction side effects, global settings, and notification logs.
   - Management command `release_expired_assets`.

## Complete Feature Coverage Matrix

| Area | Supported capabilities discovered in code | Validation method | Required acceptance points |
|---|---|---|---|
| Authentication and session | Login with selected role, `/api/user/roles/`, logout, change password | Playwright UI plus API request checks | Correct role list per user, invalid role cannot enter privileged page, changed password works, old password fails, logout clears session |
| Dashboard | Inventory summaries, application status cards, role-specific notifications, sidebar counts | Playwright UI checks for each role | Counts match seeded database, pending/approved/executed/released/rejected notices appear only for eligible users |
| System options | Team/card form/card type/project/region options | Admin seed plus UI dropdown checks | Four teams and all required forms/models/regions/projects appear in apply/admin/inventory/asset forms |
| Users and roles | Multi-role users, team ownership, admin reset password, bulk import users | Django admin UI tests plus API checks | Imported users get role/team/email, duplicate import updates missing fields, invalid team is rejected, password reset sets `123456` and login succeeds |
| Inventory | Dynamic inventory, safe availability, admin validation | Playwright UI/API plus Django model/admin checks | Available count is `totalCount - allocatedCount`, negative totals and allocated > total fail validation, allocation/release never makes counts negative |
| Application submit | New application, project search, user multi-select/custom user, attachment, paste preview, date/count validation | Playwright UI tests | Valid applications submit, invalid min/count/date/project/empty users are blocked, attachment previews and persists, history is user-isolated |
| Application history/details | My history, project overview, cancel pending app, details modal, attachment link, password reveal for own bare-metal assets | Playwright UI/API checks | Own apps visible, other applicants' private history hidden, overview includes all projects, pending app can be cancelled, details escape user text |
| Approval workflow | Team approve/reject/batch approve, pre-approve/reject/batch pre-allocation, final approve/reject/batch final, recall by team/pre-approver, filters/history | Playwright full-flow tests by role | Only authorized roles can operate, team leaders are team-scoped, statuses move exactly through `PENDING_TEAM -> PENDING_PRE -> PENDING_FINAL -> APPROVED`, rejects stop flow, recalls restore prior stage |
| Emergency coordination | Shortage detection, same-card executed/approved candidates, candidate exclusion, coordination details, donor impact | Playwright full-flow and database invariant checks | Candidate list includes eligible donor and excludes mismatched/same-project apps, selected plan persists, execution transfers cards/assets without over-allocation |
| Execution | Bind assets, selected card counts, preempted assets, actual card count lower than approved, release, auto-release toggle | Playwright UI plus DB assertions | Asset allocations created, asset status/used cards/owner/current users/app name refresh, surplus inventory returns, release unbinds assets, toggle persists |
| Partial release | Release part of an executed allocation by card count and/or selected asset | Playwright test expected to fail until supported if current UI lacks it | Partial release is mandatory: app allocation, inventory, asset used cards, status, and applicant details all reflect reduced allocation |
| Asset management | View/filter/export CSV for all roles, add/edit/delete for executor/admin, password reveal, encrypted password preservation, delete blocking in-use assets | Playwright UI/API checks | Non-executor cannot mutate assets or reveal password, executor/admin can manage assets, edit placeholder does not erase password, in-use delete is blocked |
| Statistics | Date/card filters, 7/30/90/year quick filters, status aggregation, team/project/applicant rankings, empty state | Playwright UI checks plus DB seeded totals | Filtered totals match seeded applications, ranking order is deterministic, no-data ranges render a clean empty state |
| Feedback | Submit feedback, image upload, edit pending feedback, delete own/admin feedback, resolve by executor/admin, public list | Playwright UI checks | Required fields and image type/size validation work, only owner/admin edits/deletes, resolved feedback cannot be edited, executor/admin can resolve |
| Reminders | `/remind/`, receiver selection per workflow stage, mock notification endpoint, notification logs, admin resend failed logs | Playwright API/UI plus Django admin checks | Applicant/admin can remind eligible app, unauthorized users fail, completed statuses fail, logs persist, resend updates log state |
| JSON APIs | `/api/inventory/`, `/api/application/details/`, `/assets/password/`, `/api/user/roles/`, `/mock-notification-api/` | Playwright `request` API tests | HTTP method/status validation, unauthorized and non-owner data access denied, payloads include expected fields and no password leaks |
| Admin application data | Bulk import history applications, admin status correction inventory side effects | Django admin UI tests plus model assertions | Valid rows import, invalid options fail with row-level errors, changing consuming status to released/rejected/cancelled returns inventory and unbinds assets |
| Admin assets/options/settings | Bulk import options/assets, global settings, notification log admin | Django admin UI tests | Duplicate options ignored, invalid categories rejected, assets validate configured form/type/region/owner, settings persist, failed notifications can be resent |
| Scheduled release | `release_expired_assets` management command | Django test command invocation | Disabled setting skips, enabled releases overdue executed apps, future/not-overdue apps remain, command is idempotent |
| Security and resilience | XSS escaping, CSRF/method checks, cross-user isolation, no console errors, responsive layout | Playwright desktop/mobile checks and API negative tests | User content renders as text, protected POSTs require permission/session, no client JS errors, mobile core workflows remain usable |

## Files

- Modify: `tests/e2e/seed_e2e_data.py`
  - Add deterministic users, teams, options, inventory, and assets.
  - Keep existing baseline data used by previous regression tests.
  - Add helper dictionaries for teams, users, resources, and scenario constants.
  - Add records for rejection/recall/reminder/auto-release/statistics/admin-import fixture scenarios.

- Modify: `tests/e2e/resource-management.spec.js`
  - Add E2E helpers for admin/login/form submission/approval/execution/release.
  - Add test groups for system configuration, normal full lifecycle, emergency coordination, access control, assets, statistics, feedback, reminders, API permissions, admin UI, and responsive checks.
  - Preserve existing regression tests.

- Add or modify Django tests when browser automation is the wrong tool:
  - Test: `resource_app/tests/test_admin_imports.py`
    - Admin bulk import options/users/history applications/assets.
    - Admin password reset.
    - Admin status-change inventory/asset side effects.
  - Test: `resource_app/tests/test_release_expired_assets.py`
    - `release_expired_assets` command.
  - Test: `resource_app/tests/test_api_permissions.py`
    - Negative permission and method coverage for JSON endpoints.

- No business-code changes planned initially.
  - If tests expose defects, follow TDD: keep the failing test, fix the smallest production code path, rerun targeted then full suite.

## Test Data Design

### Teams

Use four teams:

- `E2E-Alpha团队`
- `E2E-Beta团队`
- `E2E-Gamma团队`
- `E2E-Delta团队`

### Users

Create these users in seed data, all with password `TestPass123!`:

Applicants:

- `e2e_alpha_applicant_01`, team `E2E-Alpha团队`
- `e2e_alpha_applicant_02`, team `E2E-Alpha团队`
- `e2e_alpha_applicant_03`, team `E2E-Alpha团队`
- `e2e_beta_applicant_01`, team `E2E-Beta团队`
- `e2e_beta_applicant_02`, team `E2E-Beta团队`
- `e2e_beta_applicant_03`, team `E2E-Beta团队`
- `e2e_gamma_applicant_01`, team `E2E-Gamma团队`
- `e2e_gamma_applicant_02`, team `E2E-Gamma团队`
- `e2e_delta_applicant_01`, team `E2E-Delta团队`
- `e2e_delta_applicant_02`, team `E2E-Delta团队`

Team leaders:

- `e2e_alpha_leader`, role `TEAM_LEADER`, team `E2E-Alpha团队`
- `e2e_beta_leader`, role `TEAM_LEADER`, team `E2E-Beta团队`
- `e2e_gamma_leader`, role `TEAM_LEADER`, team `E2E-Gamma团队`
- `e2e_delta_leader`, role `TEAM_LEADER`, team `E2E-Delta团队`

Cross-team roles:

- `e2e_pre_approver`, role `APPROVER`
- `e2e_dept_head`, role `DEPT_HEAD`
- `e2e_executor_full`, role `EXECUTOR`
- `e2e_admin_full`, role `ADMIN`, superuser/staff

Keep existing users such as `e2e_applicant`, `e2e_approver`, and `e2e_executor` because current regression tests depend on them.

### System Options

Add options:

- `TEAM`: four teams above plus existing `平台团队`.
- `CARD_FORM`: `裸机`, `推理池`, `训练池`, `开发池`.
- `CARD_TYPE`: `A100`, `A800`, `H100`, `H200`, `L40S`.
- `REGION`: `北京`, `上海`, `深圳`.
- `PROJECT`: normal and emergency projects listed below.

### Inventory

Create inventory records sufficient for normal scenarios and constrained enough for emergency coordination:

- `E2E-A100-BareMetal-Beijing`: `裸机`, `A100`, `北京`, total `12`, allocated `0`.
- `E2E-A800-Inference-Shanghai`: `推理池`, `A800`, `上海`, total `10`, allocated `0`.
- `E2E-H100-Training-Beijing`: `训练池`, `H100`, `北京`, total `8`, allocated `0`.
- `E2E-H200-BareMetal-Shenzhen`: `裸机`, `H200`, `深圳`, total `8`, allocated `0`.
- `E2E-L40S-Dev-Beijing`: `开发池`, `L40S`, `北京`, total `12`, allocated `0`.
- `E2E-Emergency-A100-Beijing`: `裸机`, `A100`, `北京`, total `2`, allocated `2`.

### Physical Assets

Create assets for execution binding:

- A100 bare metal:
  - `E2E-FULL-A100-Node-01`, 4 cards, password `full-a100-secret-01`.
  - `E2E-FULL-A100-Node-02`, 4 cards, password `full-a100-secret-02`.
  - `E2E-FULL-A100-Node-03`, 4 cards, password `full-a100-secret-03`.
- A800 inference:
  - `E2E-FULL-A800-Pool-01`, 5 cards.
  - `E2E-FULL-A800-Pool-02`, 5 cards.
- H100 training:
  - `E2E-FULL-H100-Train-01`, 4 cards.
  - `E2E-FULL-H100-Train-02`, 4 cards.
- H200 bare metal:
  - `E2E-FULL-H200-Node-01`, 4 cards, password `full-h200-secret-01`.
  - `E2E-FULL-H200-Node-02`, 4 cards, password `full-h200-secret-02`.
- L40S dev:
  - `E2E-FULL-L40S-Dev-01`, 4 cards.
  - `E2E-FULL-L40S-Dev-02`, 4 cards.
  - `E2E-FULL-L40S-Dev-03`, 4 cards.
- Emergency donor:
  - `E2E-EMERG-A100-Donor-01`, 2 cards, already bound to executed donor application.

### Additional Scenario Fixtures

Create dedicated records so each supporting feature can be validated without interfering with the ten normal applications:

- Rejection fixture:
  - `E2E-Reject-Team`, status `PENDING_TEAM`, used to verify team rejection.
  - `E2E-Reject-Pre`, status `PENDING_PRE`, used to verify pre-approval rejection.
  - `E2E-Reject-Final`, status `PENDING_FINAL`, used to verify final rejection and inventory non-consumption.
- Recall fixture:
  - `E2E-Recall-Team`, initially moved from `PENDING_TEAM` to `PENDING_PRE`, then recalled by team leader.
  - `E2E-Recall-Pre`, initially moved from `PENDING_PRE` to `PENDING_FINAL`, then recalled by pre-approver.
- Reminder fixture:
  - One application in each stage: `PENDING_TEAM`, `PENDING_PRE`, `PENDING_FINAL`, `APPROVED`, plus `EXECUTED` as the "no reminder required" negative case.
- Auto-release fixture:
  - `E2E-AutoRelease-Expired`, `EXECUTED`, `endDate` before test date, with bound asset and inventory allocation.
  - `E2E-AutoRelease-Future`, `EXECUTED`, future `endDate`, with bound asset and inventory allocation.
- Statistics fixture:
  - Applications across at least two creation dates, three teams, three card models, and all counted statuses `APPROVED`, `EXECUTED`, `RELEASED`.
- Asset-management fixture:
  - One `IDLE` asset for add/edit/delete.
  - One `IN_USE` asset with allocation for delete-block validation.
  - One `FAULT` asset for filter/status validation.
- Feedback fixture:
  - One pending feedback owned by applicant.
  - One resolved feedback owned by applicant.
  - One pending feedback owned by another applicant.
- API security fixture:
  - One bare-metal executed application for the current applicant.
  - One bare-metal executed application for another applicant.
  - One non-bare-metal executed application with asset allocation.

## Validation Points

### A. System Configuration Validation

1. Admin login:
   - Login as `e2e_admin_full`.
   - Expected: dashboard loads; admin sidebar entries visible.

2. Option configuration:
   - Validate `TEAM`, `CARD_FORM`, `CARD_TYPE`, `REGION`, and `PROJECT` options exist in forms.
   - Expected:
     - Apply form team dropdown contains all four teams.
     - Card form dropdown contains `裸机`, `推理池`, `训练池`, `开发池`.
     - Card model dropdown contains `A100`, `A800`, `H100`, `H200`, `L40S`.
     - Project selector contains all normal and emergency projects.

3. User-role configuration:
   - Login-role API returns correct roles for all created users.
   - Expected:
     - Applicants only show `APPLICANT`.
     - Team leaders show `TEAM_LEADER`.
     - Pre-approver shows `APPROVER`.
     - Department head shows `DEPT_HEAD`.
     - Executor shows `EXECUTOR`.
     - Admin shows `ADMIN`.

4. Team ownership:
   - Each team leader sees only applications from their own team at team-approval stage.
   - Expected:
     - `e2e_alpha_leader` sees Alpha applicants only.
     - `e2e_beta_leader` sees Beta applicants only.
     - No cross-team leakage.

5. Inventory and assets:
   - Asset page shows configured physical assets.
   - Dashboard inventory totals reflect configured totals.
   - Expected:
     - A100/A800/H100/H200/L40S inventory rows exist.
     - Asset counts and statuses are initially correct.

### B. Normal Full Lifecycle Validation

Submit these ten applications through the UI:

| Applicant | Team | Project | Form | Model | Count | Expected Track |
|---|---|---|---|---|---:|---|
| e2e_alpha_applicant_01 | Alpha | E2E-Normal-Alpha-01 | 裸机 | A100 | 2 | full execute + partial release |
| e2e_alpha_applicant_02 | Alpha | E2E-Normal-Alpha-02 | 推理池 | A800 | 2 | full execute |
| e2e_alpha_applicant_03 | Alpha | E2E-Normal-Alpha-03 | 训练池 | H100 | 2 | full execute |
| e2e_beta_applicant_01 | Beta | E2E-Normal-Beta-01 | 裸机 | H200 | 2 | full execute + password |
| e2e_beta_applicant_02 | Beta | E2E-Normal-Beta-02 | 开发池 | L40S | 2 | full execute |
| e2e_beta_applicant_03 | Beta | E2E-Normal-Beta-03 | 推理池 | A800 | 2 | full execute |
| e2e_gamma_applicant_01 | Gamma | E2E-Normal-Gamma-01 | 训练池 | H100 | 2 | full execute |
| e2e_gamma_applicant_02 | Gamma | E2E-Normal-Gamma-02 | 开发池 | L40S | 2 | full execute |
| e2e_delta_applicant_01 | Delta | E2E-Normal-Delta-01 | 裸机 | A100 | 2 | full execute + partial release |
| e2e_delta_applicant_02 | Delta | E2E-Normal-Delta-02 | 开发池 | L40S | 2 | full execute |

Normal lifecycle checks:

1. Submission:
   - Each applicant logs in and submits their assigned application.
   - Expected:
     - Success message appears.
     - Applicant history contains their own application.
     - Other applicants do not see it in "我的申请记录".
     - Project overview contains all submitted applications.

2. Team leader approval:
   - Each leader logs in and approves applications for their team.
   - Expected:
     - Team-specific pending count decreases.
     - Approved applications move from `PENDING_TEAM` to `PENDING_PRE`.
     - Team leader note is stored and visible in applicant history/details.
     - Leaders cannot approve other teams' applications.

3. Pre-approval allocation:
   - `e2e_pre_approver` logs in.
   - For each application, set allocated count/type/form/region/inventory.
   - Expected:
     - Applications move from `PENDING_PRE` to `PENDING_FINAL`.
     - Allocation details show requested/allocated values.
     - Inventory safe availability badge updates.
     - If stock is sufficient, no coordination panel is required.

4. Department final approval:
   - `e2e_dept_head` logs in.
   - Approves all pre-allocated applications.
   - Expected:
     - Applications move from `PENDING_FINAL` to `APPROVED`.
     - Inventory allocated count increases.
     - Applicant history shows approved status and final approver note.

5. Execution binding:
   - `e2e_executor_full` logs in.
   - For each approved application, bind matching physical assets and mark executed.
   - Expected:
     - Applications move from `APPROVED` to `EXECUTED`.
     - AssetAllocation records exist.
     - Asset status changes to `PARTIAL` or `IN_USE`.
     - Asset owner/current users/app name are updated.
     - Execution result appears in applicant history.

6. Bare-metal password visibility:
   - Bare-metal applicants open application details.
   - Expected:
     - `裸机` allocations show password reveal buttons.
     - Applicant can reveal password for their own executed bare-metal application.
     - Non-owner applicants cannot fetch another user's bare-metal password.
     - Non-bare-metal applications do not expose password columns.

7. Partial release:
   - Executor releases at least two executed applications partially.
   - This is a required validation point. If current UI/backend only supports full release, record it as a P1 functional defect, implement or request product confirmation, then rerun this partial-release validation.
   - Expected for partial release:
     - Released card count decreases from the application allocation.
     - Asset used card count decreases.
     - Asset status changes from `IN_USE` to `PARTIAL` or `IDLE` as appropriate.
     - Inventory allocated count decreases by released count.
     - Application remains logically executed or moves to a partial-release state if implemented.
   - Full release may be tested as an additional regression path, but it does not replace the required partial-release pass criteria.

### C. Emergency Coordination Validation

Initial emergency setup:

- Create a donor executed application:
  - Project: `E2E-Emergency-Donor`
  - Applicant: `e2e_alpha_applicant_01`
  - Form/model: `裸机` / `A100`
  - Allocated count: `2`
  - Bound asset: `E2E-EMERG-A100-Donor-01`
  - Status: `EXECUTED`
- Emergency inventory has total `2`, allocated `2`, available `0`.

Emergency flow:

1. Emergency request submission:
   - Applicant `e2e_delta_applicant_01` submits project `E2E-Emergency-Urgent`.
   - Request: `裸机`, `A100`, count `2`, priority `HIGH`.
   - Expected:
     - Application enters `PENDING_TEAM`.
     - Applicant history shows pending team approval.

2. Team approval:
   - Delta leader approves.
   - Expected:
     - Application moves to `PENDING_PRE`.

3. Pre-approval shortage detection:
   - Pre-approver opens the urgent application.
   - Expected:
     - Inventory badge indicates shortage or no safe availability.
     - Coordination panel appears.
     - Candidate list includes `E2E-Emergency-Donor`.
     - Candidate list excludes same project and excludes mismatched card model/form.

4. Coordination plan selection:
   - Pre-approver chooses to coordinate/preempt 2 cards from donor application.
   - Expected:
     - Coordination details are saved.
     - Urgent application moves to `PENDING_FINAL`.
     - Donor application remains visible as impacted candidate.

5. Department approval:
   - Department head approves urgent application.
   - Expected:
     - Urgent application moves to `APPROVED`.
     - Allocation details still reference A100/裸机.

6. Executor transfer:
   - Executor opens urgent application.
   - Selects donor asset/preempt cards according to coordination plan.
   - Marks urgent application executed.
   - Expected:
     - Urgent application becomes `EXECUTED`.
     - Urgent application gets `AssetAllocation` for transferred cards.
     - Donor application allocation decreases or donor release state updates.
     - Donor asset owner/current users/app name reflect final allocations.
     - Asset `used_cards` equals sum of all active allocations.
     - No negative inventory or over-allocated assets.

7. Post-coordination applicant checks:
   - Urgent applicant can see execution result and bare-metal password.
   - Donor applicant sees changed allocation/release details.
   - Expected:
     - No password leakage between applicants.
     - Coordination result is understandable in execution/result text.

### D. Authentication, Dashboard, and Navigation Validation

1. Role API and login selection:
   - Call `/api/user/roles/?username=<user>` for applicants, leaders, pre-approver, department head, executor, admin, multi-role user, unknown user, and missing username.
   - Expected:
     - Known users return exact role codes and display labels.
     - Unknown/missing users return controlled JSON responses without a server error.
     - Login succeeds only when the selected role belongs to the user.

2. Route access control:
   - Visit `/approve/`, `/execute/`, `/assets/`, `/statistics/`, `/feedback/`, and Django `/admin/` as each role.
   - Expected:
     - Applicants cannot operate approval/execution/admin functions.
     - Team leaders can access approval but only team-scoped actions.
     - Pre-approver and department head see their relevant approval stages.
     - Executor/admin can execute and manage assets.
     - All authenticated roles can view feedback and allowed asset list.

3. Password change and logout:
   - Change password for a disposable user.
   - Logout.
   - Login with old password, then new password.
   - Expected:
     - Old password fails.
     - New password succeeds.
     - Session-only pages redirect to login after logout.

4. Dashboard:
   - Open dashboard for applicant, team leader, pre-approver, department head, executor, and admin.
   - Expected:
     - Inventory totals and sidebar badges match seeded data.
     - Applicant sees only their application outcome notifications.
     - Pending approvers/executors see only actionable notifications for their role/team.
     - No browser console errors.

### E. Application Form, History, and Details Validation

1. Dynamic inventory:
   - Select each configured form/model pair in `/apply/`.
   - Expected:
     - `/api/inventory/` is called with selected form/model.
     - Badge shows the correct available count.
     - Unknown combinations show a controlled "no inventory" state.

2. Form validation:
   - Submit invalid variants: missing project, missing users, `count < 1`, `minCount < 1`, `minCount > count`, end date earlier than start date, and non-image attachment.
   - Expected:
     - Invalid submissions stay on the form with clear validation feedback.
     - No invalid `Application` record is created.

3. User selector:
   - Select existing users through checkboxes.
   - Add a custom user token through manual input.
   - Expected:
     - Hidden `users` value contains all selected names once.
     - Tags and checkbox states remain synchronized after adding/removing users.

4. Project selector:
   - Search by partial keyword.
   - Select a project.
   - Try submitting an unconfigured project name.
   - Expected:
     - Search narrows the dropdown.
     - Hidden project field is populated only after selection.
     - Unconfigured project cannot be submitted.

5. Attachment and pasted screenshot:
   - Upload a valid image attachment.
   - Paste an image into purpose or note field.
   - Clear preview and re-upload.
   - Expected:
     - Preview appears for valid images.
     - Submitted application shows attachment link/thumbnail in history/details.
     - Clearing preview removes the pending upload.

6. Cancellation and history:
   - Cancel one `PENDING_TEAM` application.
   - Attempt cancellation after it moves to `PENDING_PRE`.
   - Expected:
     - Pending-team application becomes `CANCELLED`.
     - Later-stage cancellation is rejected.
     - "我的申请记录" remains applicant-scoped.
     - "项目申请总览" shows all project applications without exposing passwords.

7. Details modal:
   - Open details for normal, rejected, executed, released, coordinated, and attachment-bearing applications.
   - Expected:
     - Workflow notes, allocation details, execution result, attachment, assets, and release/coordination fields render correctly.
     - User-provided text is escaped and cannot execute JavaScript.

### F. Approval, Rejection, Batch, Recall, and Filtering Validation

1. Team approval:
   - Approve and reject individual applications.
   - Batch approve a whole project containing multiple team-owned applications.
   - Expected:
     - Approve moves `PENDING_TEAM -> PENDING_PRE`.
     - Reject moves to `REJECTED` with team note.
     - Batch approval affects only eligible team-owned applications under the project.

2. Team scope:
   - Login as each team leader and inspect pending/history tabs.
   - Try POSTing an approval action for another team's application.
   - Expected:
     - Cross-team application is not visible as actionable.
     - Direct POST is rejected and status is unchanged.

3. Pre-approval:
   - Pre-allocate individual applications.
   - Batch pre-allocate a project.
   - Reject a pre-approval fixture.
   - Expected:
     - Valid allocation moves to `PENDING_FINAL`.
     - Allocation details store inventory id, form, model, region, card name, and count.
     - Reject moves to `REJECTED` without consuming inventory.
     - Insufficient safe inventory opens coordination instead of silently failing.

4. Department final approval:
   - Approve and reject final-stage applications.
   - Batch final approve a project.
   - Expected:
     - Approve moves to `APPROVED` and consumes inventory exactly once.
     - Reject moves to `REJECTED` and returns any pre-reserved inventory.
     - Repeated POSTs do not double-consume inventory.

5. Recall:
   - Team leader recalls `PENDING_PRE` back to `PENDING_TEAM`.
   - Pre-approver recalls `PENDING_FINAL` back to `PENDING_PRE`.
   - Try recall after the next role has already processed the application.
   - Expected:
     - Eligible recall restores the previous stage.
     - Late recall is rejected with status unchanged.

6. Filters and history:
   - Use team/model/project/status filters on `/approve/`.
   - Expected:
     - Pending lists and history lists agree with database state.
     - Empty filters render an empty state, not stale cards.

### G. Execution, Release, Coordination Transfer, and Auto-Release Validation

1. Asset binding:
   - Bind one asset, multiple assets, and partial cards from an asset.
   - Expected:
     - Sum of selected cards cannot exceed approved allocation.
     - Selection must match card type/form/region unless it is a saved coordination candidate.
     - `AssetAllocation` records are unique per asset/application.

2. Actual-card-count adjustment:
   - Execute an application with fewer actual cards than approved.
   - Expected:
     - Application `allocatedCount` or execution record reflects actual count according to current product rule.
     - Surplus inventory is returned.
     - Approval/execution history explains the delta.

3. Full release:
   - Release one fully executed application.
   - Expected:
     - Status becomes `RELEASED`.
     - Inventory allocation returns to available pool.
     - All asset allocations for that application are deleted.
     - Asset `used_cards`, `status`, `owner`, `current_users`, and `app_name` refresh.

4. Partial release:
   - Release only part of an executed application.
   - Expected:
     - This is mandatory. If unsupported, record a P1 defect and implement before claiming full lifecycle support.
     - Released count cannot exceed active allocated count.
     - Remaining allocation stays visible to applicant and executor.
     - Inventory and asset `used_cards` decrease by exactly the released count.

5. Coordination transfer:
   - Execute the urgent application with selected donor/preempted assets.
   - Expected:
     - Donor application, urgent application, asset allocations, and inventory remain internally consistent.
     - Donor applicant can see the impact.
     - Urgent applicant can reveal only their own bare-metal password.

6. Auto-release toggle:
   - Toggle auto-release in execution management as executor/admin.
   - Try toggling as applicant.
   - Expected:
     - Authorized toggle persists in `SystemSetting(auto_release_enabled)`.
     - Unauthorized toggle is rejected.

7. `release_expired_assets` command:
   - Run with setting disabled.
   - Enable setting and run with one expired executed app and one future executed app.
   - Run a second time.
   - Expected:
     - Disabled setting skips changes.
     - Expired app becomes `RELEASED`; inventory/assets return.
     - Future app stays `EXECUTED`.
     - Second run changes nothing.

### H. Asset Management Validation

1. View and filters:
   - Open `/assets/` as applicant, leader, approver, executor, and admin.
   - Filter by keyword/status/model/form/region.
   - Expected:
     - All roles can view the allowed asset list.
     - Filters affect table rows deterministically.
     - CSV export contains the filtered rows and expected columns.

2. CRUD permissions:
   - Add, edit, and delete an idle asset as executor/admin.
   - Try the same POSTs as applicant.
   - Expected:
     - Executor/admin operations succeed.
     - Applicant POSTs are rejected and do not mutate assets.

3. Password permissions:
   - Reveal password on asset page as executor/admin.
   - Call `/assets/password/` as applicant/non-owner/anonymous.
   - Expected:
     - Executor/admin see password.
     - Applicant can reveal only password for their own executed bare-metal application through application details, not the global asset page.
     - Non-owner/anonymous requests fail without leaking password text.

4. Edit preservation and delete protection:
   - Open edit modal while password fetch fails and submit placeholder.
   - Delete an `IN_USE` asset.
   - Expected:
     - Existing encrypted password remains unchanged.
     - In-use asset deletion is blocked until release.

### I. Statistics Validation

1. Default dashboard:
   - Open `/statistics/` with seeded counted applications.
   - Expected:
     - Total applications, total cards, card-days, average duration, and status distribution match database fixtures.

2. Filters:
   - Apply start/end date filter.
   - Apply card model filter.
   - Use quick filters: 7 days, 30 days, 90 days, year.
   - Expected:
     - Charts/tables update to matching records only.
     - Filter reset restores default view.

3. Rankings:
   - Validate team, project, and applicant ranking tables.
   - Expected:
     - Sort order is stable and count/card/card-day values match fixtures.

4. Empty state:
   - Choose a date range with no records.
   - Expected:
     - Page renders a clear no-data state with no JavaScript errors.

### J. Feedback Validation

1. Submit:
   - Submit feedback with title/content only.
   - Submit feedback with multiple valid images.
   - Try empty title/content, invalid file type, and oversized image.
   - Expected:
     - Valid feedback appears in public list.
     - Invalid submissions are rejected and do not create records.

2. Edit/delete:
   - Owner edits pending feedback and deletes another pending feedback.
   - Admin edits/deletes another user's pending feedback.
   - Non-owner applicant tries edit/delete.
   - Expected:
     - Owner/admin operations succeed.
     - Non-owner operations are rejected.

3. Resolve:
   - Executor/admin marks pending feedback resolved.
   - Applicant tries to resolve.
   - Try editing resolved feedback.
   - Expected:
     - Only executor/admin can resolve.
     - Resolved feedback cannot be edited.
     - Images deleted from feedback remove backing files through model signals.

### K. Reminder and Notification Validation

1. Stage receiver selection:
   - Trigger reminder for applications in `PENDING_TEAM`, `PENDING_PRE`, `PENDING_FINAL`, and `APPROVED`.
   - Expected:
     - Receivers are team leader, pre-approver, department head, and executor respectively.
     - JSON response names the receiver accounts.

2. Authorization and ineligible statuses:
   - Trigger reminder as owner applicant, admin, another applicant, and anonymous.
   - Trigger reminder for `EXECUTED`, `REJECTED`, `CANCELLED`, and `RELEASED`.
   - Expected:
     - Owner/admin succeed for eligible states.
     - Other applicant/anonymous fail.
     - Completed or terminal statuses return "无需催办" style response.

3. Notification log and mock endpoint:
   - Use `/mock-notification-api/` and verify `SystemNotificationLog`.
   - Expected:
     - One log exists per receiver.
     - Success/failure state and error message are stored.
     - Admin resend action retries failed logs and updates state.

### L. Admin Back Office Validation

1. System option bulk import:
   - Import valid options, duplicate options, empty lines, and invalid category.
   - Expected:
     - Valid options are created.
     - Duplicates are ignored and reported.
     - Invalid category is rejected.

2. User bulk import and password reset:
   - Import users using tab and comma formats.
   - Import duplicate existing users with missing team/email.
   - Import invalid team and invalid username.
   - Use list action and single-user button to reset password.
   - Expected:
     - Valid users are created with default password `123456`.
     - Existing users are updated only for missing fields.
     - Invalid rows show row-level errors.
     - Reset users can login with `123456`.

3. Inventory admin:
   - Create/edit inventory with valid values.
   - Try negative total and allocated greater than total.
   - Expected:
     - Valid values save.
     - Invalid values show form errors and do not save.

4. Historical application import:
   - Import valid historical rows, header row, invalid team/form/model/project, invalid counts, and optional dates.
   - Expected:
     - Valid rows create applications with mapped status/priority.
     - Invalid option rows fail with row-level errors.
     - Header rows are ignored.

5. Admin application status correction:
   - Change an `APPROVED` or `EXECUTED` application to `RELEASED`, `REJECTED`, or `CANCELLED` in admin.
   - Change a non-consuming application to `APPROVED`.
   - Expected:
     - Consuming-to-non-consuming returns inventory and unbinds assets.
     - Non-consuming-to-consuming increments inventory once.
     - No negative counts or duplicate inventory consumption.

6. Asset bulk import:
   - Import valid assets, invalid model/form/region, invalid owner, and non-positive card count.
   - Expected:
     - Valid assets save with encrypted password.
     - Invalid rows are reported.
     - Non-positive card count falls back to configured default behavior or is rejected according to product decision; either behavior must be documented and stable.

7. Global settings and notification admin:
   - Edit `auto_release_enabled`.
   - Filter/search notification logs.
   - Resend failed reminders.
   - Expected:
     - Settings persist.
     - Log filters/search work.
     - Resend records success/failure accurately.

### M. API, Security, Data Integrity, and Responsive Validation

1. API method and permission matrix:
   - Exercise all JSON endpoints with GET/POST where applicable, anonymous session, wrong owner, allowed owner, executor, admin.
   - Expected:
     - Unsupported methods return controlled 4xx responses.
     - Anonymous users redirect or receive 401/403 JSON.
     - Owner-only endpoints deny other applicants.
     - Password fields appear only in explicitly allowed password endpoints.

2. Data integrity invariants after every lifecycle test:
   - Query database after each major step.
   - Expected:
     - `ResourceInventory.allocatedCount >= 0`.
     - `allocatedCount <= totalCount` for every inventory row.
     - `ResourceAsset.used_cards >= 0`.
     - `used_cards <= card_count` for every asset.
     - Each asset `used_cards` equals the sum of active `AssetAllocation.allocated_cards`.
     - Released/rejected/cancelled applications do not retain active asset allocations.

3. XSS and HTML escaping:
   - Seed malicious text in purpose, priority reason, notes, approval notes, execution results, feedback title/content, asset names, and imported history rows.
   - Expected:
     - Text displays escaped.
     - No injected `img`, `script`, event handler, or global marker executes.

4. Browser console and responsive layout:
   - Run desktop viewport `1440x900`.
   - Run mobile viewport `390x844` for login, apply, approve list, execute list, assets, feedback.
   - Expected:
     - No uncaught client errors.
     - Primary content remains readable and actionable.
     - Modals scroll and buttons stay within viewport.

## Automation Design

### Helper Functions To Add

In `tests/e2e/resource-management.spec.js`:

- `submitApplication(page, application)`
  - Already exists in current tests, extend it for the comprehensive data set.

- `approveTeamApplications(page, leaderUser, expectedProjects)`
  - Login as team leader.
  - Open `/approve/`.
  - Approve each project.
  - Assert projects leave team pending state.

- `preApproveApplication(page, project, allocation)`
  - Login as pre-approver.
  - Open `/approve/`.
  - Fill allocation form.
  - Submit pre-approval.
  - Assert `PENDING_FINAL`.

- `finalApproveApplication(page, project)`
  - Login as department head.
  - Open `/approve/`.
  - Approve final allocation.
  - Assert `APPROVED`.

- `executeApplication(page, project, assetSelections, resultText)`
  - Login as executor.
  - Open `/execute/`.
  - Select matching assets and card counts.
  - Submit execution.
  - Assert `EXECUTED`.

- `releaseApplication(page, project)`
  - Login as executor.
  - Open `/execute/?tab=history`.
  - Release application.
  - Assert inventory/asset/application post-state.

- `assertApplicationStatusViaDetails(page, applicant, project, expectedStatus)`
  - Login as applicant.
  - Open history.
  - Open details modal.
  - Assert status, allocated resource, assets, and password visibility.

- `assertNoConsoleErrors(page)`
  - Attach `page.on('console')` and `page.on('pageerror')`.
  - Ignore known benign favicon/network noise only when explicitly documented.
  - Assert the captured error list is empty before the test ends.

- `assertDbInvariants(label)`
  - Call a Django test helper or management script after critical workflows.
  - Assert inventory and asset allocation invariants listed in section M.

- `triggerReminder(page, project)`
  - Open applicant history/details or POST `/remind/`.
  - Assert JSON response, visible toast, and notification log side effects.

- `assertApiDenied(request, endpoint, params)`
  - Call protected APIs as anonymous/wrong-role/wrong-owner.
  - Assert status and payload contain no sensitive data.

- `adminBulkImport(page, modelPath, bulkText, expectedMessage)`
  - Login as admin.
  - Open the custom `bulk-import/` page.
  - Submit tab/comma-separated rows.
  - Assert success/warning/error messages and database result.

### New E2E Test Cases

1. `admin configured options and roles are available in UI`
   - Validates system options, users, and role API.

2. `ten applicants complete normal application approval execution and release lifecycle`
   - End-to-end normal workflow for the ten applications.

3. `emergency request coordinates executed same-card resources through full lifecycle`
   - End-to-end emergency coordination workflow.

4. `cross-user access controls remain isolated after full lifecycle`
   - Password/API/detail access checks after execution and release.

5. `authentication dashboard navigation and password change work by role`
   - Login/logout, selected role validation, dashboard notifications, sidebar badges, and change password.

6. `application form validates dynamic inventory users projects dates counts and attachments`
   - Valid and invalid submit variants, paste/upload preview, project/user selectors, cancellation, details modal.

7. `approval supports reject batch recall filters and direct-post authorization checks`
   - Individual and batch approvals/rejections, team/pre recall, filtered lists, negative POSTs.

8. `execution validates asset binding actual count full release partial release and auto-release toggle`
   - Asset binding constraints, surplus return, full release, required partial release, toggle permission.

9. `asset management permissions filters csv passwords edit preservation and delete guard work`
   - Asset list and CRUD matrix across roles.

10. `statistics filters rankings and empty state match seeded data`
    - Date/model/quick filters and rank table totals.

11. `feedback submit edit delete resolve image permission and resolved-lock lifecycle works`
    - Owner/admin/executor/non-owner matrix.

12. `reminders route to correct handlers and notification logs can be resent`
    - Stage receiver selection, mock endpoint, log state, admin resend.

13. `json APIs enforce method ownership and sensitive-field rules`
    - Inventory/details/password/user-role/mock API positive and negative coverage.

14. `mobile role pages remain usable without console errors`
    - Mobile viewport smoke for critical pages and modals.

### New Django Test Cases

1. `resource_app.tests.test_admin_imports.AdminImportTests`
   - `test_system_option_bulk_import_accepts_valid_and_reports_duplicates`
   - `test_user_bulk_import_validates_team_and_updates_existing_missing_fields`
   - `test_admin_password_reset_single_and_bulk_sets_default_password`
   - `test_application_history_bulk_import_maps_status_priority_and_rejects_invalid_options`
   - `test_asset_bulk_import_validates_form_model_region_owner_and_password_encryption`

2. `resource_app.tests.test_admin_side_effects.AdminSideEffectTests`
   - `test_inventory_form_rejects_negative_total`
   - `test_inventory_form_rejects_allocated_greater_than_total`
   - `test_admin_status_change_from_executed_to_released_returns_inventory_and_assets`
   - `test_admin_status_change_from_pending_to_approved_consumes_inventory_once`

3. `resource_app.tests.test_release_expired_assets.ReleaseExpiredAssetsTests`
   - `test_command_skips_when_auto_release_disabled`
   - `test_command_releases_only_overdue_executed_applications`
   - `test_command_is_idempotent`

4. `resource_app.tests.test_api_permissions.ApiPermissionTests`
   - `test_application_details_owner_admin_and_denied_users`
   - `test_asset_password_executor_admin_owner_and_denied_users`
   - `test_inventory_api_unknown_combination`
   - `test_mock_notification_api_validates_method_and_payload`

### Execution Phases

1. Phase 0: Seed and configuration smoke
   - Run seed script.
   - Verify admin/options/users/inventory/assets baseline.

2. Phase 1: Auth, dashboard, navigation, and API permission smoke
   - Prove every role can enter only intended surfaces.
   - Prove password change/logout/session behavior.

3. Phase 2: Admin back-office tests
   - Run Django admin import/reset/status/setting tests.
   - Fix data-integrity defects before browser lifecycle execution.

4. Phase 3: Application submit surface
   - Dynamic inventory, selectors, attachments, validation, cancellation, details.

5. Phase 4: Normal ten-applicant lifecycle
   - Submit all ten applications and drive them through team approval, pre-approval, final approval, execution, password visibility, full release, and mandatory partial release.

6. Phase 5: Emergency coordination lifecycle
   - Shortage, donor candidate list, coordination plan, final approval, execution transfer, donor impact.

7. Phase 6: Supporting product modules
   - Assets, statistics, feedback, reminders, notification logs.

8. Phase 7: Scheduled release and regression pack
   - Management command, idempotence, XSS/security, mobile, full Playwright suite.

## Traceability Table

| System surface | Validation coverage |
|---|---|
| `/login/` | Role selection, invalid role, password change regression, logout redirect |
| `/api/user/roles/` | Role payloads for all seeded users, unknown user, missing username |
| `/` dashboard | Role-specific counts, notifications, inventory summaries, console errors |
| `/apply/` | Submit, validation, dynamic inventory, project search, user selector, attachments, cancel, history, overview, details, remind trigger |
| `/approve/` | Single/batch approve, reject, pre-allocation, final approval, coordination, recall, filters, history, direct POST permission checks |
| `/execute/` | Asset binding, actual count adjustment, full release, partial release, auto-release toggle, coordination transfer, history |
| `/assets/` | View/filter/export, add/edit/delete, in-use delete guard, password visibility permissions |
| `/statistics/` | Default metrics, date/card/quick filters, rankings, empty state |
| `/feedback/` | Submit/edit/delete/resolve/image lifecycle and permission matrix |
| `/remind/` | Stage receiver selection, owner/admin authorization, terminal status rejection, notification logs |
| `/mock-notification-api/` | Method/payload handling and integration with notification log send/resend |
| `/api/inventory/` | Known/unknown form-model combinations and safe availability values |
| `/api/application/details/` | Owner/admin/role access, assets, attachments, escaping, no password leakage |
| `/assets/password/` | Executor/admin password access, applicant owner-only bare-metal access, non-owner denial |
| Django admin `CustomUserAdmin` | Multi-role display/filter, bulk import, single and bulk password reset |
| Django admin `SystemOptionAdmin` | Bulk import, duplicate handling, invalid category handling |
| Django admin `ResourceInventoryAdmin` | Dynamic option fields, negative/over-allocated validation |
| Django admin `ApplicationAdmin` | Historical import, status mapping, inventory/asset side effects on status correction |
| Django admin `ResourceAssetAdmin` | Bulk import, option/owner validation, encrypted password storage |
| Django admin `IssueFeedbackAdmin` | Feedback/image inline visibility and admin ownership operations |
| Django admin `SystemSettingAdmin` | `auto_release_enabled` persistence |
| Django admin `SystemNotificationLogAdmin` | Filtering/search and resend failed notifications |
| Management command `release_expired_assets` | Disabled skip, overdue release, future ignored, idempotence |
| Data model signals | Attachment/feedback image cleanup and option rename propagation |

## Current Coverage Self-Check

Existing Playwright coverage already includes these regression protections:

- Role API login smoke and applicant dashboard render.
- Multiple applicants submitting multiple applications without history leakage.
- Role primary pages render without client errors.
- Mobile applicant apply page usability.
- Approver shortage badge rendering.
- Emergency same-card preempt candidate visibility for executed donor applications.
- Executor asset binding for one approved application.
- Applicant bare-metal password reveal for own executed asset.
- Application details XSS escaping.
- Asset filtering and executor password reveal.
- Asset edit password placeholder preservation.
- Feedback submit and executor resolve smoke.

Coverage still missing and required by this expanded plan:

- The full ten-applicant workflow from submission through leader approval, pre-approval, department approval, execution, and release.
- Mandatory partial release.
- Emergency coordination execution transfer and donor post-impact validation.
- Batch approval/pre-allocation/final approval.
- Team/pre-approver recall.
- Rejection at each approval stage.
- Direct POST authorization checks.
- Password change/logout/invalid role login.
- Application attachment upload and paste behavior.
- Project/user selector negative validation.
- Reminder receiver matrix, mock endpoint integration, and notification resend.
- Statistics filters/rankings/empty state.
- Asset add/delete/export and in-use delete protection.
- Admin bulk imports, password resets, inventory validation, admin status side effects, settings, notification logs.
- Management command `release_expired_assets`.
- JSON API negative permission/method coverage.
- Database invariant assertions after lifecycle operations.
- Feedback edit/delete/image validation and resolved edit lock.
- Option rename/data propagation and file cleanup signals.

## Manual Review Checklist Before Execution

Please review these decisions before validation starts:

- Confirm resource forms: `裸机`, `推理池`, `训练池`, `开发池`.
- Confirm card models: `A100`, `A800`, `H100`, `H200`, `L40S`.
- Confirm partial release semantics:
  - Release by card count, by selected asset, or both.
  - Whether a partially released application remains `EXECUTED` with reduced allocation or moves to a new status such as `PARTIALLY_RELEASED`.
- Confirm whether one global pre-approver/dept head/executor is acceptable, or whether each team needs separate approver/dept/executor accounts.
- Confirm emergency donor behavior:
  - Donor allocation can be reduced.
  - Urgent allocation can reuse donor asset.
  - Donor applicant sees impacted allocation.
- Confirm whether CSV export is an officially supported asset feature or a convenience-only frontend feature; the plan treats it as supported because the current UI exposes it.
- Confirm whether historical imports must create missing applicants automatically; current code attempts this path, so the plan includes it as supported behavior to verify.
- Confirm expected behavior for asset import rows with non-positive card count; current code falls back to 8 cards when the value is absent or invalid.
- Confirm whether `SystemNotificationLog` must create one row per receiver or one row containing all receivers; current code appears receiver-oriented, and the plan expects receiver-level traceability.

## Execution Commands

Targeted Django tests after implementation:

```powershell
python manage.py test resource_app.tests.test_admin_imports resource_app.tests.test_admin_side_effects resource_app.tests.test_release_expired_assets resource_app.tests.test_api_permissions
```

Targeted Playwright tests after implementation:

```powershell
$env:BASE_URL='http://127.0.0.1:8001'
npm run test:e2e -- --grep "comprehensive|emergency|admin|auth|application form|approval|execution|asset|statistics|feedback|reminders|json APIs|mobile" --reporter=list
```

Full verification:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py release_expired_assets
$env:BASE_URL='http://127.0.0.1:8001'
npm run test:e2e -- --reporter=list
```

## Expected Deliverables After Execution

- Updated Playwright suite with comprehensive full-flow tests.
- Django tests covering admin imports, admin side effects, API permissions, and scheduled release.
- Any fixes required by failing tests.
- A summary report listing:
  - Passed flows.
  - Failed/gap flows.
  - Bugs found and fixed.
  - Bugs found but requiring product decision.
  - Feature coverage matrix with pass/fail/not-run status for every row in this document.
  - Data integrity invariant results after normal lifecycle, release, and emergency coordination.
  - Final command outputs.
- Commit pushed to `origin/codex`.

## Known Risks

- Current UI may not support partial release. If so, this validation identifies it as a P1 functional defect, not an acceptable limitation for the requested "部分释放" full lifecycle.
- Emergency coordination UI may require exact selectors that differ by role/state; test implementation uses visible project-scoped containers.
- Running all workflows in one test may be slow. Keep normal lifecycle, emergency lifecycle, and supporting modules in separate describe blocks for debuggability.
- Seed data must not delete non-E2E user data beyond `e2e_` prefixes.
- Admin UI tests can be slower and more brittle than model-level tests. Use Playwright only for custom admin views/actions that must work in browser; use Django tests for pure model/admin side effects.
- Reminder sending is asynchronous. Tests poll notification logs or mock receiver output with a bounded timeout instead of assuming immediate state.
- File upload/paste tests must clean created files from `media/attachments/` and `media/feedback_images/`.

## Review Status

This plan is ready for user review. No validation has been executed from this plan yet.
