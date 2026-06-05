from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from .models import CustomUser, SystemOption, ResourceInventory, Application, ResourceAsset, IssueFeedback, SystemSetting, FeedbackImage, SystemNotificationLog

class CustomUserCreationForm(forms.ModelForm):
    roles = forms.MultipleChoiceField(choices=CustomUser.ROLE_CHOICES, label='用户角色(多选)', widget=forms.CheckboxSelectMultiple, initial=['APPLICANT'])
    team = forms.ChoiceField(choices=[], label='所属团队', required=False)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'roles', 'team', 'is_staff', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        teams = SystemOption.objects.filter(category='TEAM').values_list('value', 'value')
        self.fields['team'].choices = [('', '---------')] + list(teams)
        if self.instance and self.instance.pk and self.instance.roles:
            self.initial['roles'] = self.instance.roles.split(',')

    def clean_roles(self):
        return ','.join(self.cleaned_data['roles'])

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password('123456')
        if commit:
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    roles = forms.MultipleChoiceField(choices=CustomUser.ROLE_CHOICES, label='用户角色(多选)', widget=forms.CheckboxSelectMultiple)
    team = forms.ChoiceField(choices=[], label='所属团队', required=False)

    class Meta:
        model = CustomUser
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        teams = SystemOption.objects.filter(category='TEAM').values_list('value', 'value')
        self.fields['team'].choices = [('', '---------')] + list(teams)
        if self.instance and self.instance.pk and self.instance.roles:
            self.initial['roles'] = self.instance.roles.split(',')

    def clean_roles(self):
        return ','.join(self.cleaned_data['roles'])


class RolesListFilter(admin.SimpleListFilter):
    title = '用户角色(多选)'
    parameter_name = 'roles'

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)
        distinct_roles = set(qs.values_list('roles', flat=True))
        choices = []
        choices_dict = dict(CustomUser.ROLE_CHOICES)
        for r in distinct_roles:
            if not r:
                continue
            roles_list = [item.strip() for item in r.split(',') if item.strip()]
            display_list = [choices_dict.get(item, item) for item in roles_list]
            display_name = ",".join(display_list)
            choices.append((r, display_name))
        return sorted(choices, key=lambda x: x[1])

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(roles=self.value())
        return queryset


class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'roles', 'team', 'is_staff', 'is_active'),
        }),
    )
    fieldsets = (
        (None, {'fields': ('username',)}),
        ('个人信息', {'fields': ('first_name', 'last_name', 'email')}),
        ('角色与密码安全', {'fields': ('roles', 'team', 'reset_password_button')}),
        ('权限', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('重要日期', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'roles_display', 'team', 'is_staff')
    list_filter = (RolesListFilter, 'team', 'is_staff', 'is_superuser', 'is_active')
    actions = ['reset_password_to_default']
    readonly_fields = ('reset_password_button',)
    change_list_template = "admin/customuser/change_list.html"

    def roles_display(self, obj):
        return obj.get_role_display()
    roles_display.short_description = '用户角色'

    def reset_password_to_default(self, request, queryset):
        for user in queryset:
            user.set_password('123456')
            user.save()
        self.message_user(request, f'成功重置了 {queryset.count()} 个用户的密码为 123456。')
    reset_password_to_default.short_description = '重置选中用户的密码为 123456'

    def reset_password_button(self, obj):
        if obj.pk:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:reset-user-password', args=[obj.pk])
            return format_html('<a class="button" href="{}" style="background: #6366f1; color: white; padding: 5px 12px; border-radius: 4px; font-weight: bold; text-decoration: none;">重置密码为 123456</a>', url)
        return "保存用户后可以重置密码"
    reset_password_button.short_description = "重置密码"

    def get_urls(self):
        urls = super().get_urls()
        from django.urls import path
        custom_urls = [
            path('<id>/reset-password/', self.admin_site.admin_view(self.reset_password_view), name='reset-user-password'),
            path('bulk-import/', self.admin_site.admin_view(self.bulk_import_view), name='customuser-bulk-import'),
        ]
        return custom_urls + urls

    def reset_password_view(self, request, id):
        from django.shortcuts import get_object_or_404, redirect
        user = get_object_or_404(CustomUser, pk=id)
        user.set_password('123456')
        user.save()
        self.message_user(request, f'成功将用户 {user.username} 的密码重置为 123456。')
        return redirect('admin:resource_app_customuser_change', id)

    def bulk_import_view(self, request):
        if request.method == 'POST':
            role = request.POST.get('role')
            bulk_data = request.POST.get('bulk_data', '')
            lines = [line.strip() for line in bulk_data.split('\n') if line.strip()]
            success_count = 0
            duplicate_count = 0
            updated_count = 0
            fail_count = 0
            errors = []
            
            from django.db import transaction
            from django.core.exceptions import ValidationError

            # 获取系统中已配置的团队选项集合
            valid_teams = set(SystemOption.objects.filter(category='TEAM').values_list('value', flat=True))

            try:
                with transaction.atomic():
                    for line_idx, line in enumerate(lines, 1):
                        # 支持逗号、Tab 列切分，提取第一列为用户名，第二列为所属团队或邮箱，第三列为邮箱
                        parts = line.split('\t')
                        if len(parts) < 2:
                            parts = line.split(',')
                        
                        username = parts[0].strip()
                        if not username:
                            continue
                        
                        team_val = None
                        email_val = None
                        
                        if len(parts) == 2:
                            col2 = parts[1].strip()
                            if '@' in col2:
                                email_val = col2
                            else:
                                team_val = col2
                        elif len(parts) >= 3:
                            team_val = parts[1].strip()
                            email_val = parts[2].strip()
                            
                        if team_val == '':
                            team_val = None
                        if email_val == '':
                            email_val = None
                        
                        if team_val and team_val not in valid_teams:
                            fail_count += 1
                            errors.append(f"第 {line_idx} 行：团队「{team_val}」在系统配置中不存在。")
                            continue
                        
                        existing_user = CustomUser.objects.filter(username=username).first()
                        if existing_user:
                            updated = False
                            if not existing_user.team and team_val:
                                existing_user.team = team_val
                                updated = True
                            if not existing_user.email and email_val:
                                existing_user.email = email_val
                                updated = True
                            if updated:
                                try:
                                    existing_user.full_clean()
                                    existing_user.save()
                                    updated_count += 1
                                except ValidationError as ve:
                                    fail_count += 1
                                    errors.append(f"第 {line_idx} 行 '{username}' 更新校验失败: {', '.join(ve.messages)}")
                                except Exception as ex:
                                    fail_count += 1
                                    errors.append(f"第 {line_idx} 行 '{username}' 更新失败: {str(ex)}")
                            else:
                                duplicate_count += 1
                            continue
                        
                        try:
                            # 尝试实例化并验证，确保用户名中不含空格/无效符号，以防抛出 500 异常
                            user = CustomUser(username=username, roles=role)
                            if team_val:
                                user.team = team_val
                            if email_val:
                                user.email = email_val
                            user.set_password('123456')
                            user.full_clean()
                            user.save()
                            success_count += 1
                        except ValidationError as ve:
                            fail_count += 1
                            errors.append(f"第 {line_idx} 行 '{username}' 验证失败: {', '.join(ve.messages)}")
                        except Exception as ex:
                            fail_count += 1
                            errors.append(f"第 {line_idx} 行 '{username}' 创建失败: {str(ex)}")
            except Exception as outer_ex:
                self.message_user(request, f"事务执行失败: {str(outer_ex)}", level='error')
                return redirect('..')

            msg = f"批量导入系统用户完成！成功创建 {success_count} 个用户，为 {updated_count} 个已有用户补全了信息，忽略了 {duplicate_count} 个重复用户。"
            if fail_count > 0:
                msg += f" 失败 {fail_count} 笔（包含空格/非法字符等/无效团队选项等）。"
                for err in errors[:5]:
                    msg += f" [{err}]"
                if len(errors) > 5:
                    msg += " （其它错误已省略）"
                self.message_user(request, msg, level='warning')
            else:
                self.message_user(request, msg, level='success')
            return redirect('..')

        context = dict(
           self.admin_site.each_context(request),
           title="批量导入系统用户"
        )
        return render(request, "admin/customuser/bulk_import.html", context)

from django.urls import path
from django.shortcuts import render, redirect

@admin.register(SystemOption)
class SystemOptionAdmin(admin.ModelAdmin):
    list_display = ('category', 'value')
    list_filter = ('category',)
    search_fields = ('value',)
    change_list_template = "admin/systemoption/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('bulk-import/', self.admin_site.admin_view(self.bulk_import_view), name='systemoption-bulk-import'),
        ]
        return my_urls + urls

    def bulk_import_view(self, request):
        if request.method == 'POST':
            category = request.POST.get('category')
            bulk_data = request.POST.get('bulk_data', '')
            lines = [line.strip() for line in bulk_data.split('\n') if line.strip()]
            success_count = 0
            duplicate_count = 0
            fail_count = 0
            errors = []

            # 仅允许系统选项类别，拒绝 USER_ 类（用户导入请到"系统用户"菜单）
            valid_categories = dict(SystemOption.CATEGORY_CHOICES).keys()
            if category not in valid_categories:
                self.message_user(request, f'无效的选项类型: {category}。用户导入请前往「用户管理」菜单。', level='error')
                return redirect('..')

            from django.db import transaction
            try:
                with transaction.atomic():
                    for line_idx, line in enumerate(lines, 1):
                        val = line.strip()
                        if not val:
                            continue
                        try:
                            obj, created = SystemOption.objects.get_or_create(category=category, value=val)
                            if created:
                                success_count += 1
                            else:
                                duplicate_count += 1
                        except Exception as ex:
                            fail_count += 1
                            errors.append(f"第 {line_idx} 行 '{val}' 导入失败: {str(ex)}")
            except Exception as outer_ex:
                self.message_user(request, f"事务执行失败: {str(outer_ex)}", level='error')
                return redirect('..')

            msg = f"批量导入完成！成功新增 {success_count} 个选项，忽略了 {duplicate_count} 个重复项。"
            if fail_count > 0:
                msg += f" 失败 {fail_count} 笔。"
                for err in errors[:5]:
                    msg += f" [{err}]"
                self.message_user(request, msg, level='warning')
            else:
                self.message_user(request, msg, level='success')
            return redirect('..')
            
        context = dict(
           self.admin_site.each_context(request),
           title="批量导入下拉选项配置"
        )
        return render(request, "admin/systemoption/bulk_import.html", context)

class ResourceInventoryForm(forms.ModelForm):
    class Meta:
        model = ResourceInventory
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 动态从 SystemOption 读取可用的卡型号
        card_types = SystemOption.objects.filter(category='CARD_TYPE').values_list('value', 'value')
        current_type = self.instance.cardType if self.instance and self.instance.pk else None
        choices_type = [('', '---------')] + list(card_types)
        if current_type and current_type not in [c[0] for c in choices_type]:
            choices_type.append((current_type, f"{current_type} (已从选项移除)"))
        self.fields['cardType'] = forms.ChoiceField(
            choices=choices_type,
            label='卡型号',
            help_text='这里的数据来源于“系统选项配置”中的“卡资源型号”。'
        )

        # 动态从 SystemOption 读取可用的卡形态
        card_forms = SystemOption.objects.filter(category='CARD_FORM').values_list('value', 'value')
        current_form = self.instance.cardForm if self.instance and self.instance.pk else None
        choices_form = [('', '---------')] + list(card_forms)
        if current_form and current_form not in [c[0] for c in choices_form]:
            choices_form.append((current_form, f"{current_form} (已从选项移除)"))
        self.fields['cardForm'] = forms.ChoiceField(
            choices=choices_form,
            label='卡形态',
            help_text='这里的数据来源于“系统选项配置”中的“卡资源形态”。'
        )

        # 动态从 SystemOption 读取可用的地域
        regions = SystemOption.objects.filter(category='REGION').values_list('value', 'value')
        current_region = self.instance.region if self.instance and self.instance.pk else None
        choices_region = [('', '---------')] + list(regions)
        if current_region and current_region not in [c[0] for c in choices_region]:
            choices_region.append((current_region, f"{current_region} (已从选项移除)"))
        self.fields['region'] = forms.ChoiceField(
            choices=choices_region,
            label='所在地域',
            help_text='这里的数据来源于“系统选项配置”中的“地域”选项。'
        )

    def clean(self):
        cleaned_data = super().clean()
        totalCount = cleaned_data.get('totalCount')
        allocatedCount = cleaned_data.get('allocatedCount')
        
        if totalCount is not None and totalCount < 0:
            raise forms.ValidationError("库存总数量不能为负数。")
            
        if totalCount is not None and allocatedCount is not None:
            if totalCount < allocatedCount:
                raise forms.ValidationError(f"库存总数量 ({totalCount}) 不能小于已分配数量 ({allocatedCount})。")
        return cleaned_data

@admin.register(ResourceInventory)
class ResourceInventoryAdmin(admin.ModelAdmin):
    form = ResourceInventoryForm
    list_display = ('cardName', 'cardForm', 'cardType', 'region', 'totalCount', 'allocatedCount', 'available_count')
    list_display_links = ('cardName',)
    list_editable = ('cardForm', 'cardType', 'region', 'totalCount')
    list_filter = ('cardForm', 'cardType', 'region')
    search_fields = ('cardName', 'cardType', 'region')

    def available_count(self, obj):
        return obj.totalCount - obj.allocatedCount
    available_count.short_description = '剩余可用'

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('project', 'applicant', 'team', 'cardType', 'count', 'status', 'created_at')
    list_filter = ('status', 'priority', 'cardType')
    search_fields = ('project', 'applicant__username', 'team')
    readonly_fields = ('created_at', 'updated_at')
    change_list_template = "admin/application/change_list.html"

    def save_model(self, request, obj, form, change):
        """后台修改申请单状态时，自动同步库存"""
        if change and 'status' in form.changed_data:
            try:
                old_obj = Application.objects.get(pk=obj.pk)
            except Application.DoesNotExist:
                super().save_model(request, obj, form, change)
                return
            
            old_status = old_obj.status
            new_status = obj.status
            
            # 从已占用库存的状态 → 不占用库存的状态时，归还库存
            inventory_consuming_statuses = {'APPROVED', 'EXECUTED'}
            non_consuming_statuses = {'REJECTED', 'CANCELLED', 'RELEASED', 'PENDING_TEAM', 'PENDING_PRE'}
            
            if old_status in inventory_consuming_statuses and new_status in non_consuming_statuses:
                # 归还库存
                if old_obj.allocation_details:
                    for detail in old_obj.allocation_details:
                        inv_id = detail.get('inventory_id')
                        count_to_return = detail.get('count', 0)
                        if inv_id and count_to_return > 0:
                            try:
                                inv = ResourceInventory.objects.get(id=inv_id)
                                inv.allocatedCount = max(0, inv.allocatedCount - count_to_return)
                                inv.save()
                            except ResourceInventory.DoesNotExist:
                                pass
                elif old_obj.allocatedCount:
                    invs = ResourceInventory.objects.filter(
                        cardType=old_obj.allocatedCardType,
                        cardForm=old_obj.allocatedCardForm
                    )
                    if invs.exists():
                        inv = invs.first()
                        inv.allocatedCount = max(0, inv.allocatedCount - old_obj.allocatedCount)
                        inv.save()
                
                # 释放绑定的物料资产
                from .models import AssetAllocation
                allocations = AssetAllocation.objects.filter(application=obj)
                for alloc in allocations:
                    asset = alloc.asset
                    asset.used_cards = max(0, asset.used_cards - alloc.allocated_cards)
                    if asset.used_cards <= 0:
                        asset.status = 'IDLE'
                    else:
                        asset.status = 'PARTIAL'
                    asset.save()
                allocations.delete()
                
                from django.contrib import messages
                messages.info(request, f'已自动归还申请单 #{obj.id} 占用的库存并释放绑定资产。')
            
            # 从不占用 → 占用（不太常见，但防御性处理）
            elif old_status in non_consuming_statuses and new_status in inventory_consuming_statuses:
                if obj.allocatedCount and obj.allocatedCardType:
                    invs = ResourceInventory.objects.filter(
                        cardType=obj.allocatedCardType,
                        cardForm=obj.allocatedCardForm
                    )
                    if invs.exists():
                        inv = invs.first()
                        inv.allocatedCount += obj.allocatedCount
                        inv.save()
        
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('bulk-import/', self.admin_site.admin_view(self.bulk_import_view), name='application-bulk-import'),
        ]
        return my_urls + urls

    def bulk_import_view(self, request):
        if request.method == 'POST':
            bulk_data = request.POST.get('bulk_data', '')
            lines = [line.strip() for line in bulk_data.split('\n') if line.strip()]
            success_count = 0
            fail_count = 0
            errors = []
            
            # 状态和优先级字典映射
            status_map = {
                '待审批': 'PENDING_TEAM',
                '待组长审批': 'PENDING_TEAM',
                '待资源预审': 'PENDING_PRE',
                '待部门终审': 'PENDING_FINAL',
                '已审批(待执行)': 'APPROVED',
                '已审批': 'APPROVED',
                '已驳回': 'REJECTED',
                '已执行': 'EXECUTED',
                '已撤回': 'CANCELLED'
            }
            priority_map = {
                '高': 'HIGH',
                '中': 'MEDIUM',
                '低': 'LOW'
            }

            from datetime import date
            
            # 获取系统中已配置的选项集合
            valid_teams = set(SystemOption.objects.filter(category='TEAM').values_list('value', flat=True))
            valid_card_forms = set(SystemOption.objects.filter(category='CARD_FORM').values_list('value', flat=True))
            valid_card_types = set(SystemOption.objects.filter(category='CARD_TYPE').values_list('value', flat=True))
            valid_projects = set(SystemOption.objects.filter(category='PROJECT').values_list('value', flat=True))
            
            for line_idx, line in enumerate(lines, 1):
                # 忽略表头行
                if '项目名称' in line or '申请人' in line or '卡型号' in line:
                    continue
                
                # Excel 复制出的列默认以 Tab 分隔，做个容错兼容逗号
                parts = line.split('\t')
                if len(parts) < 8:
                    parts = line.split(',')
                
                if len(parts) < 8:
                    fail_count += 1
                    errors.append(f"第 {line_idx} 行格式错误：有效数据不足 8 列。")
                    continue
                
                try:
                    # 字段映射
                    project = parts[0].strip()
                    applicant_username = parts[1].strip()
                    users = parts[2].strip()
                    team = parts[3].strip()
                    cardType = parts[4].strip()
                    cardForm = parts[5].strip()
                    
                    count = int(parts[6].strip())
                    minCount = int(parts[7].strip()) if len(parts) > 7 and parts[7].strip() else count
                    
                    # 校验系统中是否配置了对应的选项
                    if team not in valid_teams:
                        fail_count += 1
                        errors.append(f"第 {line_idx} 行：团队「{team}」在系统配置中不存在。")
                        continue
                    if cardForm not in valid_card_forms:
                        fail_count += 1
                        errors.append(f"第 {line_idx} 行：卡形态「{cardForm}」在系统配置中不存在。")
                        continue
                    if cardType not in valid_card_types:
                        fail_count += 1
                        errors.append(f"第 {line_idx} 行：卡型号「{cardType}」在系统配置中不存在。")
                        continue
                    if project not in valid_projects:
                        fail_count += 1
                        errors.append(f"第 {line_idx} 行：受益项目「{project}」在系统配置中不存在。")
                        continue
                    
                    # 选填字段处理
                    priority_str = parts[8].strip() if len(parts) > 8 and parts[8].strip() else '中'
                    priority = priority_map.get(priority_str, 'MEDIUM')
                    
                    status_str = parts[9].strip() if len(parts) > 9 and parts[9].strip() else '已执行'
                    status = status_map.get(status_str, 'EXECUTED')
                    
                    purpose = parts[10].strip() if len(parts) > 10 and parts[10].strip() else '历史数据导入'
                    
                    start_date = None
                    end_date = None
                    if len(parts) > 11 and parts[11].strip():
                        try:
                            start_date = date.fromisoformat(parts[11].strip())
                        except ValueError:
                            pass
                    if len(parts) > 12 and parts[12].strip():
                        try:
                            end_date = date.fromisoformat(parts[12].strip())
                        except ValueError:
                            pass
                            
                    note = parts[13].strip() if len(parts) > 13 and parts[13].strip() else ''
                    
                    # 校验并自动创建账号
                    try:
                        applicant = CustomUser.objects.get(username=applicant_username)
                    except CustomUser.DoesNotExist:
                        applicant = CustomUser.objects.create_user(
                            username=applicant_username,
                            password='123456',
                            role='APPLICANT'
                        )
                    
                    # 计算时长显示 text
                    duration_text = '最多使用两周'
                    if start_date and end_date:
                        delta = (end_date - start_date).days
                        duration_text = f"{start_date.isoformat()} ~ {end_date.isoformat()} ({delta}天)"
                    elif start_date:
                        duration_text = f"自 {start_date.isoformat()} 起"
                    
                    # 保存入库
                    Application.objects.create(
                        applicant=applicant,
                        users=users,
                        team=team,
                        cardForm=cardForm,
                        cardType=cardType,
                        purpose=purpose,
                        project=project,
                        model_used='- (历史导入)',
                        priority=priority,
                        priorityReason='历史导入，自动补充',
                        count=count,
                        minCount=minCount,
                        startDate=start_date,
                        endDate=end_date,
                        duration=duration_text,
                        note=note,
                        status=status
                    )
                    success_count += 1
                except Exception as ex:
                    fail_count += 1
                    errors.append(f"第 {line_idx} 行解析失败: {str(ex)}")
            
            msg = f"批量导入执行完毕：成功导入 {success_count} 笔。"
            if fail_count > 0:
                msg += f" 失败 {fail_count} 笔。"
                for err in errors[:5]:
                    msg += f" [{err}]"
                if len(errors) > 5:
                    msg += " （其它错误已省略）"
                self.message_user(request, msg, level='warning')
            else:
                self.message_user(request, msg, level='success')
            return redirect('..')

        context = dict(
           self.admin_site.each_context(request),
           title="批量导入历史申请单"
        )
        return render(request, "admin/application/bulk_import.html", context)


class ResourceAssetForm(forms.ModelForm):
    class Meta:
        model = ResourceAsset
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 动态从 SystemOption 读取可用的卡型号
        card_types = SystemOption.objects.filter(category='CARD_TYPE').values_list('value', 'value')
        current_type = self.instance.card_type if self.instance and self.instance.pk else None
        choices_type = [('', '---------')] + list(card_types)
        if current_type and current_type not in [c[0] for c in choices_type]:
            choices_type.append((current_type, f"{current_type} (已从选项移除)"))
        self.fields['card_type'] = forms.ChoiceField(
            choices=choices_type,
            label='卡型号',
            required=False,
            help_text='这里的数据来源于“系统选项配置”中的“卡资源型号”。'
        )

        # 动态从 SystemOption 读取可用的卡形态
        card_forms = SystemOption.objects.filter(category='CARD_FORM').values_list('value', 'value')
        current_form = self.instance.card_form if self.instance and self.instance.pk else None
        choices_form = [('', '---------')] + list(card_forms)
        if current_form and current_form not in [c[0] for c in choices_form]:
            choices_form.append((current_form, f"{current_form} (已从选项移除)"))
        self.fields['card_form'] = forms.ChoiceField(
            choices=choices_form,
            label='卡形态',
            required=False,
            help_text='这里的数据来源于“系统选项配置”中的“卡资源形态”。'
        )

        # 动态从 SystemOption 读取可用的地域
        regions = SystemOption.objects.filter(category='REGION').values_list('value', 'value')
        current_region = self.instance.region if self.instance and self.instance.pk else None
        choices_region = [('', '---------')] + list(regions)
        if current_region and current_region not in [c[0] for c in choices_region]:
            choices_region.append((current_region, f"{current_region} (已从选项移除)"))
        self.fields['region'] = forms.ChoiceField(
            choices=choices_region,
            label='所在地域',
            required=False,
            help_text='这里的数据来源于“系统选项配置”中的“地域”选项。'
        )


@admin.register(ResourceAsset)
class ResourceAssetAdmin(admin.ModelAdmin):
    form = ResourceAssetForm
    list_display = ('name', 'ip', 'card_type', 'card_form', 'card_count', 'status', 'owner', 'current_users', 'app_name', 'region', 'specifications')
    list_filter = ('status', 'card_type', 'card_form', 'region')
    search_fields = ('name', 'ip', 'app_name', 'specifications', 'current_users')
    change_list_template = "admin/resourceasset/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('bulk-import/', self.admin_site.admin_view(self.bulk_import_view), name='resourceasset-bulk-import'),
        ]
        return my_urls + urls

    def bulk_import_view(self, request):
        if request.method == 'POST':
            bulk_data = request.POST.get('bulk_data', '')
            lines = [line.strip() for line in bulk_data.split('\n') if line.strip()]
            success_count = 0
            fail_count = 0
            errors = []

            # 状态字典映射
            status_map = {
                '闲置': 'IDLE',
                '使用中': 'IN_USE',
                '故障': 'FAULT',
                'idle': 'IDLE',
                'in_use': 'IN_USE',
                'fault': 'FAULT'
            }

            # 获取系统中已配置的选项集合
            valid_card_forms = set(SystemOption.objects.filter(category='CARD_FORM').values_list('value', flat=True))
            valid_card_types = set(SystemOption.objects.filter(category='CARD_TYPE').values_list('value', flat=True))
            valid_regions = set(SystemOption.objects.filter(category='REGION').values_list('value', flat=True))

            for line_idx, line in enumerate(lines, 1):
                # 忽略表头行
                if '资源名称' in line or 'IP地址' in line or 'IP' in line:
                    continue

                parts = line.split('\t')
                if len(parts) < 1:
                    fail_count += 1
                    errors.append(f"第 {line_idx} 行格式错误：数据为空。")
                    continue

                try:
                    name = parts[0].strip()
                    if not name:
                        continue
                    
                    ip = parts[1].strip() if len(parts) > 1 else ''
                    password = parts[2].strip() if len(parts) > 2 else ''
                    specifications = parts[3].strip() if len(parts) > 3 else ''
                    card_type = parts[4].strip() if len(parts) > 4 else ''
                    card_form = parts[5].strip() if len(parts) > 5 else ''
                    card_count_str = parts[6].strip() if len(parts) > 6 else ''
                    card_count_val = int(card_count_str) if card_count_str.isdigit() and int(card_count_str) > 0 else 8
                    region = parts[7].strip() if len(parts) > 7 else ''
                    
                    status_str = parts[8].strip() if len(parts) > 8 and parts[8].strip() else '闲置'
                    status = status_map.get(status_str, 'IDLE')
                    
                    owner_username = parts[9].strip() if len(parts) > 9 else ''
                    current_users = parts[10].strip() if len(parts) > 10 else ''
                    app_name = parts[11].strip() if len(parts) > 11 else ''
                    
                    # 校验卡形态、卡型号、地域是否在系统配置中存在
                    if card_form and card_form not in valid_card_forms:
                        fail_count += 1
                        errors.append(f"第 {line_idx} 行：卡形态「{card_form}」在系统配置中不存在。")
                        continue
                    if card_type and card_type not in valid_card_types:
                        fail_count += 1
                        errors.append(f"第 {line_idx} 行：卡型号「{card_type}」在系统配置中不存在。")
                        continue
                    if region and region not in valid_regions:
                        fail_count += 1
                        errors.append(f"第 {line_idx} 行：地域「{region}」在系统配置中不存在。")
                        continue

                    owner = None
                    if owner_username:
                        try:
                            owner = CustomUser.objects.get(username=owner_username)
                        except CustomUser.DoesNotExist:
                            fail_count += 1
                            errors.append(f"第 {line_idx} 行：当前责任人「{owner_username}」在系统中不存在。")
                            continue

                    # 保存入库
                    ResourceAsset.objects.create(
                        name=name,
                        ip=ip,
                        password=password,
                        specifications=specifications,
                        card_type=card_type,
                        card_form=card_form,
                        card_count=card_count_val,
                        region=region,
                        status=status,
                        owner=owner,
                        current_users=current_users,
                        app_name=app_name
                    )
                    success_count += 1
                except Exception as ex:
                    fail_count += 1
                    errors.append(f"第 {line_idx} 行解析失败: {str(ex)}")

            msg = f"批量导入执行完毕：成功导入 {success_count} 笔。"
            if fail_count > 0:
                msg += f" 失败 {fail_count} 笔。"
                for err in errors[:5]:
                    msg += f" [{err}]"
                if len(errors) > 5:
                    msg += " （其它错误已省略）"
                self.message_user(request, msg, level='warning')
            else:
                self.message_user(request, msg, level='success')
            return redirect('..')

        context = dict(
           self.admin_site.each_context(request),
           title="批量导入物料资产"
        )
        return render(request, "admin/resourceasset/bulk_import.html", context)


class FeedbackImageInline(admin.TabularInline):
    model = FeedbackImage
    extra = 1

@admin.register(IssueFeedback)
class IssueFeedbackAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'content', 'user__username')
    inlines = [FeedbackImageInline]


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description')
    list_editable = ('value',)
    search_fields = ('key', 'description')


import requests
import threading
from django.conf import settings

@admin.register(SystemNotificationLog)
class SystemNotificationLogAdmin(admin.ModelAdmin):
    list_display = ('receiver_email', 'sender', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('receiver_email', 'content', 'error_message')
    actions = ['resend_notifications']

    def resend_notifications(self, request, queryset):
        api_url = getattr(settings, 'REMIND_API_URL', 'http://127.0.0.1:8000/mock-notification-api/')
        
        def do_resend_async(log_id, url, content, receivers):
            errors = []
            success_count = 0
            for r in receivers:
                try:
                    data = {
                        'content': content,
                        'receiver': r
                    }
                    res = requests.post(url, json=data, timeout=5)
                    if res.status_code == 200:
                        success_count += 1
                    else:
                        errors.append(f"发送至账号 {r} 失败: HTTP {res.status_code}")
                except Exception as e:
                    errors.append(f"发送至账号 {r} 失败: {str(e)}")
            
            if not errors:
                SystemNotificationLog.objects.filter(id=log_id).update(status='SUCCESS', error_message=None)
              # If some succeeded, mark SUCCESS but keep err_msg, or choose status
            else:
                err_msg = "\n".join(errors)
                new_status = 'FAILED' if success_count == 0 else 'SUCCESS'
                SystemNotificationLog.objects.filter(id=log_id).update(status=new_status, error_message=err_msg)

        sent_count = 0
        for log in queryset:
            r_list = [r.strip() for r in log.receiver_email.split(',') if r.strip()]
            if r_list:
                log.status = 'PENDING'
                log.save()
                threading.Thread(target=do_resend_async, args=(log.id, api_url, log.content, r_list), daemon=True).start()
                sent_count += 1
                
        self.message_user(request, f"已在后台重新发送 {sent_count} 条消息提醒通知。")
    
    resend_notifications.short_description = "重新发送所选的提醒通知"


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.site_header = '卡管理系统 - 后台管理'
admin.site.site_title = '卡管理系统'
admin.site.index_title = '初始化顺序：① 先配选项 → ② 再建用户 → ③ 设库存 → ④⑤ 导数据'

