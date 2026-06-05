from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Sum, Q
from django.http import JsonResponse
from collections import defaultdict
from datetime import date, timedelta
from .models import Application, ResourceInventory, SystemOption, CustomUser, ResourceAsset, IssueFeedback, SystemSetting, FeedbackImage, SystemNotificationLog, AssetAllocation
import json
import requests
import uuid
import os
import threading
from django.db import transaction


BARE_METAL_FORM = '裸机'


def is_bare_metal_value(value):
    return (value or '').strip() == BARE_METAL_FORM


def is_bare_metal_allocation(application, asset=None):
    return (
        is_bare_metal_value(application.cardForm) or
        is_bare_metal_value(application.allocatedCardForm) or
        (asset is not None and is_bare_metal_value(asset.card_form))
    )


def get_sidebar_counts(user):
    """计算侧边栏角标数量"""
    counts = {}
    pending_app_count = 0
    if user.role == 'TEAM_LEADER':
        qs = Application.objects.filter(status='PENDING_TEAM')
        if user.team:
            qs = qs.filter(team=user.team)
        pending_app_count = qs.count()
    elif user.role == 'APPROVER':
        pending_app_count = Application.objects.filter(status='PENDING_PRE').count()
    elif user.role == 'DEPT_HEAD':
        pending_app_count = Application.objects.filter(status='PENDING_FINAL').count()
    elif user.role == 'ADMIN':
        pending_app_count = Application.objects.filter(status__in=['PENDING_TEAM', 'PENDING_PRE', 'PENDING_FINAL']).count()
        
    counts['pending_approve'] = pending_app_count
    
    if user.role in ['EXECUTOR', 'ADMIN']:
        counts['pending_execute'] = Application.objects.filter(status='APPROVED').count()
    return counts


def get_user_notifications(user, limit=5):
    """获取当前用户相关的最新通知（最近的状态变更）"""
    notifications = []
    
    if user.role in ['APPLICANT', 'ADMIN']:
        recent_apps = Application.objects.filter(
            applicant=user,
            status__in=['APPROVED', 'REJECTED', 'EXECUTED', 'RELEASED']
        ).order_by('-updated_at')[:limit]
        for app in recent_apps:
            if app.status == 'APPROVED':
                notifications.append({
                    'type': 'success',
                    'message': f'您的申请「{app.project}」已被审批通过，分配 {app.allocatedCardType} x {app.allocatedCount} 张',
                    'time': app.updated_at
                })
            elif app.status == 'REJECTED':
                reason = app.final_approver_note or app.pre_approver_note or app.team_leader_note or app.approvalNote or "无"
                notifications.append({
                    'type': 'danger',
                    'message': f'您的申请「{app.project}」已被驳回，理由：{reason}',
                    'time': app.updated_at
                })
            elif app.status == 'EXECUTED':
                notifications.append({
                    'type': 'info',
                    'message': f'您的申请「{app.project}」已执行完成：{app.executionResult or ""}',
                    'time': app.updated_at
                })
            elif app.status == 'RELEASED':
                notifications.append({
                    'type': 'secondary',
                    'message': f'您的申请「{app.project}」所占用的资源已交付使用完毕，现已成功释放归还。',
                    'time': app.updated_at
                })
    
    new_pending = []
    if user.role == 'TEAM_LEADER':
        qs = Application.objects.filter(status='PENDING_TEAM')
        if user.team:
            qs = qs.filter(team=user.team)
        new_pending = qs.order_by('-created_at')[:limit]
    elif user.role == 'APPROVER':
        new_pending = Application.objects.filter(status='PENDING_PRE').order_by('-created_at')[:limit]
    elif user.role == 'DEPT_HEAD':
        new_pending = Application.objects.filter(status='PENDING_FINAL').order_by('-created_at')[:limit]
    elif user.role == 'ADMIN':
        new_pending = Application.objects.filter(status__in=['PENDING_TEAM', 'PENDING_PRE', 'PENDING_FINAL']).order_by('-created_at')[:limit]

    for app in new_pending:
        notifications.append({
            'type': 'warning',
            'message': f'待您审批的申请：{app.applicant.username} 申请「{app.project}」{app.cardType} x {app.count} 张',
            'time': app.created_at
        })
    
    notifications.sort(key=lambda x: x['time'], reverse=True)
    return notifications[:limit]


def refresh_asset_summary(asset):
    """Recompute a physical asset's occupancy and display fields from allocations."""
    allocations = list(
        AssetAllocation.objects.filter(asset=asset)
        .select_related('application', 'application__applicant')
        .order_by('created_at')
    )
    used_cards = sum(allocation.allocated_cards for allocation in allocations)

    asset.used_cards = min(used_cards, asset.card_count or used_cards)
    if asset.used_cards <= 0:
        asset.status = 'IDLE'
    elif asset.used_cards >= asset.card_count:
        asset.status = 'IN_USE'
    else:
        asset.status = 'PARTIAL'

    if allocations:
        first_app = allocations[0].application
        asset.owner = first_app.applicant
        asset.current_users = ', '.join(
            dict.fromkeys(
                user.strip()
                for allocation in allocations
                for user in (allocation.application.users or '').split(',')
                if user.strip()
            )
        )
        asset.app_name = ', '.join(
            dict.fromkeys(allocation.application.project for allocation in allocations)
        )
    else:
        asset.owner = None
        asset.current_users = ''
        asset.app_name = ''

    asset.save(update_fields=['used_cards', 'status', 'owner', 'current_users', 'app_name', 'updated_at'])


def get_preempt_candidates(application):
    """Find already allocated same-card applications available for coordination."""
    same_card_type = (
        Q(allocatedCardType=application.cardType) |
        Q(allocatedCardType__isnull=True, cardType=application.cardType) |
        Q(allocatedCardType='', cardType=application.cardType)
    )
    return Application.objects.filter(
        same_card_type,
        status__in=['APPROVED', 'EXECUTED'],
        allocatedCount__gt=0
    ).exclude(
        id=application.id
    ).exclude(
        project=application.project
    ).prefetch_related('asset_allocations__asset')


@login_required
def inventory_api(request):
    """AJAX API: 根据 cardType 和 cardForm 查询可用库存"""
    card_type = request.GET.get('cardType', '')
    card_form = request.GET.get('cardForm', '')
    
    filters = {}
    if card_type:
        filters['cardType'] = card_type
    if card_form:
        filters['cardForm'] = card_form
    
    if not filters:
        return JsonResponse({'available': None})
    
    summary = ResourceInventory.objects.filter(**filters).aggregate(
        total=Sum('totalCount'),
        allocated=Sum('allocatedCount')
    )
    total = summary['total'] or 0
    allocated = summary['allocated'] or 0
    return JsonResponse({'available': total - allocated})


@login_required
def dashboard(request):
    inventory = ResourceInventory.objects.all().order_by('cardType', 'cardForm', 'region', 'totalCount', 'cardName')
    applications = Application.objects.filter(status__in=['APPROVED', 'EXECUTED']).order_by('-updated_at')
    
    total_cards = sum(item.totalCount for item in inventory)
    allocated_cards = sum(item.allocatedCount for item in inventory)
    unallocated_cards = total_cards - allocated_cards
    
    # 预计算剩余可用数，避免模板中计算错误
    for item in inventory:
        item.remain = item.totalCount - item.allocatedCount
    
    pending_count = Application.objects.filter(status__in=['PENDING_TEAM', 'PENDING_PRE', 'PENDING_FINAL']).count()
    executing_count = Application.objects.filter(status='APPROVED').count()
    
    notifications = get_user_notifications(request.user, limit=8)
    
    # 获取所有不同的 cardType 和 cardForm 用于筛选
    all_card_types = sorted(list(ResourceInventory.objects.values_list('cardType', flat=True).distinct()))
    all_card_forms = sorted(list(ResourceInventory.objects.values_list('cardForm', flat=True).distinct()))
    
    context = {
        'inventory': inventory,
        'applications': applications,
        'total_cards': total_cards,
        'allocated_cards': allocated_cards,
        'unallocated_cards': unallocated_cards,
        'pending_count': pending_count,
        'executing_count': executing_count,
        'notifications': notifications,
        'all_card_types': all_card_types,
        'all_card_forms': all_card_forms,
        'current_role': request.user.role,
        'sidebar_counts': get_sidebar_counts(request.user),
    }
    return render(request, 'dashboard.html', context)

@login_required
def apply_view(request):
    if request.user.role not in ['APPLICANT', 'ADMIN']:
        messages.error(request, '无权限访问申请页面，请使用申请人账号登录。')
        return redirect('dashboard')
        
    if request.method == 'POST':
        action = request.POST.get('action', 'submit')
        
        # 撤回申请
        if action == 'cancel':
            app_id = request.POST.get('app_id')
            application = get_object_or_404(Application, id=app_id, applicant=request.user)
            if application.status in ['PENDING_TEAM', 'PENDING_PRE', 'PENDING_FINAL']:
                application.allocatedCount = None
                application.allocatedCardType = None
                application.allocatedCardForm = None
                application.approvalNote = None
                application.status = 'CANCELLED'
                application.save()
                messages.success(request, f'已成功撤回申请「{application.project}」。')
            else:
                messages.error(request, '只能撤回待审批状态的申请。')
            return redirect('apply')
        
        # 提交新申请
        team = request.POST.get('team')
        cardForm = request.POST.get('cardForm')
        cardType = request.POST.get('cardType')
        project = request.POST.get('project')
        priority = request.POST.get('priority')
        count = request.POST.get('count')
        minCount = request.POST.get('minCount')
        users_list = request.POST.getlist('users')
        model_used = request.POST.get('model_used')
        purpose = request.POST.get('purpose')
        priorityReason = request.POST.get('priorityReason')
        start_date_str = request.POST.get('startDate', '')
        end_date_str = request.POST.get('endDate', '')
        note = request.POST.get('note')
        
        count_val = int(count) if count else 0
        min_count_val = int(minCount) if minCount else count_val
        
        if count_val <= 0:
            messages.error(request, '申请卡数量必须大于 0，请重新输入。')
            return redirect('apply')
            
        if min_count_val <= 0:
            messages.error(request, '最少卡数量必须大于 0，请重新输入。')
            return redirect('apply')
        
        if min_count_val > count_val:
            messages.error(request, f'最少卡数量 ({min_count_val}) 不能超过申请卡数量 ({count_val})，请修正。')
            return redirect('apply')
        
        # 解析日期
        start_date = None
        end_date = None
        duration_text = '未指定'
        if start_date_str and end_date_str:
            try:
                start_date = date.fromisoformat(start_date_str)
                end_date = date.fromisoformat(end_date_str)
                if end_date < start_date:
                    messages.error(request, '结束使用日期不能早于开始使用日期，请修正。')
                    return redirect('apply')
                delta = (end_date - start_date).days
                duration_text = f'{start_date_str} ~ {end_date_str} ({delta}天)'
            except ValueError:
                duration_text = f'{start_date_str} ~ {end_date_str}'
        
        attachment = request.FILES.get('attachment')
        if attachment:
            # 1. 校验扩展名
            ext = os.path.splitext(attachment.name)[1].lower()
            allowed_exts = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
            if ext not in allowed_exts:
                messages.error(request, '附件上传失败：仅允许上传图片文件（支持 .png, .jpg, .jpeg, .gif, .webp 格式）。')
                return redirect('apply')
            
            # 2. 校验文件大小（限制 5MB）
            if attachment.size > 5 * 1024 * 1024:
                messages.error(request, '附件上传失败：图片文件大小不能超过 5MB。')
                return redirect('apply')
                
            # 3. UUID 随机重命名以保证安全性
            attachment.name = f"{uuid.uuid4()}{ext}"

        Application.objects.create(
            applicant=request.user,
            team=team,
            cardForm=cardForm,
            cardType=cardType,
            project=project,
            priority=priority,
            count=count_val,
            minCount=min_count_val,
            users=', '.join(users_list),
            model_used=model_used,
            purpose=purpose,
            priorityReason=priorityReason,
            startDate=start_date,
            endDate=end_date,
            duration=duration_text,
            note=note,
            attachment=attachment,
            status='PENDING_TEAM'
        )
        messages.success(request, '申请已成功提交！')
        return redirect('apply')

    my_apps = Application.objects.filter(applicant=request.user).order_by('-created_at')
    options = SystemOption.objects.all()
    
    # 为申请人提供库存参考（按型号汇总，同型号不同形态在同一行）
    raw_summary = ResourceInventory.objects.values('cardType', 'cardForm').annotate(
        total_sum=Sum('totalCount'),
        allocated_sum=Sum('allocatedCount')
    ).order_by('cardType')
    
    # 按 cardType 分组
    inventory_by_type = defaultdict(list)
    for item in raw_summary:
        total = item['total_sum'] or 0
        allocated = item['allocated_sum'] or 0
        inventory_by_type[item['cardType']].append({
            'cardForm': item['cardForm'],
            'availableCount': total - allocated,
        })
    
    # 序列化给模板的 JS 使用
    inventory_ref_json = json.dumps(
        [{'cardType': ct, 'cardForm': cf, 'available': (item['total_sum'] or 0) - (item['allocated_sum'] or 0)}
         for item in raw_summary
         for ct, cf in [(item['cardType'], item['cardForm'])]]
    )
    
    all_apps = Application.objects.exclude(status='CANCELLED').order_by('-created_at')
    
    context = {
        'my_apps': my_apps,
        'all_apps': all_apps,
        'teams': options.filter(category='TEAM'),
        'card_forms': options.filter(category='CARD_FORM'),
        'card_types': options.filter(category='CARD_TYPE'),
        'projects': options.filter(category='PROJECT'),
        'all_users': CustomUser.objects.all(),
        'inventory_by_type': dict(inventory_by_type),
        'inventory_ref_json': inventory_ref_json,
        'current_role': request.user.role,
        'sidebar_counts': get_sidebar_counts(request.user),
    }
    return render(request, 'apply.html', context)

@login_required
def approve_view(request):
    if request.user.role not in ['TEAM_LEADER', 'APPROVER', 'DEPT_HEAD', 'ADMIN']:
        messages.error(request, '无权限访问审批页面。')
        return redirect('dashboard')
    
    active_tab = request.GET.get('tab', 'pending')
    anchor = ''
        
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # 组长批量同意
        if action == 'batch_team_approve':
            if request.user.role not in ['TEAM_LEADER', 'ADMIN']:
                messages.error(request, '无权限进行组长批量审批。')
                return redirect('approve')
            project = request.POST.get('batch_project')
            with transaction.atomic():
                qs = Application.objects.select_for_update().filter(status='PENDING_TEAM', project=project)
                if request.user.role == 'TEAM_LEADER' and request.user.team:
                    qs = qs.filter(team=request.user.team)
                count = 0
                for app in qs:
                    app.status = 'PENDING_PRE'
                    app.team_leader_note = '组长批量同意'
                    app.save()
                    count += 1
            messages.success(request, f'已成功批量同意项目「{project}」下的 {count} 笔申请（已送交资源预审）。')
            return redirect(f'/approve/?tab=pending#project-{project}')

        # 批量预分配（不需要 app_id）
        if action == 'batch_pre_allocate':
            if request.user.role not in ['APPROVER', 'ADMIN']:
                messages.error(request, '无权限进行批量资源预分配。')
                return redirect('approve')
            project = request.POST.get('batch_project')
            with transaction.atomic():
                batch_apps = list(Application.objects.select_for_update().filter(
                    status='PENDING_PRE', project=project, allocatedCount__isnull=True
                ))
                if not batch_apps:
                    messages.warning(request, f'项目「{project}」没有需要预分配的申请。')
                    return redirect(f'/approve/?tab=pending#project-{project}')

                # 按 cardType+cardForm 汇总本批次需求
                demand_by_type = defaultdict(int)
                for app in batch_apps:
                    demand_by_type[(app.cardType, app.cardForm)] += app.count

                # 校验每种资源的可用库存
                shortage_msgs = []
                for (card_type, card_form), demand in demand_by_type.items():
                    inv_sums = ResourceInventory.objects.filter(
                        cardType=card_type, cardForm=card_form
                    ).aggregate(
                        total_sum=Sum('totalCount'),
                        allocated_sum=Sum('allocatedCount')
                    )
                    total = inv_sums['total_sum'] or 0
                    allocated = inv_sums['allocated_sum'] or 0

                    # 已有的待终审预分配（不含本批次）
                    pre_allocated_final = Application.objects.filter(
                        status='PENDING_FINAL',
                        allocatedCardType=card_type,
                        allocatedCardForm=card_form,
                        allocatedCount__gt=0
                    ).aggregate(sum_pre=Sum('allocatedCount'))['sum_pre'] or 0

                    available = total - allocated - pre_allocated_final
                    if demand > available:
                        shortage_msgs.append(
                            f'{card_type}({card_form})：需要 {demand} 张，可用 {available} 张，缺口 {demand - available} 张'
                        )

                if shortage_msgs:
                    detail = '；'.join(shortage_msgs)
                    messages.error(request, f'批量预分配失败，库存不足：{detail}。请逐条手动分配或先补充库存。')
                    return redirect(f'/approve/?tab=pending#project-{project}')

                # 校验通过，执行批量预分配
                count = 0
                for app in batch_apps:
                    app.allocatedCount = app.count
                    app.allocatedCardType = app.cardType
                    app.allocatedCardForm = app.cardForm
                    app.pre_approver_note = '批量预分配'
                    app.status = 'PENDING_FINAL'
                    app.save()
                    count += 1
            messages.success(request, f'已为项目「{project}」批量预分配 {count} 笔申请（已送交部门终审）。')
            return redirect(f'/approve/?tab=pending#project-{project}')

        # 批量实际分配（终审通过）整个项目的预分配结果
        if action == 'batch_approve':
            if request.user.role not in ['DEPT_HEAD', 'ADMIN']:
                messages.error(request, '无权限进行批量终审。')
                return redirect('approve')
            project = request.POST.get('batch_project')
            approved_count = 0
            with transaction.atomic():
                batch_apps = Application.objects.select_for_update().filter(status='PENDING_FINAL', project=project, allocatedCount__gt=0)
                for app in batch_apps:
                    app.status = 'APPROVED'
                    app.final_approver_note = '部门批量同意'
                    
                    # 扣减库存，使用 select_for_update 并发排他锁
                    inventories = ResourceInventory.objects.select_for_update().filter(cardType=app.allocatedCardType, cardForm=app.allocatedCardForm)
                    alloc_details = []
                    if inventories.exists():
                        remaining_to_allocate = app.allocatedCount
                        for inv in inventories:
                            available = inv.totalCount - inv.allocatedCount
                            if available > 0:
                                to_add = min(remaining_to_allocate, available)
                                inv.allocatedCount += to_add
                                inv.save()
                                if not app.allocatedCardName:
                                    app.allocatedCardName = inv.cardName
                                    app.allocatedRegion = inv.region
                                alloc_details.append({
                                    'inventory_id': inv.id,
                                    'cardName': inv.cardName,
                                    'region': inv.region,
                                    'count': to_add
                                })
                                remaining_to_allocate -= to_add
                                if remaining_to_allocate <= 0:
                                    break
                        if remaining_to_allocate > 0:
                            first_inv = inventories.first()
                            first_inv.allocatedCount += remaining_to_allocate
                            first_inv.save()
                            if not app.allocatedCardName:
                                app.allocatedCardName = first_inv.cardName
                                app.allocatedRegion = first_inv.region
                            # 记录溢出分配
                            found = False
                            for det in alloc_details:
                                if det['inventory_id'] == first_inv.id:
                                    det['count'] += remaining_to_allocate
                                    found = True
                                    break
                            if not found:
                                alloc_details.append({
                                    'inventory_id': first_inv.id,
                                    'cardName': first_inv.cardName,
                                    'region': first_inv.region,
                                    'count': remaining_to_allocate
                                })
                    else:
                        default_inv = ResourceInventory.objects.create(
                            cardName=f"自动创建{app.allocatedCardType}池",
                            cardForm=app.allocatedCardForm,
                            cardType=app.allocatedCardType,
                            region="默认区域",
                            totalCount=app.allocatedCount,
                            allocatedCount=app.allocatedCount
                        )
                        app.allocatedCardName = default_inv.cardName
                        app.allocatedRegion = default_inv.region
                        alloc_details.append({
                            'inventory_id': default_inv.id,
                            'cardName': default_inv.cardName,
                            'region': default_inv.region,
                            'count': app.allocatedCount
                        })
                    
                    app.allocation_details = alloc_details
                    app.save()
                    approved_count += 1
                
            messages.success(request, f'已成功批准项目「{project}」的 {approved_count} 笔预分配申请！')
            return redirect(f'/approve/?tab=pending#project-{project}')
        
        # 以下操作需要 app_id
        app_id = request.POST.get('app_id')
        
        # 组长单步审批
        if action == 'team_approve' or action == 'team_reject':
            if request.user.role not in ['TEAM_LEADER', 'ADMIN']:
                messages.error(request, '无组长审批权限。')
                return redirect('approve')
            
            with transaction.atomic():
                application = get_object_or_404(Application.objects.select_for_update(), id=app_id)
                if request.user.role == 'TEAM_LEADER' and request.user.team and application.team != request.user.team:
                    messages.error(request, '只能审批属于您团队的申请。')
                    return redirect('approve')
                
                note = request.POST.get('team_leader_note') or request.POST.get('rejectReason') or ''
                application.team_leader_note = note
                if action == 'team_approve':
                    application.status = 'PENDING_PRE'
                    application.save()
                    messages.success(request, f'已同意项目「{application.project}」的组长审批，已送交资源预审。')
                else:
                    application.status = 'REJECTED'
                    application.save()
                    messages.warning(request, f'已驳回项目「{application.project}」的申请。')
            return redirect(f'/approve/?tab=pending#project-{application.project}')
            
        # 预分配/预审
        elif action in ['pre_allocate', 'pre_reject']:
            if request.user.role not in ['APPROVER', 'ADMIN']:
                messages.error(request, '无资源预审权限。')
                return redirect('approve')
            
            with transaction.atomic():
                application = get_object_or_404(Application.objects.select_for_update(), id=app_id)
                if action == 'pre_reject':
                    reject_reason = request.POST.get('rejectReason')
                    application.status = 'REJECTED'
                    application.pre_approver_note = reject_reason
                    application.save()
                    messages.warning(request, f'已驳回项目「{application.project}」的资源预审。')
                else:
                    allocatedCount = int(request.POST.get('allocatedCount', 0))
                    if allocatedCount < 0:
                        messages.error(request, '分配卡数量不能为负数，请修正。')
                        return redirect('approve')
                    allocatedCardType = request.POST.get('allocatedCardType')
                    allocatedCardForm = request.POST.get('allocatedCardForm')
                    note = request.POST.get('pre_approver_note', '')
                    
                    # BACKEND VALIDATION:
                    inv_sums = ResourceInventory.objects.filter(
                        cardType=allocatedCardType, 
                        cardForm=allocatedCardForm
                    ).aggregate(
                        total_sum=Sum('totalCount'),
                        allocated_sum=Sum('allocatedCount')
                    )
                    total = inv_sums['total_sum'] or 0
                    allocated = inv_sums['allocated_sum'] or 0
                    
                    pre_allocated_final = Application.objects.filter(
                        status='PENDING_FINAL',
                        allocatedCardType=allocatedCardType,
                        allocatedCardForm=allocatedCardForm,
                        allocatedCount__gt=0
                    ).exclude(id=application.id).aggregate(sum_pre=Sum('allocatedCount'))['sum_pre'] or 0
                    
                    preempt_data = []
                    preempt_total = 0
                    prefix = f"preempt_{application.id}_"
                    for key, val in request.POST.items():
                        if key.startswith(prefix):
                            try:
                                candidate_id = int(key[len(prefix):])
                                count = int(val)
                                if count > 0:
                                    cand = Application.objects.get(id=candidate_id)
                                    preempt_data.append({
                                        'app_id': candidate_id,
                                        'project': cand.project,
                                        'count': count
                                    })
                                    preempt_total += count
                            except (ValueError, Application.DoesNotExist):
                                pass

                    safe_available = total - allocated - pre_allocated_final
                    if allocatedCount > safe_available + preempt_total:
                        messages.error(request, f'保存失败：可用资源及拟抽调总数不足（缺口 {allocatedCount - safe_available - preempt_total} 张）。')
                        return redirect(f'/approve/?tab=pending#project-{application.project}')
                    
                    if allocatedCount > safe_available:
                        warn_msg = f"[系统提示：可用资源不足，缺口 {allocatedCount - safe_available} 张，将执行协调抽调方案]"
                        note = f"{note}\n{warn_msg}" if note else warn_msg
                        messages.warning(request, f'可用资源不足，已放行并附带抽调方案（拟抽调 {preempt_total} 张）。')
                    else:
                        messages.success(request, f'已保存项目「{application.project}」的预分配方案，已送交部门终审。')

                    application.allocatedCount = allocatedCount
                    application.allocatedCardType = allocatedCardType
                    application.allocatedCardForm = allocatedCardForm
                    application.pre_approver_note = note
                    application.coordination_details = preempt_data if preempt_data else None
                    application.status = 'PENDING_FINAL'
                    application.save()
            return redirect(f'/approve/?tab=pending#project-{application.project}')
            
        # 部门负责人终审
        elif action in ['final_approve', 'final_reject']:
            if request.user.role not in ['DEPT_HEAD', 'ADMIN']:
                messages.error(request, '无部门终审权限。')
                return redirect('approve')
                
            with transaction.atomic():
                application = get_object_or_404(Application.objects.select_for_update(), id=app_id)
                if action == 'final_reject':
                    reject_reason = request.POST.get('rejectReason')
                    application.status = 'REJECTED'
                    application.final_approver_note = reject_reason
                    application.save()
                    messages.warning(request, f'已驳回项目「{application.project}」的部门终审。')
                else:
                    note = request.POST.get('final_approver_note', '')
                    application.final_approver_note = note
                    application.status = 'APPROVED'
                    
                    # 正式扣减库存
                    allocatedCount = application.allocatedCount or 0
                    allocatedCardType = application.allocatedCardType
                    allocatedCardForm = application.allocatedCardForm
                    
                    inventories = ResourceInventory.objects.select_for_update().filter(cardType=allocatedCardType, cardForm=allocatedCardForm)
                    alloc_details = []
                    if inventories.exists():
                        remaining_to_allocate = allocatedCount
                        for inv in inventories:
                            available = inv.totalCount - inv.allocatedCount
                            if available > 0:
                                to_add = min(remaining_to_allocate, available)
                                inv.allocatedCount += to_add
                                inv.save()
                                if not application.allocatedCardName:
                                    application.allocatedCardName = inv.cardName
                                    application.allocatedRegion = inv.region
                                alloc_details.append({
                                    'inventory_id': inv.id,
                                    'cardName': inv.cardName,
                                    'region': inv.region,
                                    'count': to_add
                                })
                                remaining_to_allocate -= to_add
                                if remaining_to_allocate <= 0:
                                    break
                        if remaining_to_allocate > 0:
                            first_inv = inventories.first()
                            first_inv.allocatedCount += remaining_to_allocate
                            first_inv.save()
                            if not application.allocatedCardName:
                                application.allocatedCardName = first_inv.cardName
                                application.allocatedRegion = first_inv.region
                            # 记录溢出分配
                            found = False
                            for det in alloc_details:
                                if det['inventory_id'] == first_inv.id:
                                    det['count'] += remaining_to_allocate
                                    found = True
                                    break
                            if not found:
                                alloc_details.append({
                                    'inventory_id': first_inv.id,
                                    'cardName': first_inv.cardName,
                                    'region': first_inv.region,
                                    'count': remaining_to_allocate
                                })
                    else:
                        default_inv = ResourceInventory.objects.create(
                            cardName=f"自动创建{allocatedCardType}池",
                            cardForm=allocatedCardForm,
                            cardType=allocatedCardType,
                            region="默认区域",
                            totalCount=allocatedCount,
                            allocatedCount=allocatedCount
                        )
                        application.allocatedCardName = default_inv.cardName
                        application.allocatedRegion = default_inv.region
                        alloc_details.append({
                            'inventory_id': default_inv.id,
                            'cardName': default_inv.cardName,
                            'region': default_inv.region,
                            'count': allocatedCount
                        })
                    
                    application.allocation_details = alloc_details
                    application.save()
                    messages.success(request, f'部门终审已批准项目「{application.project}」的资源申请。')
            return redirect(f'/approve/?tab=pending#project-{application.project}')
        
        # ========== 撤回操作 ==========
        # 组长撤回：PENDING_PRE → PENDING_TEAM
        elif action == 'team_recall':
            if request.user.role not in ['TEAM_LEADER', 'ADMIN']:
                messages.error(request, '无权限执行撤回操作。')
                return redirect('approve')
            with transaction.atomic():
                application = get_object_or_404(Application.objects.select_for_update(), id=app_id)
                if application.status != 'PENDING_PRE':
                    messages.error(request, '该申请单状态已发生变化，无法撤回（预审人可能已处理）。')
                    return redirect('/approve/?tab=history')
                if request.user.role == 'TEAM_LEADER' and request.user.team and application.team != request.user.team:
                    messages.error(request, '只能撤回属于您团队的申请。')
                    return redirect('/approve/?tab=history')
                application.status = 'PENDING_TEAM'
                application.team_leader_note = ''
                application.save()
                messages.success(request, f'已撤回项目「{application.project}」({application.applicant.username}) 的组长审批，可重新审批。')
            return redirect('/approve/?tab=pending')

        # 预审人撤回：PENDING_FINAL → PENDING_PRE
        elif action == 'pre_recall':
            if request.user.role not in ['APPROVER', 'ADMIN']:
                messages.error(request, '无权限执行撤回操作。')
                return redirect('approve')
            with transaction.atomic():
                application = get_object_or_404(Application.objects.select_for_update(), id=app_id)
                if application.status != 'PENDING_FINAL':
                    messages.error(request, '该申请单状态已发生变化，无法撤回（终审人可能已处理）。')
                    return redirect('/approve/?tab=history')
                application.status = 'PENDING_PRE'
                application.pre_approver_note = ''
                application.allocatedCount = None
                application.allocatedCardType = None
                application.allocatedCardForm = None
                application.allocatedCardName = None
                application.allocatedRegion = None
                application.coordination_details = None
                application.save()
                messages.success(request, f'已撤回项目「{application.project}」({application.applicant.username}) 的预审分配，可重新预分配。')
            return redirect('/approve/?tab=pending')

    # GET 逻辑：根据角色加载并过滤待办申请单
    role = request.user.role
    if role == 'TEAM_LEADER':
        pending_apps = Application.objects.filter(status='PENDING_TEAM').order_by('created_at')
        if request.user.team:
            pending_apps = pending_apps.filter(team=request.user.team)
    elif role == 'APPROVER':
        pending_apps = Application.objects.filter(status='PENDING_PRE').order_by('created_at')
    elif role == 'DEPT_HEAD':
        pending_apps = Application.objects.filter(status='PENDING_FINAL').order_by('created_at')
    else:  # ADMIN
        pending_apps = Application.objects.filter(status__in=['PENDING_TEAM', 'PENDING_PRE', 'PENDING_FINAL']).order_by('created_at')
    
    # 已审批记录：根据角色特征加载已处理（已审批/已预审/已驳回/已执行）的历史卡片，避免中间状态在历史中显示为“暂无记录”
    if role == 'TEAM_LEADER':
        # 组长已处理的申请：流转出组长待审批状态且未撤回的所属团队申请
        history_apps = Application.objects.exclude(
            status__in=['PENDING_TEAM', 'CANCELLED']
        ).order_by('-updated_at')
        if request.user.team:
            history_apps = history_apps.filter(team=request.user.team)
    elif role == 'APPROVER':
        # 预审人已处理的申请：流转出待预分配状态且未撤回的申请
        history_apps = Application.objects.exclude(
            status__in=['PENDING_TEAM', 'PENDING_PRE', 'CANCELLED']
        ).order_by('-updated_at')
    elif role == 'DEPT_HEAD':
        # 终审人已处理的申请：最终完成审批决策（APPROVED/REJECTED/已执行/已释放）的申请
        history_apps = Application.objects.filter(
            status__in=['APPROVED', 'REJECTED', 'EXECUTED', 'RELEASED']
        ).order_by('-updated_at')
    else:  # ADMIN
        # 管理员默认可以查看流转出初始状态且非撤回的所有申请
        history_apps = Application.objects.exclude(
            status__in=['PENDING_TEAM', 'CANCELLED']
        ).order_by('-updated_at')

    history_apps = history_apps[:50]
    
    # 汇总库存
    raw_summary = ResourceInventory.objects.values('cardType', 'cardForm').annotate(
        total_sum=Sum('totalCount'),
        allocated_sum=Sum('allocatedCount')
    ).order_by('cardType', 'cardForm', 'total_sum')
    inventory_summary = []
    for item in raw_summary:
        card_type = item['cardType']
        card_form = item['cardForm']
        total = item['total_sum'] or 0
        allocated = item['allocated_sum'] or 0
        
        pre_allocated = Application.objects.filter(
            status='PENDING_FINAL',
            allocatedCardType=card_type,
            allocatedCardForm=card_form,
            allocatedCount__gt=0
        ).aggregate(sum_pre=Sum('allocatedCount'))['sum_pre'] or 0
        
        inventory_summary.append({
            'cardType': card_type,
            'cardForm': card_form,
            'totalCount': total,
            'allocatedCount': allocated,
            'preAllocatedCount': pre_allocated,
            'availableCount': total - allocated - pre_allocated,
        })
        
    # 所有项目名（用于筛选下拉，去重，在筛选之前获取以保证下拉菜单完整）
    all_projects = sorted(set(pending_apps.values_list('project', flat=True)))

    # 需求汇总 — 支持按项目筛选，对整个 pending_apps 进行整页过滤
    filter_project = request.GET.get('filter_project', '')
    if filter_project:
        pending_apps = pending_apps.filter(project=filter_project)

    pending_apps = list(pending_apps)

    # 为 PENDING_PRE 状态的申请单，附加 preempt_candidates
    for app in pending_apps:
        if app.status == 'PENDING_PRE':
            # 按卡型号匹配可抽调的候选（不限形态，因为分配形态可能与申请形态不同）
            app.preempt_candidates = get_preempt_candidates(app)

    # 统计
    total_apps_count = len(pending_apps)
    pre_allocated_apps_count = sum(1 for app in pending_apps if app.allocatedCount is not None and app.allocatedCount > 0)
    un_pre_allocated_apps_count = total_apps_count - pre_allocated_apps_count
    
    demand_summary = defaultdict(lambda: {'count': 0, 'minCount': 0, 'pre_allocated': 0})
    for app in pending_apps:
        key = (app.cardType, app.cardForm)
        demand_summary[key]['count'] += app.count
        demand_summary[key]['minCount'] += app.minCount
        if app.allocatedCount is not None:
            demand_summary[key]['pre_allocated'] += app.allocatedCount
            
    demand_list = []
    for (card_type, card_form), vals in demand_summary.items():
        demand_list.append({
            'cardType': card_type,
            'cardForm': card_form,
            'count': vals['count'],
            'minCount': vals['minCount'],
            'pre_allocated': vals['pre_allocated'],
        })
        
    # 按项目聚合
    project_map = defaultdict(list)
    for app in pending_apps:
        project_map[app.project].append(app)
        
    grouped_apps = []
    seen_projects = []
    for app in pending_apps:
        if app.project not in seen_projects:
            seen_projects.append(app.project)
            
    for project in seen_projects:
        apps = project_map[project]
        has_unallocated = any(a.status == 'PENDING_PRE' and a.allocatedCount is None for a in apps)
        has_preallocated = any(a.allocatedCount is not None and a.allocatedCount > 0 for a in apps)
        
        has_team_pending = any(a.status == 'PENDING_TEAM' for a in apps)
        has_pre_pending = any(a.status == 'PENDING_PRE' for a in apps)
        has_final_pending = any(a.status == 'PENDING_FINAL' for a in apps)
        
        grouped_apps.append({
            'project': project,
            'apps': apps,
            'count': len(apps),
            'total_requested': sum(a.count for a in apps),
            'total_min_requested': sum(a.minCount for a in apps),
            'has_unallocated': has_unallocated,
            'has_preallocated': has_preallocated,
            'has_team_pending': has_team_pending,
            'has_pre_pending': has_pre_pending,
            'has_final_pending': has_final_pending,
        })
        
    options = SystemOption.objects.all()
    inventory_ref_json = json.dumps(inventory_summary)
    
    context = {
        'pending_apps': pending_apps,
        'history_apps': history_apps,
        'grouped_apps': grouped_apps,
        'total_apps_count': total_apps_count,
        'pre_allocated_apps_count': pre_allocated_apps_count,
        'un_pre_allocated_apps_count': un_pre_allocated_apps_count,
        'demand_list': demand_list,
        'inventory_summary': inventory_summary,
        'inventory_ref_json': inventory_ref_json,
        'card_forms': options.filter(category='CARD_FORM'),
        'card_types': options.filter(category='CARD_TYPE'),
        'all_projects': all_projects,
        'filter_project': filter_project,
        'current_role': request.user.role,
        'active_tab': active_tab,
        'sidebar_counts': get_sidebar_counts(request.user),
    }
    return render(request, 'approve.html', context)

@login_required
def execute_view(request):
    if request.user.role not in ['EXECUTOR', 'ADMIN']:
        messages.error(request, '无权限访问执行页面。')
        return redirect('dashboard')
        
    # 读取自动释放开关配置
    auto_release_setting, _ = SystemSetting.objects.get_or_create(
        key='auto_release_enabled',
        defaults={'value': 'false', 'description': '是否启用自动释放已到期卡资源'}
    )
    auto_release_enabled = auto_release_setting.value == 'true'
        
    active_tab = request.GET.get('tab', 'pending')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # 切换自动释放配置
        if action == 'toggle_auto_release':
            if request.user.role not in ['EXECUTOR', 'ADMIN']:
                messages.error(request, '无权限修改自动释放配置。')
                return redirect('execute')
            auto_release_setting.value = 'false' if auto_release_enabled else 'true'
            auto_release_setting.save()
            new_status = '开启' if auto_release_setting.value == 'true' else '关闭'
            messages.success(request, f'成功将自动释放功能 {new_status}。')
            return redirect('execute')
            
        # 释放/归还资源
        if action == 'release':
            app_id = request.POST.get('app_id')
            with transaction.atomic():
                application = get_object_or_404(Application.objects.select_for_update(), id=app_id)
                
                # 安全校验：确保申请单仍处于已执行状态
                if application.status != 'EXECUTED':
                    messages.error(request, f'该申请不处于“已执行”状态（当前状态：{application.get_status_display()}），操作已取消。')
                    return redirect('/execute/?tab=history')
                    
                # 恢复库存数量，使用 select_for_update 行锁
                if application.allocation_details:
                    # 使用精准的拆分分配表恢复库存
                    for detail in application.allocation_details:
                        inv_id = detail.get('inventory_id')
                        count_to_return = detail.get('count', 0)
                        
                        inv = None
                        if inv_id:
                            try:
                                inv = ResourceInventory.objects.select_for_update().get(id=inv_id)
                            except ResourceInventory.DoesNotExist:
                                pass
                                
                        if not inv:
                            # 降级方案：根据卡池名称和地域等做模糊匹配归还
                            fallback_invs = ResourceInventory.objects.select_for_update().filter(
                                cardName=detail.get('cardName'),
                                cardType=application.allocatedCardType,
                                cardForm=application.allocatedCardForm,
                                region=detail.get('region')
                            )
                            if fallback_invs.exists():
                                inv = fallback_invs.first()
                                
                        if inv:
                            inv.allocatedCount = max(0, inv.allocatedCount - count_to_return)
                            inv.save()
                else:
                    # 兼容历史单值归还数据
                    inventories = ResourceInventory.objects.select_for_update().filter(
                        cardName=application.allocatedCardName,
                        cardType=application.allocatedCardType,
                        cardForm=application.allocatedCardForm,
                        region=application.allocatedRegion
                    )
                    if inventories.exists():
                        inv = inventories.first()
                        inv.allocatedCount = max(0, inv.allocatedCount - (application.allocatedCount or 0))
                        inv.save()
                
                # 自动释放绑定的物料资产
                allocations = AssetAllocation.objects.select_for_update().filter(application=application)
                released_count = allocations.count()
                for alloc in allocations:
                    asset = alloc.asset
                    asset.used_cards = max(0, asset.used_cards - alloc.allocated_cards)
                    if asset.used_cards <= 0:
                        asset.status = 'IDLE'
                    else:
                        asset.status = 'PARTIAL'
                    alloc.delete()
                    refresh_asset_summary(asset)
                    
                application.status = 'RELEASED'
                application.save()
                
            msg = f'已成功释放项目「{application.project}」占用的资源，对应卡资源库存已恢复。'
            if released_count > 0:
                msg += f' 同时已自动释放并解绑了 {released_count} 台物理/虚拟物料设备。'
            messages.success(request, msg)
            return redirect('/execute/?tab=history')
            
        # 标记为已执行 (默认行为)
        app_id = request.POST.get('app_id')
        executionResult = request.POST.get('executionResult')
        
        with transaction.atomic():
            application = get_object_or_404(Application.objects.select_for_update(), id=app_id)
            
            # 安全校验：确保申请单仍处于已审批（待执行）状态
            if application.status != 'APPROVED':
                messages.error(request, f'该申请不处于“已审批(待执行)”状态（当前状态：{application.get_status_display()}），操作已取消。')
                return redirect('execute')
                
            selected_card_dict = {}
            
            for asset_id_str in request.POST.getlist('selected_assets'):
                try:
                    asset_id = int(asset_id_str)
                    cards = int(request.POST.get(f'asset_card_{asset_id_str}', 0))
                except (TypeError, ValueError):
                    messages.error(request, '物料资产选择数据不合法，请重新选择。')
                    return redirect('execute')
                if cards > 0:
                    selected_card_dict[asset_id] = selected_card_dict.get(asset_id, 0) + cards

            selected_card_total = sum(selected_card_dict.values())
            if selected_card_total > (application.allocatedCount or 0):
                messages.error(request, f'绑定物料卡数不能超过审批分配数量（{application.allocatedCount or 0} 张）。')
                return redirect('execute')

            selected_assets = {
                asset.id: asset
                for asset in ResourceAsset.objects.select_for_update().filter(id__in=selected_card_dict.keys())
            }
            if len(selected_assets) != len(selected_card_dict):
                messages.error(request, '所选物料资产不存在或已被删除，请重新选择。')
                return redirect('execute')

            for asset_id, cards in selected_card_dict.items():
                asset = selected_assets[asset_id]
                available_cards = max(0, asset.card_count - asset.used_cards)
                if cards > available_cards:
                    messages.error(request, f'物料「{asset.name}」剩余 {available_cards} 张卡，不能分配 {cards} 张。')
                    return redirect('execute')

            if application.coordination_details:
                required_preempt_cards = sum(c['count'] for c in application.coordination_details)
                old_app_map = defaultdict(list)
                selected_preempt_cards = 0
                
                for cand_dict in application.coordination_details:
                    cand_id = cand_dict['app_id']
                    try:
                        cand_app = Application.objects.get(id=cand_id)
                    except Application.DoesNotExist:
                        continue
                        
                    cand_preempt_asset_ids = request.POST.getlist(f'preempted_assets_{cand_id}')
                    for asset_id_str in cand_preempt_asset_ids:
                        cards_to_preempt = int(request.POST.get(f'preempt_card_{cand_id}_{asset_id_str}', 0))
                        if cards_to_preempt > 0:
                            asset = ResourceAsset.objects.select_for_update().get(id=int(asset_id_str))
                            old_app_map[cand_app].append((asset, cards_to_preempt))
                            selected_preempt_cards += cards_to_preempt
                            selected_card_dict[int(asset_id_str)] = selected_card_dict.get(int(asset_id_str), 0) + cards_to_preempt
                            selected_assets[asset.id] = asset
                
                if selected_preempt_cards < required_preempt_cards:
                    messages.error(request, f'剥夺失败：协调方案要求至少剥夺 {required_preempt_cards} 张卡，但您仅选择了 {selected_preempt_cards} 张。')
                    return redirect('execute')
                    
                for old_app, asset_tuples in old_app_map.items():
                    asset_names = [f"{a.name}(剥夺{c}卡)" for a, c in asset_tuples]
                    preempted_card_total = sum(c for a, c in asset_tuples)
                    
                    old_app.allocatedCount = max(0, old_app.allocatedCount - preempted_card_total)
                    old_app.executionResult = f"[紧急抽调] 被 {application.project} 剥夺设备: {', '.join(asset_names)}\n" + (old_app.executionResult or '')
                    old_app.save()
                    
                    inventories = ResourceInventory.objects.select_for_update().filter(
                        cardType=old_app.allocatedCardType,
                        cardForm=old_app.allocatedCardForm,
                    )
                    if inventories.exists():
                        inv = inventories.first()
                        inv.allocatedCount = max(0, inv.allocatedCount - preempted_card_total)
                        inv.save()
                        
                    SystemNotificationLog.objects.create(
                        receiver_email=old_app.applicant.email or old_app.applicant.username,
                        content=f"【资源抽调通知】由于紧急调度，您的项目「{old_app.project}」被抽调了 {preempted_card_total} 张卡: {', '.join(asset_names)}。"
                    )
                    
                    for pa, c in asset_tuples:
                        try:
                            alloc = AssetAllocation.objects.get(asset=pa, application=old_app)
                            alloc.allocated_cards -= c
                            if alloc.allocated_cards <= 0:
                                alloc.delete()
                            else:
                                alloc.save()
                        except AssetAllocation.DoesNotExist:
                            pass
                        
                        pa.used_cards = max(0, pa.used_cards - c)
                        pa.save()
                        refresh_asset_summary(pa)

            selected_card_total = sum(selected_card_dict.values())
            if selected_card_total > (application.allocatedCount or 0):
                messages.error(request, f'绑定物料卡数不能超过审批分配数量（{application.allocatedCount or 0} 张）。')
                return redirect('execute')

            assigned_assets_info = []
            for asset_id, cards in selected_card_dict.items():
                asset = selected_assets[asset_id]
                asset.used_cards += cards
                if asset.used_cards >= asset.card_count:
                    asset.status = 'IN_USE'
                else:
                    asset.status = 'PARTIAL'
                asset.save()
                
                alloc, created = AssetAllocation.objects.get_or_create(
                    asset=asset,
                    application=application,
                    defaults={'allocated_cards': cards}
                )
                if not created:
                    alloc.allocated_cards += cards
                    alloc.save()
                    
                refresh_asset_summary(asset)
                assigned_assets_info.append(f"{asset.name}(分配{cards}卡)")
            
            actual_card_count = selected_card_total
            adjusted = False
            diff = 0
            if actual_card_count > 0 and actual_card_count < application.allocatedCount:
                diff = application.allocatedCount - actual_card_count
                adjusted = True
                
                # 调整库存，归还多预留的库存
                if application.allocation_details:
                    remaining_to_return = diff
                    new_details = []
                    for detail in application.allocation_details:
                        inv_id = detail.get('inventory_id')
                        allocated_in_detail = detail.get('count', 0)
                        
                        if remaining_to_return > 0 and allocated_in_detail > 0:
                            to_return = min(remaining_to_return, allocated_in_detail)
                            
                            inv = None
                            if inv_id:
                                try:
                                    inv = ResourceInventory.objects.select_for_update().get(id=inv_id)
                                except ResourceInventory.DoesNotExist:
                                    pass
                            if not inv:
                                fallback_invs = ResourceInventory.objects.select_for_update().filter(
                                    cardName=detail.get('cardName'),
                                    cardType=application.allocatedCardType,
                                    cardForm=application.allocatedCardForm,
                                    region=detail.get('region')
                                )
                                if fallback_invs.exists():
                                    inv = fallback_invs.first()
                            
                            if inv:
                                inv.allocatedCount = max(0, inv.allocatedCount - to_return)
                                inv.save()
                                
                            detail['count'] = allocated_in_detail - to_return
                            remaining_to_return -= to_return
                            
                        if detail.get('count', 0) > 0:
                            new_details.append(detail)
                            
                    application.allocation_details = new_details
                else:
                    # 历史数据兼容降级：直接尝试根据单值属性匹配归还
                    inventories = ResourceInventory.objects.select_for_update().filter(
                        cardName=application.allocatedCardName,
                        cardType=application.allocatedCardType,
                        cardForm=application.allocatedCardForm,
                        region=application.allocatedRegion
                    )
                    if inventories.exists():
                        inv = inventories.first()
                        inv.allocatedCount = max(0, inv.allocatedCount - diff)
                        inv.save()
                        
                # 更新申请单的实际分配数量
                application.allocatedCount = actual_card_count
            
            application.status = 'EXECUTED'
            if assigned_assets_info:
                prefix = f"[已自动绑定物料: {', '.join(assigned_assets_info)}] "
                application.executionResult = prefix + executionResult
            else:
                application.executionResult = executionResult
                
            application.save()
            
        if adjusted:
            messages.success(request, f'已标记 {application.project} 的分配为已执行。实际执行 {actual_card_count} 卡（已将余下 {diff} 卡释放回库存）。')
        else:
            messages.success(request, f'已标记 {application.project} 的分配为已执行。')
        return redirect('/execute/?tab=pending')
        
    approved_apps = Application.objects.filter(status='APPROVED').order_by('updated_at')
    executed_apps = Application.objects.filter(status__in=['EXECUTED', 'RELEASED']).order_by('-updated_at')[:50]
    
    # 动态匹配闲置的资产及附加协调方案详情
    for app in approved_apps:
        app.idle_assets_matching = ResourceAsset.objects.filter(
            card_type=app.allocatedCardType,
            card_form=app.allocatedCardForm,
            status__in=['IDLE', 'PARTIAL']
        ).order_by('name')
        
        for asset in app.idle_assets_matching:
            asset.remaining_cards = asset.card_count - asset.used_cards
            
        if app.coordination_details:
            coord_objs = []
            for coord in app.coordination_details:
                try:
                    cand = Application.objects.get(id=coord['app_id'])
                    allocations = AssetAllocation.objects.filter(application=cand)
                    assets_info = []
                    for alloc in allocations:
                        asset_obj = alloc.asset
                        asset_obj.allocated_cards = alloc.allocated_cards
                        assets_info.append(asset_obj)
                    coord_objs.append({
                        'app_id': cand.id,
                        'project': cand.project,
                        'count': coord['count'],
                        'assets': assets_info
                    })
                except Application.DoesNotExist:
                    pass
            app.coord_objs = coord_objs
        
    # 计算每个申请单的紧迫度（距离 endDate 剩余天数）
    today = date.today()
    for app in approved_apps:
        if app.endDate:
            days_left = (app.endDate - today).days
            app.days_until_end = days_left
            app.is_urgent = days_left <= 1  # 明天到期或已过期
        else:
            app.days_until_end = None
            app.is_urgent = False
    
    # 将紧急的排在前面
    urgent_apps = [a for a in approved_apps if a.is_urgent]
    normal_apps = [a for a in approved_apps if not a.is_urgent]
    
    context = {
        'approved_apps': approved_apps,
        'urgent_apps': urgent_apps,
        'normal_apps': normal_apps,
        'executed_apps': executed_apps,
        'current_role': request.user.role,
        'active_tab': active_tab,
        'sidebar_counts': get_sidebar_counts(request.user),
        'auto_release_enabled': auto_release_enabled,
    }
    return render(request, 'execute.html', context)

@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, '密码修改成功！')
            return redirect('dashboard')
        else:
            messages.error(request, '请纠正表单中的错误。')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'change_password.html', {'form': form, 'sidebar_counts': get_sidebar_counts(request.user)})


@login_required
def asset_management_view(request):
    # 所有登录角色均可访问页面 (查看及筛选)
    # 但密码和增删改只有管理员和执行人有权限
    is_admin_or_executor = request.user.role in ['EXECUTOR', 'ADMIN']
    
    if request.method == 'POST':
        # 如果不是管理员或执行人，拦截 POST CRUD 请求
        if not is_admin_or_executor:
            messages.error(request, '您无权进行此操作。')
            return redirect('assets')
            
        action = request.POST.get('action')
        
        if action == 'add':
            name = request.POST.get('name')
            ip = request.POST.get('ip', '')
            password = request.POST.get('password', '')
            owner_id = request.POST.get('owner')
            current_users = request.POST.get('current_users', '')
            card_type = request.POST.get('card_type', '')
            card_form = request.POST.get('card_form', '')
            card_count = request.POST.get('card_count', '8')
            try:
                card_count = int(card_count)
            except (ValueError, TypeError):
                card_count = 8
            status = request.POST.get('status', 'IDLE')
            app_name = request.POST.get('app_name', '')
            region = request.POST.get('region', '')
            specifications = request.POST.get('specifications', '')
            
            owner = None
            if owner_id:
                try:
                    owner = CustomUser.objects.get(id=owner_id)
                except CustomUser.DoesNotExist:
                    pass
            
            ResourceAsset.objects.create(
                name=name,
                ip=ip,
                password=password,
                owner=owner,
                current_users=current_users,
                card_type=card_type,
                card_form=card_form,
                card_count=card_count,
                status=status,
                app_name=app_name,
                region=region,
                specifications=specifications
            )
            messages.success(request, '成功添加物料资产！')
            return redirect('assets')
            
        elif action == 'edit':
            asset_id = request.POST.get('asset_id')
            asset = get_object_or_404(ResourceAsset, id=asset_id)
            
            asset.name = request.POST.get('name')
            asset.ip = request.POST.get('ip', '')
            asset.password = request.POST.get('password', '')
            
            owner_id = request.POST.get('owner')
            if owner_id:
                try:
                    asset.owner = CustomUser.objects.get(id=owner_id)
                except CustomUser.DoesNotExist:
                    asset.owner = None
            else:
                asset.owner = None
                
            asset.current_users = request.POST.get('current_users', '')
            asset.card_type = request.POST.get('card_type', '')
            asset.card_form = request.POST.get('card_form', '')
            card_count_str = request.POST.get('card_count', '8')
            try:
                asset.card_count = int(card_count_str)
            except (ValueError, TypeError):
                asset.card_count = 8
            asset.status = request.POST.get('status', 'IDLE')
            asset.app_name = request.POST.get('app_name', '')
            asset.region = request.POST.get('region', '')
            asset.specifications = request.POST.get('specifications', '')
            try:
                asset.full_clean()
                asset.save()
                messages.success(request, '物料资产已成功更新！')
            except Exception as e:
                err_msg = str(e)
                if hasattr(e, 'message_dict'):
                    err_msg = "; ".join([f"{k}: {', '.join(v)}" for k, v in e.message_dict.items()])
                elif hasattr(e, 'messages'):
                    err_msg = "; ".join(e.messages)
                messages.error(request, f'物料资产更新失败：{err_msg}')
            return redirect('assets')
            
        elif action == 'delete':
            asset_id = request.POST.get('asset_id')
            asset = get_object_or_404(ResourceAsset, id=asset_id)
            if asset.status == 'IN_USE':
                messages.error(request, f'无法删除资产「{asset.name}」：该资产当前处于“使用中”状态。请先在执行管理页面中释放相关资源，再进行删除。')
                return redirect('assets')
            asset.delete()
            messages.success(request, '物料资产已成功删除。')
            return redirect('assets')
            
    # GET 逻辑
    assets = ResourceAsset.objects.all().order_by('-created_at')
    
    # 选项获取 (用于弹框中的选项)
    options = SystemOption.objects.all()
    card_types = options.filter(category='CARD_TYPE')
    card_forms = options.filter(category='CARD_FORM')
    regions = options.filter(category='REGION')
    
    # 获取所有的 CustomUser (作为当前责任人的选项)
    all_users = CustomUser.objects.all().order_by('username')
    
    context = {
        'assets': assets,
        'card_types': card_types,
        'card_forms': card_forms,
        'regions': regions,
        'all_users': all_users,
        'is_admin_or_executor': is_admin_or_executor,
        'current_role': request.user.role,
        'sidebar_counts': get_sidebar_counts(request.user),
    }
    return render(request, 'assets.html', context)


@login_required
def statistics_view(request):
    # 获取筛选参数
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    filter_card_type = request.GET.get('card_type', '')
    
    # 筛选状态为已审批、已执行、已释放的申请单
    apps_query = Application.objects.filter(status__in=['APPROVED', 'EXECUTED', 'RELEASED'])
    
    # 应用卡型号过滤
    if filter_card_type:
        apps_query = apps_query.filter(cardType=filter_card_type)
        
    # 时间段过滤
    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
            apps_query = apps_query.filter(Q(endDate__gte=start_date) | Q(startDate__gte=start_date))
        except ValueError:
            pass
            
    if end_date_str:
        try:
            end_date = date.fromisoformat(end_date_str)
            apps_query = apps_query.filter(startDate__lte=end_date)
        except ValueError:
            pass

    # 数据库级别高性能聚合：各团队+卡型号，以及各项目+卡型号
    from django.db.models import Sum, Count

    team_stats_qs = apps_query.values('team', 'cardType').annotate(
        total_cards=Sum('card_count'),
        total_card_days=Sum('card_days'),
        app_count=Count('id')
    ).order_by('-total_cards')

    project_stats_qs = apps_query.values('project', 'cardType').annotate(
        total_cards=Sum('card_count'),
        total_card_days=Sum('card_days'),
        app_count=Count('id')
    ).order_by('-total_cards')

    # 转换为排序的列表
    team_list = []
    for item in team_stats_qs:
        team_list.append({
            'team': item['team'],
            'card_type': item['cardType'],
            'total_cards': item['total_cards'] or 0,
            'total_card_days': item['total_card_days'] or 0,
            'app_count': item['app_count'] or 0
        })
    
    project_list = []
    for item in project_stats_qs:
        project_list.append({
            'project': item['project'],
            'card_type': item['cardType'],
            'total_cards': item['total_cards'] or 0,
            'total_card_days': item['total_card_days'] or 0,
            'app_count': item['app_count'] or 0
        })
    
    grand_total_cards = sum(x['total_cards'] for x in team_list)
    grand_total_card_days = sum(x['total_card_days'] for x in team_list)
    grand_total_apps = sum(x['app_count'] for x in team_list)
    
    all_card_types = sorted(list(SystemOption.objects.filter(category='CARD_TYPE').values_list('value', flat=True).distinct()))
    
    context = {
        'team_list': team_list,
        'project_list': project_list,
        'all_card_types': all_card_types,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'selected_card_type': filter_card_type,
        'grand_total_cards': grand_total_cards,
        'grand_total_card_days': grand_total_card_days,
        'grand_total_apps': grand_total_apps,
        'sidebar_counts': get_sidebar_counts(request.user),
    }
    return render(request, 'statistics.html', context)


@login_required
def feedback_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'submit':
            title = request.POST.get('title')
            content = request.POST.get('content')
            images = request.FILES.getlist('images')
            
            if not title or not content:
                messages.error(request, '标题或内容不能为空。')
                return redirect('feedback')
                
            # 校验图片
            valid_images = []
            allowed_exts = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
            for img in images:
                ext = os.path.splitext(img.name)[1].lower()
                if ext not in allowed_exts:
                    messages.error(request, f'提交失败：文件「{img.name}」格式不符合图片要求（仅支持 .png, .jpg, .jpeg, .gif, .webp）。')
                    return redirect('feedback')
                if img.size > 5 * 1024 * 1024:
                    messages.error(request, f'提交失败：文件「{img.name}」大小超过 5MB 限制。')
                    return redirect('feedback')
                img.name = f"{uuid.uuid4()}{ext}"
                valid_images.append(img)
                
            fb = IssueFeedback.objects.create(
                user=request.user,
                title=title,
                content=content,
                status='PENDING'
            )
            
            for img in valid_images:
                FeedbackImage.objects.create(feedback=fb, image=img)
                
            messages.success(request, '问题反馈已成功提交，感谢您的建议！')
            return redirect('feedback')
            
        elif action == 'edit':
            feedback_id = request.POST.get('feedback_id')
            feedback = get_object_or_404(IssueFeedback, id=feedback_id)
            
            if feedback.user != request.user and request.user.role != 'ADMIN':
                messages.error(request, '您无权编辑此反馈。')
                return redirect('feedback')
                
            if feedback.status != 'PENDING':
                messages.error(request, '该反馈已解决，禁止编辑。')
                return redirect('feedback')
                
            title = request.POST.get('title')
            content = request.POST.get('content')
            images_to_delete = request.POST.getlist('delete_images')
            new_images = request.FILES.getlist('images')
            
            if not title or not content:
                messages.error(request, '标题或内容不能为空。')
                return redirect('feedback')
                
            # 校验新上传的图片
            valid_images = []
            allowed_exts = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
            for img in new_images:
                ext = os.path.splitext(img.name)[1].lower()
                if ext not in allowed_exts:
                    messages.error(request, f'保存失败：新文件「{img.name}」格式不符合图片要求（仅支持 .png, .jpg, .jpeg, .gif, .webp）。')
                    return redirect('feedback')
                if img.size > 5 * 1024 * 1024:
                    messages.error(request, f'保存失败：新文件「{img.name}」大小超过 5MB 限制。')
                    return redirect('feedback')
                img.name = f"{uuid.uuid4()}{ext}"
                valid_images.append(img)
                
            feedback.title = title
            feedback.content = content
            feedback.save()
            
            if images_to_delete:
                FeedbackImage.objects.filter(id__in=images_to_delete, feedback=feedback).delete()
                
            for img in valid_images:
                FeedbackImage.objects.create(feedback=feedback, image=img)
                
            messages.success(request, '反馈信息已成功修改！')
            return redirect('feedback')
            
        elif action == 'delete':
            feedback_id = request.POST.get('feedback_id')
            feedback = get_object_or_404(IssueFeedback, id=feedback_id)
            
            if feedback.user != request.user and request.user.role != 'ADMIN':
                messages.error(request, '您无权删除此反馈。')
                return redirect('feedback')
                
            feedback.delete()
            messages.success(request, '反馈记录已成功删除！')
            return redirect('feedback')
            
        elif action == 'resolve':
            if request.user.role not in ['EXECUTOR', 'ADMIN']:
                messages.error(request, '您无权执行此操作。')
                return redirect('feedback')
                
            feedback_id = request.POST.get('feedback_id')
            feedback = get_object_or_404(IssueFeedback, id=feedback_id)
            feedback.status = 'RESOLVED'
            feedback.save()
            messages.success(request, '反馈问题已标记为已解决状态！')
            return redirect('feedback')
            
    # GET 逻辑：所有人都可以查阅全员提交的所有反馈单
    feedbacks = IssueFeedback.objects.all().order_by('-created_at')
    
    context = {
        'feedbacks': feedbacks,
        'current_role': request.user.role,
        'sidebar_counts': get_sidebar_counts(request.user),
    }
    return render(request, 'feedback.html', context)


from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

@login_required
def remind_view(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '仅支持 POST 请求。'})
        
    app_id = request.POST.get('app_id')
    application = get_object_or_404(Application, id=app_id)
    
    # 只能由申请人或管理员发起催办
    if application.applicant != request.user and request.user.role != 'ADMIN':
        return JsonResponse({'success': False, 'message': '您无权催办此申请。'})
        
    status = application.status
    receivers = []
    stage_desc = ""
    target_url = ""
    host = request.get_host()
    scheme = 'https' if request.is_secure() else 'http'
    
    if status == 'PENDING_TEAM':
        stage_desc = "待组长审批"
        # 寻找同团队的组长
        team_leaders = CustomUser.objects.filter(roles__contains='TEAM_LEADER', team=application.team)
        receivers = [u.email for u in team_leaders]
        target_url = f"{scheme}://{host}/approve/?tab=pending#project-{application.project}"
        
    elif status == 'PENDING_PRE':
        stage_desc = "待资源预审"
        approvers = CustomUser.objects.filter(roles__contains='APPROVER')
        receivers = [u.email for u in approvers]
        target_url = f"{scheme}://{host}/approve/?tab=pending#project-{application.project}"
        
    elif status == 'PENDING_FINAL':
        stage_desc = "待部门终审"
        dept_heads = CustomUser.objects.filter(roles__contains='DEPT_HEAD')
        receivers = [u.email for u in dept_heads]
        target_url = f"{scheme}://{host}/approve/?tab=pending#project-{application.project}"
        
    elif status == 'APPROVED':
        stage_desc = "已审批，待执行"
        executors = CustomUser.objects.filter(roles__contains='EXECUTOR')
        receivers = [u.email for u in executors]
        target_url = f"{scheme}://{host}/execute/?tab=pending"
        
    else:
        return JsonResponse({'success': False, 'message': f'当前状态「{application.get_status_display()}」无需催办。'})
        
    if not receivers:
        return JsonResponse({'success': False, 'message': f'当前环节「{stage_desc}」暂未配置对应处理人。'})
        
    content = f"【卡管理系统提醒】您有待决策或待执行的内容。项目名称：{application.project}，申请人：{application.applicant.username}，当前环节：{stage_desc}。请点击链接处理：{target_url}"
    
    # 异步发送提醒消息
    def send_remind_async(url, text, r_list, log_id):
        errors = []
        success_count = 0
        for r in r_list:
            try:
                data = {
                    'content': text,
                    'receiver': r
                }
                res = requests.post(url, json=data, timeout=5)
                if res.status_code == 200:
                    success_count += 1
                else:
                    errors.append(f"发送至账号 {r} 失败: HTTP {res.status_code} ({res.text[:200]})")
            except Exception as e:
                errors.append(f"发送至账号 {r} 失败: {str(e)}")
        
        if not errors:
            SystemNotificationLog.objects.filter(id=log_id).update(status='SUCCESS')
        else:
            err_msg = "\n".join(errors)
            new_status = 'FAILED' if success_count == 0 else 'SUCCESS'
            SystemNotificationLog.objects.filter(id=log_id).update(status=new_status, error_message=err_msg)

    api_url = getattr(settings, 'REMIND_API_URL', 'http://127.0.0.1:8000/mock-notification-api/')
    
    # 创建通知日志记录
    log_entry = SystemNotificationLog.objects.create(
        sender=request.user,
        receiver_email=", ".join(receivers),
        content=content,
        status='PENDING'
    )
    
    threading.Thread(target=send_remind_async, args=(api_url, content, receivers, log_entry.id), daemon=True).start()
    
    return JsonResponse({
        'success': True,
        'message': f"已在后台发起催办提醒！将推送到当前环节的所有处理人: {', '.join(receivers)}"
    })
@login_required
def get_asset_password(request):
    asset_id = request.GET.get('asset_id')
    if not asset_id:
        return JsonResponse({'error': '缺少 asset_id 参数。'}, status=400)
    asset = get_object_or_404(ResourceAsset, id=asset_id)
    
    has_permission = False
    if request.user.role in ['EXECUTOR', 'ADMIN']:
        has_permission = True
    else:
        allocs = AssetAllocation.objects.filter(
            asset=asset, 
            application__applicant=request.user, 
            application__status='EXECUTED'
        ).select_related('application')
        has_permission = any(
            is_bare_metal_allocation(alloc.application, asset)
            for alloc in allocs
        )
            
    if not has_permission:
        return JsonResponse({'error': '无权限访问。'}, status=403)
        
    return JsonResponse({'password': asset.password or ''})

@login_required
def get_application_details(request):
    app_id = request.GET.get('app_id')
    if not app_id:
        return JsonResponse({'error': '缺少 app_id 参数。'}, status=400)
    
    app = get_object_or_404(Application, id=app_id)
    
    # Permission check
    has_permission = False
    if request.user == app.applicant or request.user.role in ['ADMIN', 'EXECUTOR', 'APPROVER', 'TEAM_LEADER', 'DEPT_HEAD']:
        has_permission = True
        
    if not has_permission:
        return JsonResponse({'error': '无权限查看该申请单详情。'}, status=403)
        
    # Get bound assets
    assets = []
    can_view_asset_password = (
        request.user == app.applicant or request.user.role in ['ADMIN', 'EXECUTOR']
    ) and app.status == 'EXECUTED'
    for alloc in app.asset_allocations.select_related('asset'):
        asset = alloc.asset
        assets.append({
            'id': asset.id,
            'name': asset.name,
            'ip': asset.ip or '',
            'region': asset.region or '',
            'status': asset.get_status_display(),
            'specifications': asset.specifications or '',
            'allocated_cards': alloc.allocated_cards,
            'has_password_permission': can_view_asset_password and is_bare_metal_allocation(app, asset)
        })
        
    data = {
        'id': app.id,
        'applicant': app.applicant.username,
        'team': app.team,
        'project': app.project,
        'users': app.users,
        'cardForm': app.cardForm,
        'cardType': app.cardType,
        'count': app.count,
        'minCount': app.minCount,
        'startDate': app.startDate.strftime('%Y-%m-%d') if app.startDate else '',
        'endDate': app.endDate.strftime('%Y-%m-%d') if app.endDate else '',
        'duration': app.duration,
        'priority': app.get_priority_display(),
        'priorityReason': app.priorityReason,
        'purpose': app.purpose,
        'note': app.note or '',
        'status': app.status,
        'status_display': app.get_status_display(),
        'created_at': app.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'team_leader_note': app.team_leader_note or '',
        'pre_approver_note': app.pre_approver_note or '',
        'final_approver_note': app.final_approver_note or '',
        'approvalNote': app.approvalNote or '',
        'allocatedCount': app.allocatedCount,
        'allocatedCardType': app.allocatedCardType or '',
        'allocatedCardForm': app.allocatedCardForm or '',
        'allocatedRegion': app.allocatedRegion or '',
        'allocatedCardName': app.allocatedCardName or '',
        'executionResult': app.executionResult or '',
        'attachment_url': app.attachment.url if app.attachment else '',
        'assets': assets
    }
    return JsonResponse(data)


@csrf_exempt
def mock_notification_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        content = data.get('content', '')
        receiver = data.get('receiver', '')
        
        # 控制台打印催办信息，高亮提示
        print("\n" + "="*80)
        print(f"📡 [MOCK NOTIFICATION RECEIVER] NEW MESSAGE RECEIVED!")
        print(f"👤 Receiver: {receiver}")
        print(f"📝 Content: {content}")
        print("="*80 + "\n")
        
        return JsonResponse({'status': 'ok', 'message': 'Notification received and printed.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


from django.contrib.auth.views import LoginView

class CustomLoginView(LoginView):
    template_name = 'login.html'
    
    def form_valid(self, form):
        user = form.get_user()
        login_role = self.request.POST.get('login_role')
        roles_list = getattr(user, 'roles', '').split(',') if getattr(user, 'roles', '') else ['APPLICANT']

        if login_role:
            if login_role not in roles_list:
                if login_role == 'APPLICANT':
                    login_role = roles_list[0] if roles_list else 'APPLICANT'
                else:
                    from django.contrib import messages
                    messages.error(self.request, f"登录被拒绝：您当前的账号未被授予该角色权限。")
                    from django.shortcuts import redirect
                    return redirect('login')
                
        response = super().form_valid(form)
        if login_role and login_role in roles_list:
            self.request.session['active_role'] = login_role
            
        return response

from django.http import JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def get_user_roles_api(request):
    username = request.GET.get('username')
    if not username:
        return JsonResponse({'roles': []})
    try:
        user = CustomUser.objects.get(username=username)
        roles = [r.strip() for r in user.roles.split(',') if r.strip()] if getattr(user, 'roles', '') else ['APPLICANT']
        return JsonResponse({'roles': roles})
    except CustomUser.DoesNotExist:
        return JsonResponse({'roles': []})
