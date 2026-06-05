# 资源管理系统全功能端到端验证方案

> **给后续执行该方案的 AI/工程师：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐项执行。所有步骤使用 checkbox（`- [ ]`）语法，执行时需要实时更新状态。

**目标：** 构建并运行一套完整的 Playwright + Django 验证体系，证明物料资源管理系统的所有已支持功能都可以正确工作，覆盖系统配置、登录鉴权、申请、审批、执行、释放、紧急协调、资产管理、统计、反馈、催办、API、后台管理和自动释放。

**架构：** 使用现有 Django 应用和 Playwright E2E 框架。通过 `tests/e2e/seed_e2e_data.py` 固化测试用户、系统选项、库存、资产、申请单和反馈数据；业务主链路通过真实 UI 走完；后台导入、定时释放、API 权限和数据一致性通过 Django 测试补足。验证重点包括表单校验、权限隔离、状态流转、库存变化、资产绑定、裸机密码可见性、部分释放、紧急协调、提醒通知、反馈处理、统计口径和后台数据修正副作用。

**技术栈：** Django、SQLite 测试/开发数据库、Playwright、现有 `npm run test:e2e` 命令、Windows PowerShell。

---

## 范围

本验证必须覆盖当前系统暴露的每个路由、后台能力、API 端点、工作流状态转换和定时命令。三个核心业务场景仍然是验收主线，但所有会影响生产正确性的辅助功能也必须纳入验证。

1. 系统配置：
   - 配置多个资源形态：`裸机`、`推理池`、`训练池`、`开发池`。
   - 配置多个卡型号：`A100`、`A800`、`H100`、`H200`、`L40S`。
   - 配置 4 个团队。
   - 配置 10 个分布在不同团队的申请人。
   - 配置组长、预审人、部门负责人、执行人、管理员账号。
   - 配置普通流程和紧急流程所需库存与物理资产。

2. 正常申请流程：
   - 10 个申请人分别提交物料申请。
   - 各团队组长按团队归属审批。
   - 预审人完成资源预分配。
   - 部门负责人完成终审。
   - 执行人绑定资产并标记已执行。
   - 申请人在详情中看到执行结果，裸机场景可看到裸机密码。
   - 执行人完成部分释放，库存和资产同步更新。

3. 紧急协调流程：
   - 1 个用户提交紧急项目申请，当前空闲库存不足。
   - 系统展示相同卡型号、已执行/已审批申请单作为可协调候选。
   - 预审人制定协调/抽调方案。
   - 部门负责人终审通过。
   - 执行人完成资源转移。
   - 被抽调申请单和紧急申请单都展示正确的卡数、资产和后续状态。

4. 支撑平台功能：
   - 登录、角色选择、改密、退出、未授权访问处理。
   - 首页看板、库存卡片、状态提醒、侧边栏计数。
   - 申请页动态库存、项目搜索、使用人多选/自定义、附件上传/粘贴预览、表单校验、历史、项目总览、撤回、催办、详情弹窗。
   - 审批页单笔/批量审批、驳回、预分配、终审、撤回、筛选、历史、紧急协调。
   - 执行页资产绑定、实际执行卡数调整、全量释放、部分释放、自动释放开关、协调执行。
   - 资产管理查看/筛选/导出/新增/编辑/删除/密码权限。
   - 统计页筛选、排行榜、空状态和快捷时间范围。
   - 问题反馈提交、编辑、删除、解决、图片权限。
   - 催办接口接收人选择、通知日志、模拟通知接口、后台重发。
   - JSON API：库存、申请详情、资产密码、用户角色。
   - Django 后台：选项/用户/历史申请/资产批量导入，密码重置，库存校验，申请单状态修正副作用，全局设置，通知日志。
   - 管理命令 `release_expired_assets`。

## 完整功能覆盖矩阵

| 功能域 | 代码中已发现的支持能力 | 验证方式 | 必须通过的断言 |
|---|---|---|---|
| 登录与会话 | 按角色登录、`/api/user/roles/`、退出、修改密码 | Playwright UI + API 请求 | 角色列表准确；用户不能选择自己没有的角色进入系统；新密码可登录；旧密码失败；退出后会话失效 |
| 首页看板 | 库存摘要、申请状态卡片、角色通知、侧边栏计数 | 各角色 Playwright UI 检查 | 计数与种子数据一致；申请人只看到自己的结果提醒；审批/执行提醒只给当前角色可处理事项 |
| 系统选项 | 团队、卡形态、卡型号、项目、地域 | 种子数据 + UI 下拉检查 | 四个团队和所有形态/型号/地域/项目出现在申请、后台库存、后台资产表单中 |
| 用户与角色 | 多角色用户、团队归属、后台重置密码、用户批量导入 | Django 后台 UI 测试 + API 检查 | 导入用户获得正确角色/团队/邮箱；重复导入补全缺失字段；无效团队被拒绝；重置后可用 `123456` 登录 |
| 库存 | 动态库存、安全可用量、后台库存校验 | Playwright UI/API + Django 表单/模型检查 | 可用量等于 `totalCount - allocatedCount`；负库存和已分配大于总数被拒绝；分配/释放不会导致负数 |
| 申请提交 | 新建申请、项目搜索、使用人多选/自定义、附件、粘贴预览、日期/数量校验 | Playwright UI 测试 | 合法申请可提交；非法数量/日期/项目/空使用人被拦截；附件可预览并持久化；历史记录按申请人隔离 |
| 申请历史/详情 | 我的历史、项目总览、撤回待审批申请、详情弹窗、附件链接、裸机密码查看 | Playwright UI/API 检查 | 只看到自己的“我的申请记录”；项目总览展示所有项目申请但不泄露密码；详情文本转义；本人可查看自己的裸机密码 |
| 审批工作流 | 组长审批/驳回/批量审批，预审/驳回/批量预分配，终审/驳回/批量终审，组长/预审撤回，筛选和历史 | 按角色 Playwright 全流程测试 | 仅授权角色可操作；组长按团队隔离；状态严格按 `PENDING_TEAM -> PENDING_PRE -> PENDING_FINAL -> APPROVED` 流转；驳回终止流程；撤回回到上一阶段 |
| 紧急协调 | 短缺检测、相同卡型号已执行/已审批候选、候选排除、协调详情、被抽调方影响 | Playwright 全流程 + 数据库不变量检查 | 候选包含合格 donor，排除同项目/型号或形态不匹配申请；方案持久化；执行后资产和卡数无超分配 |
| 执行 | 绑定资产、选择卡数、被抽调资产、实际卡数少于审批数、释放、自动释放开关 | Playwright UI + 数据库断言 | 生成资产分配明细；资产状态/已用卡数/责任人/使用人/应用名刷新；多余库存归还；释放解绑资产；开关持久化 |
| 部分释放 | 按卡数或按资产释放已执行申请的一部分 | Playwright 测试；当前不支持则作为 P1 缺陷 | 部分释放是必过项：申请分配数、库存、资产已用卡数、状态、申请详情都必须体现剩余分配 |
| 资产管理 | 所有角色查看/筛选/CSV 导出；执行人/管理员新增编辑删除；密码查看；加密密码保留；使用中资产禁止删除 | Playwright UI/API 检查 | 非执行人不能变更资产或查看全局资产密码；执行人/管理员可管理；编辑占位符不清空密码；使用中资产删除被拦截 |
| 统计 | 日期/卡型号筛选、7/30/90 天/全年快捷筛选、状态汇总、团队/项目/申请人排行、空状态 | Playwright UI + 数据库种子校验 | 过滤后的总数与种子数据一致；排行稳定；无数据区间展示干净空状态 |
| 问题反馈 | 提交反馈、图片上传、编辑待处理反馈、本人/管理员删除、执行人/管理员解决、公开列表 | Playwright UI 检查 | 必填和图片类型/大小校验生效；只有本人/管理员能编辑删除；已解决反馈不可编辑；执行人/管理员可标记解决 |
| 催办 | `/remind/`、各流程阶段接收人选择、模拟通知接口、通知日志、后台重发失败通知 | Playwright API/UI + Django 后台检查 | 申请人/管理员可催办符合条件申请；无权用户失败；终态申请提示无需催办；日志持久化；重发更新日志状态 |
| JSON API | `/api/inventory/`、`/api/application/details/`、`/assets/password/`、`/api/user/roles/`、`/mock-notification-api/` | Playwright `request` API 测试 | HTTP 方法和状态码受控；未授权/非本人数据访问被拒绝；返回字段符合预期且不泄露密码 |
| 后台申请数据 | 历史申请批量导入、后台状态修正引发库存/资产副作用 | Django 后台 UI 测试 + 模型断言 | 合法行导入；无效选项带行号报错；从占用状态改为释放/驳回/撤回会归还库存并解绑资产 |
| 后台资产/选项/设置 | 选项批量导入、资产批量导入、全局设置、通知日志后台 | Django 后台 UI 测试 | 重复选项忽略；非法类别拒绝；资产校验形态/型号/地域/责任人；设置持久化；失败通知可重发 |
| 定时释放 | `release_expired_assets` 管理命令 | Django 测试调用命令 | 开关关闭时跳过；开关开启时释放已超期已执行申请；未超期申请不变；命令幂等 |
| 安全与稳定 | XSS 转义、CSRF/方法校验、跨用户隔离、无控制台错误、响应式布局 | Playwright 桌面/移动端检查 + API 反向测试 | 用户输入作为文本渲染；受保护 POST 需要权限和登录；无前端 JS 错误；移动端核心流程可用 |

## 文件改动规划

- 修改：`tests/e2e/seed_e2e_data.py`
  - 增加确定性的用户、团队、系统选项、库存、资产和申请单。
  - 保留现有 E2E 回归测试依赖的基础数据。
  - 增加团队、用户、资源、普通流程、紧急流程、驳回、撤回、催办、自动释放、统计、后台导入等场景常量。

- 修改：`tests/e2e/resource-management.spec.js`
  - 增加登录、后台、申请、审批、执行、释放、资产、统计、反馈、催办、API、移动端等辅助函数。
  - 增加系统配置、正常全流程、紧急协调、权限隔离、资产、统计、反馈、提醒、API 权限、后台 UI 和响应式测试。
  - 保留已有回归测试。

- 新增或修改 Django 测试：
  - `resource_app/tests/test_admin_imports.py`
    - 后台批量导入选项、用户、历史申请、资产。
    - 后台单个和批量重置密码。
  - `resource_app/tests/test_admin_side_effects.py`
    - 库存表单校验。
    - 后台修改申请状态后的库存/资产副作用。
  - `resource_app/tests/test_release_expired_assets.py`
    - `release_expired_assets` 命令。
  - `resource_app/tests/test_api_permissions.py`
    - JSON API 的权限、方法和敏感字段覆盖。

- 初始阶段不直接修改业务代码。
  - 如果测试暴露缺陷，按 TDD 处理：保留失败测试，最小范围修复业务代码，先跑目标测试，再跑全量验证。

## 测试数据设计

### 团队

配置四个团队：

- `E2E-Alpha团队`
- `E2E-Beta团队`
- `E2E-Gamma团队`
- `E2E-Delta团队`

### 用户

所有用户默认密码为 `TestPass123!`。

申请人：

- `e2e_alpha_applicant_01`，团队 `E2E-Alpha团队`
- `e2e_alpha_applicant_02`，团队 `E2E-Alpha团队`
- `e2e_alpha_applicant_03`，团队 `E2E-Alpha团队`
- `e2e_beta_applicant_01`，团队 `E2E-Beta团队`
- `e2e_beta_applicant_02`，团队 `E2E-Beta团队`
- `e2e_beta_applicant_03`，团队 `E2E-Beta团队`
- `e2e_gamma_applicant_01`，团队 `E2E-Gamma团队`
- `e2e_gamma_applicant_02`，团队 `E2E-Gamma团队`
- `e2e_delta_applicant_01`，团队 `E2E-Delta团队`
- `e2e_delta_applicant_02`，团队 `E2E-Delta团队`

组长：

- `e2e_alpha_leader`，角色 `TEAM_LEADER`，团队 `E2E-Alpha团队`
- `e2e_beta_leader`，角色 `TEAM_LEADER`，团队 `E2E-Beta团队`
- `e2e_gamma_leader`，角色 `TEAM_LEADER`，团队 `E2E-Gamma团队`
- `e2e_delta_leader`，角色 `TEAM_LEADER`，团队 `E2E-Delta团队`

跨团队角色：

- `e2e_pre_approver`，角色 `APPROVER`
- `e2e_dept_head`，角色 `DEPT_HEAD`
- `e2e_executor_full`，角色 `EXECUTOR`
- `e2e_admin_full`，角色 `ADMIN`，同时是 superuser/staff

保留已有用户：

- `e2e_applicant`
- `e2e_approver`
- `e2e_executor`

这些已有用户被当前回归测试依赖，种子脚本不能删除。

### 系统选项

新增或确认以下选项：

- `TEAM`：四个 E2E 团队，加现有 `平台团队`。
- `CARD_FORM`：`裸机`、`推理池`、`训练池`、`开发池`。
- `CARD_TYPE`：`A100`、`A800`、`H100`、`H200`、`L40S`。
- `REGION`：`北京`、`上海`、`深圳`。
- `PROJECT`：普通流程项目、紧急流程项目、驳回/撤回/提醒/统计专用项目。

### 库存

普通流程库存：

- `E2E-A100-BareMetal-Beijing`：`裸机`、`A100`、`北京`，总数 `12`，已分配 `0`。
- `E2E-A800-Inference-Shanghai`：`推理池`、`A800`、`上海`，总数 `10`，已分配 `0`。
- `E2E-H100-Training-Beijing`：`训练池`、`H100`、`北京`，总数 `8`，已分配 `0`。
- `E2E-H200-BareMetal-Shenzhen`：`裸机`、`H200`、`深圳`，总数 `8`，已分配 `0`。
- `E2E-L40S-Dev-Beijing`：`开发池`、`L40S`、`北京`，总数 `12`，已分配 `0`。

紧急流程库存：

- `E2E-Emergency-A100-Beijing`：`裸机`、`A100`、`北京`，总数 `2`，已分配 `2`，可用 `0`。

### 物理资产

A100 裸机：

- `E2E-FULL-A100-Node-01`，4 卡，密码 `full-a100-secret-01`。
- `E2E-FULL-A100-Node-02`，4 卡，密码 `full-a100-secret-02`。
- `E2E-FULL-A100-Node-03`，4 卡，密码 `full-a100-secret-03`。

A800 推理池：

- `E2E-FULL-A800-Pool-01`，5 卡。
- `E2E-FULL-A800-Pool-02`，5 卡。

H100 训练池：

- `E2E-FULL-H100-Train-01`，4 卡。
- `E2E-FULL-H100-Train-02`，4 卡。

H200 裸机：

- `E2E-FULL-H200-Node-01`，4 卡，密码 `full-h200-secret-01`。
- `E2E-FULL-H200-Node-02`，4 卡，密码 `full-h200-secret-02`。

L40S 开发池：

- `E2E-FULL-L40S-Dev-01`，4 卡。
- `E2E-FULL-L40S-Dev-02`，4 卡。
- `E2E-FULL-L40S-Dev-03`，4 卡。

紧急协调 donor：

- `E2E-EMERG-A100-Donor-01`，2 卡，初始已绑定到已执行 donor 申请。

### 额外场景数据

为避免影响 10 个正常申请，额外创建专用数据：

- 驳回场景：
  - `E2E-Reject-Team`：状态 `PENDING_TEAM`，验证组长驳回。
  - `E2E-Reject-Pre`：状态 `PENDING_PRE`，验证预审驳回。
  - `E2E-Reject-Final`：状态 `PENDING_FINAL`，验证终审驳回和库存不占用。

- 撤回场景：
  - `E2E-Recall-Team`：先从 `PENDING_TEAM` 推进到 `PENDING_PRE`，再由组长撤回。
  - `E2E-Recall-Pre`：先从 `PENDING_PRE` 推进到 `PENDING_FINAL`，再由预审人撤回。

- 催办场景：
  - 分别准备 `PENDING_TEAM`、`PENDING_PRE`、`PENDING_FINAL`、`APPROVED` 阶段申请。
  - 额外准备 `EXECUTED` 申请作为“无需催办”反向用例。

- 自动释放场景：
  - `E2E-AutoRelease-Expired`：`EXECUTED`，`endDate` 早于测试日期，已绑定资产且占用库存。
  - `E2E-AutoRelease-Future`：`EXECUTED`，未来 `endDate`，已绑定资产且占用库存。

- 统计场景：
  - 至少覆盖两个创建日期、三个团队、三个卡型号，以及 `APPROVED`、`EXECUTED`、`RELEASED` 三类统计状态。

- 资产管理场景：
  - 1 个 `IDLE` 资产，用于新增/编辑/删除。
  - 1 个 `IN_USE` 资产，带分配明细，用于删除保护。
  - 1 个 `FAULT` 资产，用于筛选/状态验证。

- 反馈场景：
  - 1 条当前申请人自己的待处理反馈。
  - 1 条当前申请人自己的已解决反馈。
  - 1 条其他申请人的待处理反馈。

- API 安全场景：
  - 1 个当前申请人自己的裸机已执行申请。
  - 1 个其他申请人的裸机已执行申请。
  - 1 个非裸机已执行申请，带资产分配。

## 验证点

### A. 系统配置验证

1. 管理员登录：
   - 使用 `e2e_admin_full` 登录。
   - 预期：看板加载成功，后台/管理员入口可见。

2. 选项配置：
   - 验证申请表单和后台表单中存在 `TEAM`、`CARD_FORM`、`CARD_TYPE`、`REGION`、`PROJECT`。
   - 预期：
     - 团队下拉包含四个 E2E 团队。
     - 卡形态包含 `裸机`、`推理池`、`训练池`、`开发池`。
     - 卡型号包含 `A100`、`A800`、`H100`、`H200`、`L40S`。
     - 项目选择器包含普通项目和紧急项目。

3. 用户角色配置：
   - 调用登录角色 API。
   - 预期：
     - 申请人只返回 `APPLICANT`。
     - 组长返回 `TEAM_LEADER`。
     - 预审人返回 `APPROVER`。
     - 部门负责人返回 `DEPT_HEAD`。
     - 执行人返回 `EXECUTOR`。
     - 管理员返回 `ADMIN`。

4. 团队归属：
   - 各组长进入审批页。
   - 预期：
     - Alpha 组长只看到 Alpha 团队申请。
     - Beta 组长只看到 Beta 团队申请。
     - 不出现跨团队可审批数据。

5. 库存和资产：
   - 资产页展示配置的物理资产。
   - 首页和库存相关区域展示配置的库存总数。
   - 预期：
     - A100/A800/H100/H200/L40S 库存行存在。
     - 初始资产数量和状态正确。

### B. 正常完整生命周期验证

通过 UI 提交以下 10 个申请：

| 申请人 | 团队 | 项目 | 形态 | 型号 | 数量 | 验证轨道 |
|---|---|---|---|---|---:|---|
| `e2e_alpha_applicant_01` | Alpha | `E2E-Normal-Alpha-01` | 裸机 | A100 | 2 | 执行 + 部分释放 |
| `e2e_alpha_applicant_02` | Alpha | `E2E-Normal-Alpha-02` | 推理池 | A800 | 2 | 执行 |
| `e2e_alpha_applicant_03` | Alpha | `E2E-Normal-Alpha-03` | 训练池 | H100 | 2 | 执行 |
| `e2e_beta_applicant_01` | Beta | `E2E-Normal-Beta-01` | 裸机 | H200 | 2 | 执行 + 密码 |
| `e2e_beta_applicant_02` | Beta | `E2E-Normal-Beta-02` | 开发池 | L40S | 2 | 执行 |
| `e2e_beta_applicant_03` | Beta | `E2E-Normal-Beta-03` | 推理池 | A800 | 2 | 执行 |
| `e2e_gamma_applicant_01` | Gamma | `E2E-Normal-Gamma-01` | 训练池 | H100 | 2 | 执行 |
| `e2e_gamma_applicant_02` | Gamma | `E2E-Normal-Gamma-02` | 开发池 | L40S | 2 | 执行 |
| `e2e_delta_applicant_01` | Delta | `E2E-Normal-Delta-01` | 裸机 | A100 | 2 | 执行 + 部分释放 |
| `e2e_delta_applicant_02` | Delta | `E2E-Normal-Delta-02` | 开发池 | L40S | 2 | 执行 |

正常流程检查：

1. 提交申请：
   - 10 个申请人分别登录并提交对应申请。
   - 预期：
     - 出现提交成功提示。
     - 申请人自己的历史中出现该申请。
     - 其他申请人的“我的申请记录”中不出现该申请。
     - 项目总览中能看到所有已提交申请。

2. 组长审批：
   - 各组长审批本团队申请。
   - 预期：
     - 待审批数量减少。
     - 状态从 `PENDING_TEAM` 变为 `PENDING_PRE`。
     - 组长意见被保存并可在申请详情看到。
     - 组长不能审批其他团队申请。

3. 资源预审：
   - `e2e_pre_approver` 登录。
   - 对每个申请设置分配数量、形态、型号、地域、库存来源。
   - 预期：
     - 状态从 `PENDING_PRE` 变为 `PENDING_FINAL`。
     - 详情中展示申请值和分配值。
     - 库存安全可用量提示更新。
     - 库存充足时不要求协调方案。

4. 部门终审：
   - `e2e_dept_head` 登录并批准所有预分配申请。
   - 预期：
     - 状态从 `PENDING_FINAL` 变为 `APPROVED`。
     - 库存已分配数量增加。
     - 申请历史展示终审通过和终审意见。

5. 执行绑定：
   - `e2e_executor_full` 登录。
   - 为每个已审批申请绑定匹配资产并标记已执行。
   - 预期：
     - 状态从 `APPROVED` 变为 `EXECUTED`。
     - 生成 `AssetAllocation`。
     - 资产状态变为 `PARTIAL` 或 `IN_USE`。
     - 资产责任人、当前使用人、应用名刷新。
     - 申请人历史中展示执行结果。

6. 裸机密码可见性：
   - 裸机申请人打开详情。
   - 预期：
     - 裸机分配展示密码查看按钮。
     - 申请人可以查看自己已执行裸机资产密码。
     - 非本人不能获取其他申请人的裸机密码。
     - 非裸机申请不展示密码字段。

7. 部分释放：
   - 执行人对至少两个已执行申请做部分释放。
   - 预期：
     - 这是强制验证点。若当前 UI/后端只支持全量释放，记录为 P1 功能缺陷，必须实现或等待产品确认后再宣称完整生命周期通过。
     - 已释放卡数从申请分配中扣减。
     - 资产已用卡数扣减。
     - 资产状态按剩余使用量变为 `PARTIAL` 或 `IDLE`。
     - 库存已分配数量按释放数量减少。
     - 申请保持已执行的剩余分配状态，或进入产品确认后的部分释放状态。
   - 全量释放可以作为额外回归路径，但不能替代部分释放验收。

### C. 紧急协调验证

初始紧急数据：

- 创建 donor 已执行申请：
  - 项目：`E2E-Emergency-Donor`
  - 申请人：`e2e_alpha_applicant_01`
  - 形态/型号：`裸机` / `A100`
  - 分配数量：`2`
  - 绑定资产：`E2E-EMERG-A100-Donor-01`
  - 状态：`EXECUTED`
- 紧急库存总量 `2`，已分配 `2`，可用 `0`。

紧急流程：

1. 紧急申请提交：
   - `e2e_delta_applicant_01` 提交项目 `E2E-Emergency-Urgent`。
   - 申请：`裸机`、`A100`、数量 `2`、优先级 `HIGH`。
   - 预期：申请进入 `PENDING_TEAM`，申请人历史显示待组长审批。

2. 组长审批：
   - Delta 组长批准。
   - 预期：状态变为 `PENDING_PRE`。

3. 预审短缺检测：
   - 预审人打开紧急申请。
   - 预期：
     - 库存提示短缺或安全可用量为 0。
     - 协调面板出现。
     - 候选列表包含 `E2E-Emergency-Donor`。
     - 候选列表排除同项目、不同型号、不同形态申请。

4. 选择协调方案：
   - 预审人选择从 donor 申请协调/抽调 2 卡。
   - 预期：
     - 协调详情被保存。
     - 紧急申请进入 `PENDING_FINAL`。
     - donor 申请仍可作为受影响候选查看。

5. 部门终审：
   - 部门负责人批准紧急申请。
   - 预期：紧急申请变为 `APPROVED`，分配详情仍是 A100/裸机。

6. 执行转移：
   - 执行人打开紧急申请。
   - 按协调方案选择 donor 资产或被抽调卡数。
   - 标记紧急申请已执行。
   - 预期：
     - 紧急申请变为 `EXECUTED`。
     - 紧急申请获得转移后的 `AssetAllocation`。
     - donor 申请分配减少，或进入产品定义的被释放/被抽调状态。
     - donor 资产责任人、使用人、应用名反映最终分配。
     - 资产 `used_cards` 等于所有活跃分配明细之和。
     - 库存和资产不存在负数或超分配。

7. 协调后申请人检查：
   - 紧急申请人查看执行结果和裸机密码。
   - donor 申请人查看分配变化。
   - 预期：
     - 不发生跨申请人密码泄露。
     - 执行结果或详情中能理解协调结果。

### D. 登录、首页和导航验证

1. 角色 API 与登录选择：
   - 对申请人、组长、预审人、部门负责人、执行人、管理员、多角色用户、未知用户、缺失用户名调用 `/api/user/roles/?username=<user>`。
   - 预期：
     - 已知用户返回准确角色 code 和展示名。
     - 未知/缺失用户返回受控 JSON，不出现服务端错误。
     - 登录时只能选择该用户拥有的角色。

2. 路由权限：
   - 各角色访问 `/approve/`、`/execute/`、`/assets/`、`/statistics/`、`/feedback/`、Django `/admin/`。
   - 预期：
     - 申请人不能操作审批、执行、后台功能。
     - 组长可访问审批页，但只能处理本团队组长环节。
     - 预审人和部门负责人只看到各自阶段。
     - 执行人/管理员可执行和管理资产。
     - 所有登录角色可进入反馈页和被允许的资产列表。

3. 修改密码与退出：
   - 对一次性用户修改密码。
   - 退出登录。
   - 分别用旧密码和新密码登录。
   - 预期：
     - 旧密码失败。
     - 新密码成功。
     - 退出后访问登录态页面会跳转登录页。

4. 首页看板：
   - 申请人、组长、预审人、部门负责人、执行人、管理员分别打开首页。
   - 预期：
     - 库存总数和侧边栏徽标与种子数据一致。
     - 申请人只看到自己的申请结果提醒。
     - 审批人/执行人只看到当前角色可处理提醒。
     - 无浏览器控制台错误。

### E. 申请表单、历史和详情验证

1. 动态库存：
   - 在 `/apply/` 中选择每个已配置形态/型号组合。
   - 预期：
     - `/api/inventory/` 使用所选形态和型号查询。
     - 徽标显示正确可用数量。
     - 未配置组合展示受控的无库存状态。

2. 表单校验：
   - 提交缺项目、缺使用人、`count < 1`、`minCount < 1`、`minCount > count`、结束日期早于开始日期、非图片附件。
   - 预期：
     - 非法提交停留在表单并显示反馈。
     - 不创建非法 `Application` 记录。

3. 使用人选择器：
   - 通过 checkbox 选择已有用户。
   - 通过手动输入添加自定义使用人。
   - 预期：
     - 隐藏 `users` 值包含所有选中名称且不重复。
     - 标签和 checkbox 状态同步。

4. 项目选择器：
   - 通过关键字搜索项目。
   - 选择项目。
   - 尝试提交未配置项目名。
   - 预期：
     - 搜索会收窄下拉列表。
     - 只有选中项目后隐藏 project 字段才有值。
     - 未配置项目不能提交。

5. 附件与粘贴截图：
   - 上传合法图片附件。
   - 在用途或备注字段粘贴图片。
   - 清除预览后重新上传。
   - 预期：
     - 合法图片出现预览。
     - 提交后历史/详情出现附件链接或缩略图。
     - 清除预览会移除待上传文件。

6. 撤回和历史：
   - 撤回一个 `PENDING_TEAM` 申请。
   - 申请进入 `PENDING_PRE` 后再次尝试撤回。
   - 预期：
     - 待组长审批申请变为 `CANCELLED`。
     - 后续阶段撤回被拒绝。
     - “我的申请记录”保持申请人隔离。
     - “项目申请总览”展示全员项目申请，但不泄露密码。

7. 详情弹窗：
   - 打开普通、驳回、已执行、已释放、协调、带附件申请详情。
   - 预期：
     - 流程意见、分配详情、执行结果、附件、资产、释放/协调字段正确展示。
     - 用户输入文本被转义，不能执行 JavaScript。

### F. 审批、驳回、批量、撤回和筛选验证

1. 组长审批：
   - 单笔批准和驳回申请。
   - 对同项目多笔本团队申请批量批准。
   - 预期：
     - 批准使 `PENDING_TEAM -> PENDING_PRE`。
     - 驳回变为 `REJECTED` 并保存组长意见。
     - 批量批准只影响该项目下本团队可处理申请。

2. 团队隔离：
   - 各组长查看待办和历史。
   - 直接 POST 其他团队申请的审批动作。
   - 预期：
     - 跨团队申请不作为待办展示。
     - 直接 POST 被拒绝，状态不变。

3. 预审：
   - 单笔预分配。
   - 按项目批量预分配。
   - 驳回预审场景申请。
   - 预期：
     - 合法分配进入 `PENDING_FINAL`。
     - `allocation_details` 保存库存 id、形态、型号、地域、卡资源名称和数量。
     - 驳回变为 `REJECTED` 且不占用库存。
     - 库存不足时进入协调路径，不能静默失败。

4. 部门终审：
   - 单笔批准和驳回。
   - 按项目批量终审通过。
   - 预期：
     - 批准变为 `APPROVED` 并且库存只占用一次。
     - 驳回变为 `REJECTED`，预占用库存归还。
     - 重复 POST 不会重复扣库存。

5. 撤回：
   - 组长将 `PENDING_PRE` 撤回到 `PENDING_TEAM`。
   - 预审人将 `PENDING_FINAL` 撤回到 `PENDING_PRE`。
   - 下一角色已经处理后尝试撤回。
   - 预期：
     - 符合条件撤回会回到上一阶段。
     - 过期撤回被拒绝且状态不变。

6. 筛选和历史：
   - 在 `/approve/` 使用团队、型号、项目、状态筛选。
   - 预期：
     - 待办和历史列表与数据库状态一致。
     - 无匹配项时展示空状态，而不是旧卡片残留。

### G. 执行、释放、协调转移和自动释放验证

1. 资产绑定：
   - 绑定单个资产、多个资产、资产部分卡数。
   - 预期：
     - 所选卡数总和不能超过审批分配数。
     - 非协调场景必须匹配卡型号/形态/地域。
     - 每个资产和申请之间只生成一条唯一分配明细。

2. 实际执行卡数调整：
   - 用少于审批数的实际卡数执行。
   - 预期：
     - 申请分配数或执行记录按当前产品规则体现实际卡数。
     - 多余库存归还。
     - 审批/执行历史解释差额。

3. 全量释放：
   - 释放一个已执行申请。
   - 预期：
     - 状态变为 `RELEASED`。
     - 库存归还。
     - 该申请的资产分配明细删除。
     - 资产 `used_cards`、`status`、`owner`、`current_users`、`app_name` 刷新。

4. 部分释放：
   - 只释放一个已执行申请的一部分。
   - 预期：
     - 这是强制验收点。若不支持，记录 P1 缺陷，不能宣称全流程通过。
     - 释放数量不能超过当前活跃分配数。
     - 剩余分配仍能被申请人和执行人看到。
     - 库存和资产 `used_cards` 精确扣减释放数量。

5. 协调转移：
   - 使用 donor/被抽调资产执行紧急申请。
   - 预期：
     - donor 申请、紧急申请、资产分配、库存保持一致。
     - donor 申请人能看到影响。
     - 紧急申请人只能查看自己的裸机密码。

6. 自动释放开关：
   - 执行人/管理员在执行管理页切换自动释放。
   - 申请人尝试切换。
   - 预期：
     - 授权切换持久化到 `SystemSetting(auto_release_enabled)`。
     - 未授权切换被拒绝。

7. `release_expired_assets` 命令：
   - 开关关闭时运行。
   - 开启开关后，准备一个已超期已执行申请和一个未来到期已执行申请并运行。
   - 再运行第二次。
   - 预期：
     - 开关关闭时不改数据。
     - 已超期申请变为 `RELEASED`，库存和资产归还。
     - 未到期申请保持 `EXECUTED`。
     - 第二次运行无新增变化。

### H. 资产管理验证

1. 查看与筛选：
   - 申请人、组长、审批人、执行人、管理员访问 `/assets/`。
   - 按关键字、状态、型号、形态、地域筛选。
   - 预期：
     - 所有角色可查看被允许的资产列表。
     - 筛选后表格行确定性变化。
     - CSV 导出包含筛选结果和预期列。

2. CRUD 权限：
   - 执行人/管理员新增、编辑、删除闲置资产。
   - 申请人尝试同样 POST。
   - 预期：
     - 执行人/管理员操作成功。
     - 申请人操作被拒绝且不改数据。

3. 密码权限：
   - 执行人/管理员在资产页查看密码。
   - 申请人、非本人、匿名调用 `/assets/password/`。
   - 预期：
     - 执行人/管理员可看密码。
     - 申请人只能通过申请详情查看自己已执行裸机资产密码，不能通过全局资产页查看。
     - 非本人和匿名请求失败且不泄露密码文本。

4. 编辑保留和删除保护：
   - 密码接口失败时打开编辑弹窗并提交占位符。
   - 删除 `IN_USE` 资产。
   - 预期：
     - 原加密密码保持不变。
     - 使用中资产删除被拦截，必须先释放相关申请。

### I. 统计验证

1. 默认统计：
   - 使用种子数据打开 `/statistics/`。
   - 预期：
     - 总申请数、总卡数、卡天数、平均时长、状态分布与数据库一致。

2. 筛选：
   - 应用开始/结束日期筛选。
   - 应用卡型号筛选。
   - 使用 7 天、30 天、90 天、全年快捷筛选。
   - 预期：
     - 图表和表格只统计匹配记录。
     - 重置筛选恢复默认视图。

3. 排行榜：
   - 校验团队、项目、申请人排行。
   - 预期：
     - 排序稳定。
     - 数量、卡数、卡天数与种子数据一致。

4. 空状态：
   - 选择无记录日期范围。
   - 预期：
     - 页面展示清晰无数据状态。
     - 无 JavaScript 错误。

### J. 问题反馈验证

1. 提交：
   - 提交只有标题和内容的反馈。
   - 提交带多个合法图片的反馈。
   - 尝试空标题/空内容、非法文件类型、超大图片。
   - 预期：
     - 合法反馈出现在公开列表。
     - 非法提交被拒绝且不创建记录。

2. 编辑/删除：
   - 本人编辑待处理反馈并删除另一条待处理反馈。
   - 管理员编辑/删除其他用户待处理反馈。
   - 非本人申请人尝试编辑/删除。
   - 预期：
     - 本人/管理员操作成功。
     - 非本人操作被拒绝。

3. 解决：
   - 执行人/管理员将反馈标记为已解决。
   - 申请人尝试解决。
   - 尝试编辑已解决反馈。
   - 预期：
     - 只有执行人/管理员可解决。
     - 已解决反馈不可编辑。
     - 删除反馈图片时模型信号清理对应文件。

### K. 催办和通知验证

1. 阶段接收人：
   - 对 `PENDING_TEAM`、`PENDING_PRE`、`PENDING_FINAL`、`APPROVED` 申请触发催办。
   - 预期：
     - 接收人分别是组长、预审人、部门负责人、执行人。
     - JSON 响应包含接收账号。

2. 授权和不适用状态：
   - 本人申请人、管理员、其他申请人、匿名用户分别触发催办。
   - 对 `EXECUTED`、`REJECTED`、`CANCELLED`、`RELEASED` 触发催办。
   - 预期：
     - 本人/管理员可催办符合条件申请。
     - 其他申请人/匿名失败。
     - 终态申请返回“无需催办”类响应。

3. 通知日志和模拟接口：
   - 使用 `/mock-notification-api/` 并验证 `SystemNotificationLog`。
   - 预期：
     - 每个接收人都有可追踪日志。
     - 成功/失败状态和错误信息被保存。
     - 后台重发失败日志后状态更新。

### L. Django 后台验证

1. 系统选项批量导入：
   - 导入合法选项、重复选项、空行、非法类别。
   - 预期：
     - 合法选项创建。
     - 重复选项忽略并提示。
     - 非法类别拒绝。

2. 用户批量导入和密码重置：
   - 使用 Tab 和逗号格式导入用户。
   - 对已有用户重复导入以补全团队/邮箱。
   - 导入无效团队和非法用户名。
   - 使用列表 action 和单用户按钮重置密码。
   - 预期：
     - 合法用户创建，默认密码 `123456`。
     - 已有用户只补全缺失字段。
     - 非法行显示行级错误。
     - 重置后可用 `123456` 登录。

3. 库存后台：
   - 新增/编辑合法库存。
   - 尝试负总量、已分配大于总量。
   - 预期：
     - 合法值可保存。
     - 非法值显示表单错误且不保存。

4. 历史申请导入：
   - 导入合法历史行、表头行、非法团队/形态/型号/项目、非法数量、可选日期。
   - 预期：
     - 合法行按状态/优先级映射创建申请。
     - 非法选项行带行级错误。
     - 表头行被忽略。

5. 后台申请状态修正：
   - 将 `APPROVED` 或 `EXECUTED` 申请改为 `RELEASED`、`REJECTED`、`CANCELLED`。
   - 将不占用库存的申请改为 `APPROVED`。
   - 预期：
     - 占用状态转非占用状态会归还库存并解绑资产。
     - 非占用状态转占用状态只增加一次库存占用。
     - 不出现负数或重复占用。

6. 资产批量导入：
   - 导入合法资产、非法型号/形态/地域、非法责任人、非正数卡数。
   - 预期：
     - 合法资产保存且密码加密。
     - 非法行被报告。
     - 非正数卡数按产品确认行为处理；当前代码倾向回退为默认 8 卡，该行为必须稳定并记录。

7. 全局设置和通知后台：
   - 编辑 `auto_release_enabled`。
   - 筛选/搜索通知日志。
   - 重发失败提醒。
   - 预期：
     - 设置持久化。
     - 日志筛选/搜索可用。
     - 重发准确记录成功或失败。

### M. API、安全、数据一致性和响应式验证

1. API 方法和权限矩阵：
   - 对所有 JSON 端点使用 GET/POST、匿名、错误本人、正确本人、执行人、管理员组合验证。
   - 预期：
     - 不支持的方法返回受控 4xx。
     - 匿名用户重定向或收到 401/403 JSON。
     - 本人专属端点拒绝其他申请人。
     - 密码字段只在明确允许的密码接口中出现。

2. 生命周期后的数据不变量：
   - 每个关键步骤后查询数据库。
   - 预期：
     - 每个 `ResourceInventory.allocatedCount >= 0`。
     - 每个库存 `allocatedCount <= totalCount`。
     - 每个 `ResourceAsset.used_cards >= 0`。
     - 每个资产 `used_cards <= card_count`。
     - 每个资产 `used_cards` 等于活跃 `AssetAllocation.allocated_cards` 总和。
     - 已释放/已驳回/已撤回申请不保留活跃资产分配。

3. XSS 和 HTML 转义：
   - 在用途、优先级理由、备注、审批意见、执行结果、反馈标题/内容、资产名称、导入历史行中写入恶意文本。
   - 预期：
     - 文本被转义展示。
     - 不生成注入的 `img`、`script`、事件处理器或全局标记。

4. 控制台错误和响应式：
   - 桌面视口 `1440x900`。
   - 移动端视口 `390x844`，覆盖登录、申请、审批列表、执行列表、资产、反馈。
   - 预期：
     - 无未捕获前端错误。
     - 主要内容可读、可操作。
     - 弹窗可滚动，按钮不超出视口。

## 自动化设计

### Playwright 辅助函数

在 `tests/e2e/resource-management.spec.js` 中补充：

- `submitApplication(page, application)`
  - 扩展现有提交函数，支持完整数据集。

- `approveTeamApplications(page, leaderUser, expectedProjects)`
  - 组长登录。
  - 打开 `/approve/`。
  - 审批指定项目。
  - 断言项目离开组长待办。

- `preApproveApplication(page, project, allocation)`
  - 预审人登录。
  - 打开 `/approve/`。
  - 填写分配表单。
  - 提交预审。
  - 断言进入 `PENDING_FINAL`。

- `finalApproveApplication(page, project)`
  - 部门负责人登录。
  - 打开 `/approve/`。
  - 终审通过。
  - 断言进入 `APPROVED`。

- `executeApplication(page, project, assetSelections, resultText)`
  - 执行人登录。
  - 打开 `/execute/`。
  - 选择匹配资产和卡数。
  - 提交执行。
  - 断言进入 `EXECUTED`。

- `releaseApplication(page, project)`
  - 执行人登录。
  - 打开 `/execute/?tab=history`。
  - 释放申请。
  - 断言库存、资产、申请状态变化。

- `assertApplicationStatusViaDetails(page, applicant, project, expectedStatus)`
  - 申请人登录。
  - 打开历史。
  - 打开详情弹窗。
  - 断言状态、分配资源、资产和密码可见性。

- `assertNoConsoleErrors(page)`
  - 监听 `page.on('console')` 和 `page.on('pageerror')`。
  - 只在明确记录时忽略已知无害 favicon/网络噪声。
  - 测试结束前断言错误列表为空。

- `assertDbInvariants(label)`
  - 通过 Django helper 或管理脚本检查数据不变量。
  - 断言库存和资产分配满足 M 节要求。

- `triggerReminder(page, project)`
  - 从申请历史/详情或 POST `/remind/` 触发催办。
  - 断言 JSON 响应、页面提示、通知日志副作用。

- `assertApiDenied(request, endpoint, params)`
  - 以匿名/错误角色/非本人访问受保护 API。
  - 断言状态码和 payload 不含敏感数据。

- `adminBulkImport(page, modelPath, bulkText, expectedMessage)`
  - 管理员登录。
  - 打开自定义 `bulk-import/` 页面。
  - 提交 Tab/逗号分隔数据。
  - 断言成功/警告/错误消息和数据库结果。

### 新增 Playwright 用例

1. `admin configured options and roles are available in UI`
   - 验证系统选项、用户和角色 API。

2. `ten applicants complete normal application approval execution and release lifecycle`
   - 10 个申请完整走完申请、审批、预审、终审、执行、释放流程。

3. `emergency request coordinates executed same-card resources through full lifecycle`
   - 紧急协调完整生命周期。

4. `cross-user access controls remain isolated after full lifecycle`
   - 执行和释放后继续验证密码、API、详情权限隔离。

5. `authentication dashboard navigation and password change work by role`
   - 登录/退出、角色选择、首页通知、侧边栏计数、修改密码。

6. `application form validates dynamic inventory users projects dates counts and attachments`
   - 动态库存、选择器、附件、校验、撤回、详情。

7. `approval supports reject batch recall filters and direct-post authorization checks`
   - 单笔/批量审批、驳回、撤回、筛选、反向 POST。

8. `execution validates asset binding actual count full release partial release and auto-release toggle`
   - 资产绑定约束、多余库存归还、全量释放、强制部分释放、开关权限。

9. `asset management permissions filters csv passwords edit preservation and delete guard work`
   - 资产列表和 CRUD 权限矩阵。

10. `statistics filters rankings and empty state match seeded data`
    - 日期/型号/快捷筛选和排行榜。

11. `feedback submit edit delete resolve image permission and resolved-lock lifecycle works`
    - 本人/管理员/执行人/非本人权限矩阵。

12. `reminders route to correct handlers and notification logs can be resent`
    - 阶段接收人、模拟接口、日志状态、后台重发。

13. `json APIs enforce method ownership and sensitive-field rules`
    - 库存、详情、密码、角色、模拟通知 API 的正反向覆盖。

14. `mobile role pages remain usable without console errors`
    - 关键页面和弹窗移动端冒烟。

### 新增 Django 测试

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

### 执行阶段

1. Phase 0：种子数据和配置冒烟
   - 运行种子脚本。
   - 验证后台、选项、用户、库存、资产基线。

2. Phase 1：登录、首页、导航、API 权限冒烟
   - 证明每个角色只能进入预期功能面。
   - 证明改密、退出、会话行为正确。

3. Phase 2：后台管理测试
   - 运行后台导入、重置、状态修正、设置测试。
   - 先修复数据一致性缺陷，再执行浏览器生命周期。

4. Phase 3：申请提交面验证
   - 动态库存、选择器、附件、校验、撤回、详情。

5. Phase 4：10 个申请人正常生命周期
   - 提交 10 个申请，并走完组长审批、预审、终审、执行、密码可见性、全量释放、强制部分释放。

6. Phase 5：紧急协调生命周期
   - 短缺、donor 候选、协调方案、终审、执行转移、donor 影响。

7. Phase 6：支撑产品模块
   - 资产、统计、反馈、催办、通知日志。

8. Phase 7：自动释放和回归包
   - 管理命令、幂等性、XSS/安全、移动端、完整 Playwright 套件。

## 追踪矩阵

| 系统入口 | 验证覆盖 |
|---|---|
| `/login/` | 角色选择、非法角色、改密回归、退出后重定向 |
| `/api/user/roles/` | 所有种子用户角色、未知用户、缺失用户名 |
| `/` 首页 | 角色计数、通知、库存摘要、控制台错误 |
| `/apply/` | 提交、校验、动态库存、项目搜索、使用人选择、附件、撤回、历史、总览、详情、催办入口 |
| `/approve/` | 单笔/批量批准、驳回、预分配、终审、协调、撤回、筛选、历史、直接 POST 权限 |
| `/execute/` | 资产绑定、实际卡数调整、全量释放、部分释放、自动释放开关、协调转移、历史 |
| `/assets/` | 查看/筛选/导出、新增/编辑/删除、使用中删除保护、密码权限 |
| `/statistics/` | 默认指标、日期/型号/快捷筛选、排行、空状态 |
| `/feedback/` | 提交/编辑/删除/解决/图片生命周期和权限矩阵 |
| `/remind/` | 阶段接收人、本人/管理员授权、终态拒绝、通知日志 |
| `/mock-notification-api/` | 方法/参数处理，以及通知日志发送/重发集成 |
| `/api/inventory/` | 已知/未知形态型号组合、安全可用量 |
| `/api/application/details/` | 本人/管理员/角色访问、资产、附件、转义、无密码泄露 |
| `/assets/password/` | 执行人/管理员密码访问、申请人本人裸机权限、非本人拒绝 |
| Django admin `CustomUserAdmin` | 多角色展示/筛选、批量导入、单个和批量重置密码 |
| Django admin `SystemOptionAdmin` | 批量导入、重复处理、非法类别 |
| Django admin `ResourceInventoryAdmin` | 动态选项字段、负数/超分配校验 |
| Django admin `ApplicationAdmin` | 历史导入、状态映射、状态修正后的库存/资产副作用 |
| Django admin `ResourceAssetAdmin` | 批量导入、选项/责任人校验、加密密码保存 |
| Django admin `IssueFeedbackAdmin` | 反馈和图片 inline、管理员处理 |
| Django admin `SystemSettingAdmin` | `auto_release_enabled` 持久化 |
| Django admin `SystemNotificationLogAdmin` | 筛选/搜索、失败通知重发 |
| 管理命令 `release_expired_assets` | 开关关闭跳过、超期释放、未到期忽略、幂等 |
| 数据模型信号 | 申请附件/反馈图片文件清理、选项改名传播 |

## 当前覆盖自检

现有 Playwright 已有以下回归保护：

- 角色 API 登录冒烟和申请人首页渲染。
- 多个申请人提交多张申请单时，历史记录不串数据。
- 各角色主要页面无前端错误。
- 移动端申请页可用性。
- 预审人短缺库存徽标渲染。
- 紧急协调同型号已执行 donor 候选展示。
- 执行人可绑定一个资产并标记申请已执行。
- 申请人可查看自己已执行裸机资产密码。
- 申请详情 XSS 转义。
- 资产筛选和执行人查看资产密码。
- 资产编辑时密码占位符不会覆盖原密码。
- 反馈提交和执行人解决冒烟。

仍缺失且本方案要求补齐：

- 10 个申请人从提交到组长审批、预审、终审、执行、释放的完整流程。
- 强制部分释放。
- 紧急协调执行转移和 donor 后置影响验证。
- 批量审批、批量预分配、批量终审。
- 组长撤回和预审撤回。
- 每个审批阶段的驳回。
- 直接 POST 权限反向测试。
- 修改密码、退出、非法角色登录。
- 申请附件上传和粘贴行为。
- 项目和使用人选择器反向校验。
- 催办接收人矩阵、模拟通知接口、通知重发。
- 统计筛选、排行、空状态。
- 资产新增、删除、导出、使用中删除保护。
- 后台批量导入、密码重置、库存校验、后台状态副作用、全局设置、通知日志。
- `release_expired_assets` 管理命令。
- JSON API 反向权限和方法覆盖。
- 生命周期后的数据库不变量断言。
- 反馈编辑、删除、图片校验、已解决锁定。
- 选项改名传播和文件清理信号。

## 执行前人工确认清单

执行验证前请确认：

- 资源形态是否确认为：`裸机`、`推理池`、`训练池`、`开发池`。
- 卡型号是否确认为：`A100`、`A800`、`H100`、`H200`、`L40S`。
- 部分释放语义：
  - 按卡数释放、按资产释放，还是两者都支持。
  - 部分释放后申请保持 `EXECUTED` 并减少剩余分配，还是新增类似 `PARTIALLY_RELEASED` 状态。
- 一个全局预审人/部门负责人/执行人是否可接受，还是每个团队都需要独立角色。
- 紧急 donor 行为：
  - donor 分配可被减少。
  - 紧急申请可复用 donor 资产。
  - donor 申请人能看到被影响后的分配。
- CSV 导出是否属于正式支持功能；当前 UI 已暴露该能力，本方案按支持功能处理。
- 历史导入是否必须自动创建缺失申请人；当前代码尝试该路径，本方案按支持行为验证。
- 资产导入中非正数卡数的期望行为；当前代码倾向回退为 8 卡。
- `SystemNotificationLog` 需要按接收人逐条记录，还是一条日志包含多个接收人；当前方案要求接收人级可追踪。

## 执行命令

目标 Django 测试：

```powershell
python manage.py test resource_app.tests.test_admin_imports resource_app.tests.test_admin_side_effects resource_app.tests.test_release_expired_assets resource_app.tests.test_api_permissions
```

目标 Playwright 测试：

```powershell
$env:BASE_URL='http://127.0.0.1:8001'
npm run test:e2e -- --grep "comprehensive|emergency|admin|auth|application form|approval|execution|asset|statistics|feedback|reminders|json APIs|mobile" --reporter=list
```

全量验证：

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py release_expired_assets
$env:BASE_URL='http://127.0.0.1:8001'
npm run test:e2e -- --reporter=list
```

## 执行后的交付物

- 完整 Playwright 全流程测试。
- 覆盖后台导入、后台副作用、API 权限、定时释放的 Django 测试。
- 所有失败测试暴露问题后的最小修复。
- 测试总结报告，包含：
  - 已通过流程。
  - 失败或缺口流程。
  - 已发现并修复的 Bug。
  - 已发现但需要产品决策的 Bug。
  - 本文覆盖矩阵中每一行的通过/失败/未执行状态。
  - 正常生命周期、释放、紧急协调后的数据一致性结果。
  - 最终命令输出。
- 提交并推送到 `origin/codex`。

## 已知风险

- 当前 UI 可能不支持部分释放。若不支持，必须记录为 P1 功能缺陷，不能作为可接受限制。
- 紧急协调 UI 的选择器可能因角色和状态不同而变化；测试实现必须使用项目作用域内的可见容器定位。
- 全部流程放进一个测试会很慢；正常生命周期、紧急生命周期、支撑模块必须拆成独立 describe block。
- 种子数据不能删除非 `e2e_` 前缀的用户数据。
- 后台 UI 测试比模型级测试更慢、更脆弱；只有必须验证浏览器交互的自定义后台页面/动作才用 Playwright，纯副作用用 Django 测试。
- 催办发送是异步的；测试必须用有限超时轮询通知日志或模拟接收器结果。
- 文件上传/粘贴测试必须清理 `media/attachments/` 和 `media/feedback_images/` 中创建的文件。

## 审阅状态

本方案已补充为中文全功能验证计划，等待用户审阅。尚未按本方案执行完整验证。
