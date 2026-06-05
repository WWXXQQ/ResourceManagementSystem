# 算力物料资源管理平台 (Resource Management System) - 核心技术架构文档

这份文档详细总结了当前“算力物料资源管理平台”的功能概貌、业务闭环、核心系统架构以及技术实现细节。
非常适合作为 **Prompt / 上下文** 喂给各类 AI 辅助开发工具（如 Claude Code, OpenClaw, Cursor 等），帮助它们快速理解项目，无缝进行后续的二次开发、优化和迭代。

---

## 一、 系统定位与核心功能点

本系统是一套为 AI 算力团队（或大规模 GPU 集群团队）量身定制的**算力资源申请、流转、审批、抽调与实体物料生命周期管控**的一体化管理系统。

### 1.1 核心业务闭环
- **普通用户（申请人）**：提交算力需求单（选择项目、卡型、形态、数量、期望使用时段等），并可通过“看板”实时查看全组的资源大盘及可用库存。
- **组长（初审人 - TEAM_LEADER）**：负责业务必要性审核。
- **预审员（预审配置 - PRE_APPROVER）**：负责资源统筹。根据当前逻辑库存（安全余量），为申请单“定额定型”。若库存不足，预审员可触发**“紧急协调抽调机制”**，从其他已分配的低优项目中剥夺算力卡。
- **部门负责人（终审放行 - FINAL_APPROVER）**：审阅整体方案（包括抽调方案），一键批量放行。
- **执行人（资源交付 - EXECUTOR）**：物理实施层。执行人将逻辑申请单与后台真实的物理机器资产（`ResourceAsset`）进行绑定，记录 IP 地址与实际分配卡数。

### 1.2 高级系统特性
1. **精细化物理切割分配 (Partial Allocation)**：
   打破了“整机分配”的传统模式。一台拥有 8 张 GPU 的裸机，可以按“张”为粒度，精准拆分并挂载给不同的业务项目。系统自动维护物理机的“空闲 (IDLE) / 部分使用 (PARTIAL) / 满载 (IN_USE)”状态机。
2. **多维安全库存模型**：
   引入“预分配锁定（Pre-allocated）”概念。当单据处于待终审时，虽然没发货，但对应库存已被扣除（安全可用 = 物理总库存 - 已执行扣减 - 排队中单据锁定）。
3. **自动化超期释放机制**：
   拥有后台常驻钩子 / 定时脚本。当用户的申请单“使用截止日期”到期后，系统自动释放单据，并自动解绑对应的物理机卡数，将资源退回公海库存。
4. **用户反馈与催办闭环**：
   独立的 `IssueFeedback` 表，支持问题反馈与管理员的消息催办（催办功能目前已打通邮件发送或站内信底座）。

---

## 二、 技术栈与构建方案

- **后端框架**：Python + Django
- **数据库**：SQLite (开发/初期部署环境)，生产时可无缝切为 PostgreSQL
- **前端架构**：原生 HTML5 + 原生 JavaScript + CSS3 变量驱动（未采用 React/Vue 这种重型框架，保证了极高的渲染速度和极简的依赖栈）
- **UI 设计美学 (Glassmorphism & Dark Mode)**：
  - 采用现代化黑夜模式 (Dark Mode) 与毛玻璃特效 (Glassmorphism)。
  - 核心 CSS 采用了极具科技感的设计（如悬浮动画、渐变强调色、实时 Badge 等），给用户极佳的视觉 WOW 体验。

---

## 三、 核心数据库模型 (Models) 设计说明

代码主要位于 `resource_app/models.py` 中。

### 1. `Application` (申请单据)
这是全站流通的核心数据实体。
- **状态流转 (`status`)**：
  `PENDING_TEAM` (待组长初审) -> `PENDING_PRE` (待预审) -> `PENDING_FINAL` (待终审) -> `APPROVED` (待执行) -> `EXECUTED` (已执行) -> `RELEASED` (已释放) -> `REJECTED` (已驳回) / `WITHDRAWN` (已撤销)
- **核心字段**：
  - 用户申请需求：`count` (需卡数), `cardType` (申请型号, 如 D910B), `cardForm` (申请形态, 如 裸机/保障卡)
  - 预审配卡结果：`allocatedCount`, `allocatedCardType`, `allocatedCardForm`
  - 协调抽调方案：`coordination_details` (JSON，记录拟抽调的受害者单据ID及剥夺卡数)

### 2. `ResourceInventory` (逻辑库存大盘)
主要用于看板和预审时的逻辑额度计算。
- 按 `(cardName, cardType, cardForm, region)` 四元组聚合。
- `totalCount`: 物理采购总数。
- `allocatedCount`: 已被“成功执行”的扣减数。
*(注：待审批锁定数是实时查询 Application 聚合计算出来的，不存死在表里)*

### 3. `ResourceAsset` (物理台账资产)
表示机房里真实存在的服务器/集群节点。
- `card_count`: 本机总卡数 (例如 8)
- `used_cards`: 当前已被占用的卡数 (例如 2)
- `status`: `IDLE` (空闲, used=0), `PARTIAL` (部分占用, 0 < used < total), `IN_USE` (满载, used=total)

### 4. `AssetAllocation` (精细化分配映射表 - 重点)
多对多核心枢纽表。连接 `ResourceAsset` 与 `Application`。
- `asset`: 外键指向某台物理服务器。
- `application`: 外键指向某张业务申请单。
- `allocated_cards`: 该单据从这台服务器上割走的卡数（精确到张）。

---

## 四、 页面级架构 (Templates & Views)

- `views.py: index()` -> `dashboard.html`: 申请人与公共大盘页面。提供申请入口、个人历史、以及带数据权限控制的全景库存看板。
- `views.py: team_approve_view()` -> `team_approve.html`: 组长初审视角。
- `views.py: approve_view()` -> `approve.html`: 预审及终审视角。**这是全站最复杂的交互页面**，内部包含了动态 AJAX/DOM 级库存校验（基于 JSON Context）、紧急抽调面板拉起、防呆禁用提交等重量级原生 JS 逻辑。
- `views.py: execute_view()` -> `execute.html`: 执行人视角。提供“手工绑定物理机并自动计算拆分差值”的逻辑。
- `views.py: issue_feedback_view()` -> (复用看板/对话框): 反馈及催办通道。

---

## 五、 给 AI 助手的特别提示 (AI Developer Guidelines)

如果你是即将接手本项目的 AI（例如 Claude Code），在修改代码时请严格注意以下几点：

> [!IMPORTANT]
> 1. **关于模型关系的重大历史包袱**
>    本项目在近期发生了一次重大架构升级：**剥离了物理机 1对1 独占模型，改为了 1对多 拆分映射（`AssetAllocation`）**。
>    请**永远不要**在代码里试图寻找 `allocated_application` 这个已被废除的单向外键。所有物理分配关系的查询必须经过 `AssetAllocation` 中间表。
>
> 2. **执行环节的松耦合设计**
>    在 `execute_view` 中，执行人分配真实物理资产是**“可选的”**。允许申请单只在逻辑库存上扣减额度（不选任何实体物理机），此时 `actual_card_count = 0`，不应当做错误拦截，直接完成流转即可。
>
> 3. **前端交互设计约束**
>    本项目的前端不使用 React/Vue，严重依赖 Django Template Engine (`{% for %}`) 混编生成 JSON 变量供原生 JS 驱动。在修改 `approve.html` 的动态校验与防呆逻辑（如按钮置灰、抽调面板显隐）时，必须小心处理 `{% if %}` 模板分支与 JS 变量的隔离作用域问题。

---
**Document Status**: Stable (Phase 4 Final)
**Last Upgraded**: Asset Partial Allocation Engine (Bug-free)
