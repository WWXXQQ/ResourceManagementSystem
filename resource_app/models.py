from django.db import models
from django.contrib.auth.models import AbstractUser
from cryptography.fernet import Fernet
import base64
import hashlib
from django.conf import settings
from django.db.models.signals import post_delete, pre_save, post_save
from django.dispatch import receiver
import os
from datetime import date

def get_fernet():
    key_hash = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(key_hash)
    return Fernet(key)

class EncryptedCharField(models.CharField):
    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == '':
            return value
        try:
            # If already encrypted, don't encrypt again
            if value.startswith('gAAAA'):
                return value
            f = get_fernet()
            return f.encrypt(value.encode()).decode()
        except Exception:
            return value

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        try:
            f = get_fernet()
            return f.decrypt(value.encode()).decode()
        except Exception:
            return value

    def to_python(self, value):
        if value is None or value == '':
            return value
        try:
            if value.startswith('gAAAA'):
                f = get_fernet()
                return f.decrypt(value.encode()).decode()
        except Exception:
            pass
        return super().to_python(value)


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True, verbose_name='配置键')
    value = models.CharField(max_length=200, verbose_name='配置值')
    description = models.CharField(max_length=200, blank=True, null=True, verbose_name='配置描述')

    class Meta:
        verbose_name = '全局设置'
        verbose_name_plural = '⑧ 全局设置（高级配置）'

    def __str__(self):
        return f"{self.key}: {self.value}"


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('APPLICANT', '申请人'),
        ('TEAM_LEADER', '组长'),
        ('APPROVER', '预审人/审批人'),
        ('DEPT_HEAD', '部门负责人'),
        ('EXECUTOR', '执行人'),
        ('ADMIN', '管理员'),
    )
    roles = models.CharField(max_length=255, default='APPLICANT', verbose_name='用户角色(多选)')
    team = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name='所属团队')
    email = models.CharField(max_length=150, blank=True, default='', verbose_name='账号')

    def get_role_display(self):
        """兼容和支持多选角色，返回逗号分隔的人类可读名称"""
        choices_dict = dict(self.ROLE_CHOICES)
        if not self.roles:
            return choices_dict.get('APPLICANT', '申请人')
        roles_list = [r.strip() for r in self.roles.split(',') if r.strip()]
        display_list = [choices_dict.get(r, r) for r in roles_list]
        return ",".join(display_list)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '② 用户管理（账号/角色/团队）'


class SystemOption(models.Model):
    CATEGORY_CHOICES = (
        ('TEAM', '所在团队'),
        ('CARD_FORM', '卡资源形态'),
        ('CARD_TYPE', '卡资源型号'),
        ('PROJECT', '受益项目'),
        ('REGION', '地域'),
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='选项类型')
    value = models.CharField(max_length=100, verbose_name='选项值')

    class Meta:
        unique_together = ('category', 'value')
        verbose_name = '下拉选项'
        verbose_name_plural = '① 下拉选项配置（团队/型号/形态/项目/地域）【最先配置】'

    def __str__(self):
        return f"{self.get_category_display()}: {self.value}"


class ResourceInventory(models.Model):
    cardName = models.CharField(max_length=100, default='默认卡资源', verbose_name='卡资源名称')
    cardForm = models.CharField(max_length=50, default='裸机', verbose_name='卡资源形态')
    cardType = models.CharField(max_length=50, verbose_name='卡资源型号')
    region = models.CharField(max_length=50, default='北京', verbose_name='卡所在地域')
    totalCount = models.IntegerField(default=0, verbose_name='总数量')
    allocatedCount = models.IntegerField(default=0, verbose_name='已分配数量')

    class Meta:
        verbose_name = '卡池库存'
        verbose_name_plural = '③ 卡池库存（各型号总量与余量）'

    def __str__(self):
        return f"{self.cardName} | {self.cardForm} | {self.cardType} | {self.region} (余 {self.totalCount - self.allocatedCount})"


class Application(models.Model):
    STATUS_CHOICES = (
        ('PENDING_TEAM', '待组长审批'),
        ('PENDING_PRE', '待资源预审'),
        ('PENDING_FINAL', '待部门终审'),
        ('APPROVED', '已审批(待执行)'),
        ('REJECTED', '已驳回'),
        ('EXECUTED', '已执行'),
        ('CANCELLED', '已撤回'),
        ('RELEASED', '已释放'),
    )
    PRIORITY_CHOICES = (
        ('HIGH', '高'),
        ('MEDIUM', '中'),
        ('LOW', '低'),
    )

    applicant = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='applications', verbose_name='申请人')
    users = models.TextField(verbose_name='使用人(多个)')
    team = models.CharField(max_length=100, db_index=True, verbose_name='所在团队')
    
    cardForm = models.CharField(max_length=100, db_index=True, verbose_name='申请卡形态')
    cardType = models.CharField(max_length=100, db_index=True, verbose_name='申请卡型号')
    purpose = models.TextField(verbose_name='申请用途')
    project = models.CharField(max_length=100, db_index=True, verbose_name='受益项目')
    model_used = models.CharField(max_length=100, verbose_name='使用的模型')
    
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, verbose_name='优先级')
    priorityReason = models.TextField(verbose_name='优先级理由')
    
    count = models.IntegerField(verbose_name='申请数量')
    minCount = models.IntegerField(verbose_name='最少数量')
    startDate = models.DateField(blank=True, null=True, verbose_name='开始使用日期')
    endDate = models.DateField(blank=True, null=True, verbose_name='结束使用日期')
    duration = models.CharField(max_length=100, default='最多使用两周', verbose_name='使用时间')
    note = models.TextField(blank=True, null=True, verbose_name='备注')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_TEAM', db_index=True, verbose_name='状态')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    # 审批结果
    allocatedCount = models.IntegerField(blank=True, null=True, verbose_name='分配数量')
    allocatedCardType = models.CharField(max_length=100, blank=True, null=True, verbose_name='分配型号')
    allocatedCardForm = models.CharField(max_length=100, blank=True, null=True, verbose_name='分配形态')
    allocatedRegion = models.CharField(max_length=100, blank=True, null=True, verbose_name='分配地域')
    allocatedCardName = models.CharField(max_length=100, blank=True, null=True, verbose_name='分配卡资源名称')
    approvalNote = models.TextField(blank=True, null=True, verbose_name='审批意见')
    
    # 执行结果
    executionResult = models.TextField(blank=True, null=True, verbose_name='执行结果')
    attachment = models.FileField(upload_to='attachments/', blank=True, null=True, verbose_name='图片附件')
    
    # 审批流节点意见
    team_leader_note = models.TextField(blank=True, null=True, verbose_name='组长审批意见')
    pre_approver_note = models.TextField(blank=True, null=True, verbose_name='预审意见')
    final_approver_note = models.TextField(blank=True, null=True, verbose_name='部门负责人终审意见')

    # 新增第五阶段深度自检优化字段
    allocation_details = models.JSONField(blank=True, null=True, verbose_name='分配卡池详情')
    coordination_details = models.JSONField(blank=True, null=True, verbose_name='协调抽调详情')
    card_count = models.IntegerField(blank=True, null=True, verbose_name='计算卡张数')
    card_days = models.IntegerField(blank=True, null=True, verbose_name='计算卡天数')

    @property
    def is_overdue(self):
        if self.status == 'EXECUTED' and self.endDate and self.endDate < date.today():
            return True
        return False

    class Meta:
        verbose_name = '申请单'
        verbose_name_plural = '④ 申请单列表（历史单据导入与查看）'

    def __str__(self):
        return f"{self.project} - {self.applicant.username} ({self.get_status_display()})"


class ResourceAsset(models.Model):
    STATUS_CHOICES = (
        ('IDLE', '闲置'),
        ('IN_USE', '使用中(满载)'),
        ('PARTIAL', '部分分配'),
        ('FAULT', '故障'),
    )
    name = models.CharField(max_length=100, verbose_name='资源名称')
    ip = models.CharField(max_length=50, blank=True, null=True, verbose_name='IP地址')
    password = EncryptedCharField(max_length=250, blank=True, null=True, verbose_name='密码')
    owner = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='当前责任人(申请人)', related_name='owned_assets')
    current_users = models.CharField(max_length=200, blank=True, null=True, verbose_name='当前使用人')
    
    card_type = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name='卡资源型号')
    card_form = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name='卡资源形态')
    card_count = models.PositiveIntegerField(default=8, verbose_name='卡数量', help_text='该台设备的GPU卡数量，裸机一般为8卡')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IDLE', db_index=True, verbose_name='状态')
    
    app_name = models.CharField(max_length=100, blank=True, null=True, verbose_name='所在应用')
    region = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name='地域')
    specifications = models.CharField(max_length=100, blank=True, null=True, verbose_name='规格')
    used_cards = models.PositiveIntegerField(default=0, verbose_name='已用卡数', help_text='该物理机目前已被分配的卡数量')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    def clean(self):
        super().clean()
        if self.pk:
            try:
                old = ResourceAsset.objects.get(pk=self.pk)
                if old.status == 'IN_USE':
                    if (self.status != 'IN_USE' or
                        self.card_type != old.card_type or
                        self.card_form != old.card_form or
                        self.region != old.region):
                        from django.core.exceptions import ValidationError
                        raise ValidationError('该物理资产当前处于“使用中”状态，不能随意修改其核心参数或状态。如需变更，请先释放对应的申请单。')
            except ResourceAsset.DoesNotExist:
                pass

    class Meta:
        verbose_name = '物料资产'
        verbose_name_plural = '⑤ 物料资产（服务器/设备台账）'

    def __str__(self):
        return f"{self.name} ({self.ip or '无IP'})"


class AssetAllocation(models.Model):
    asset = models.ForeignKey(ResourceAsset, on_delete=models.CASCADE, related_name='allocations', verbose_name='物理资产')
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='asset_allocations', verbose_name='申请单')
    allocated_cards = models.PositiveIntegerField(default=1, verbose_name='分配卡数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='分配时间')

    class Meta:
        verbose_name = '资产分配明细'
        verbose_name_plural = '⑥ 资产分配明细'
        unique_together = ('asset', 'application')

    def __str__(self):
        return f"{self.asset.name} -> {self.application.project} ({self.allocated_cards}卡)"


class IssueFeedback(models.Model):
    STATUS_CHOICES = (
        ('PENDING', '待处理'),
        ('RESOLVED', '已解决'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='feedbacks', verbose_name='反馈人')
    title = models.CharField(max_length=200, verbose_name='问题标题')
    content = models.TextField(verbose_name='详细描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '问题反馈'
        verbose_name_plural = '⑥ 问题反馈'

    def __str__(self):
        return f"{self.title} - {self.user.username} ({self.get_status_display()})"


class FeedbackImage(models.Model):
    feedback = models.ForeignKey(IssueFeedback, on_delete=models.CASCADE, related_name='images', verbose_name='所属反馈')
    image = models.FileField(upload_to='feedback_images/', verbose_name='图片')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '反馈图片'
        verbose_name_plural = '反馈图片'

    def __str__(self):
        return f"Image for {self.feedback.title} ({self.id})"


class SystemNotificationLog(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    receiver_email = models.CharField(max_length=150, verbose_name='接收账号')
    content = models.TextField(verbose_name='通知内容')
    status = models.CharField(
        max_length=20, 
        default='PENDING', 
        choices=(('PENDING', '发送中'), ('SUCCESS', '发送成功'), ('FAILED', '发送失败')), 
        verbose_name='状态'
    )
    error_message = models.TextField(blank=True, null=True, verbose_name='错误信息')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '通知日志'
        verbose_name_plural = '⑦ 通知日志（催办记录）'

    def __str__(self):
        return f"Notification to {self.receiver_email} ({self.status})"


# ==================== Django Signals for File Cleanup ====================

@receiver(post_delete, sender=Application)
def delete_application_attachment_on_delete(sender, instance, **kwargs):
    if instance.attachment:
        if os.path.isfile(instance.attachment.path):
            try:
                os.remove(instance.attachment.path)
            except Exception as e:
                print(f"[SIGNAL] Failed to delete application attachment file: {e}")

@receiver(pre_save, sender=Application)
def delete_application_attachment_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return False
    try:
        old_file = Application.objects.get(pk=instance.pk).attachment
    except Application.DoesNotExist:
        return False
    new_file = instance.attachment
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            try:
                os.remove(old_file.path)
            except Exception as e:
                print(f"[SIGNAL] Failed to delete old application attachment file: {e}")

@receiver(post_delete, sender=FeedbackImage)
def delete_feedback_image_file_on_delete(sender, instance, **kwargs):
    if instance.image:
        if os.path.isfile(instance.image.path):
            try:
                os.remove(instance.image.path)
            except Exception as e:
                print(f"[SIGNAL] Failed to delete feedback image file: {e}")


@receiver(pre_save, sender=ResourceInventory)
def sync_inventory_changes(sender, instance, **kwargs):
    # Ensure options exist in SystemOption
    if instance.cardForm:
        SystemOption.objects.get_or_create(category='CARD_FORM', value=instance.cardForm)
    if instance.cardType:
        SystemOption.objects.get_or_create(category='CARD_TYPE', value=instance.cardType)
    if instance.region:
        SystemOption.objects.get_or_create(category='REGION', value=instance.region)

    if instance.pk:
        try:
            old_instance = ResourceInventory.objects.get(pk=instance.pk)
            old_form = old_instance.cardForm
            old_type = old_instance.cardType
            old_region = old_instance.region
            
            new_form = instance.cardForm
            new_type = instance.cardType
            new_region = instance.region
            
            if old_form != new_form or old_type != new_type or old_region != new_region:
                # Update ResourceAsset
                ResourceAsset.objects.filter(
                    card_type=old_type,
                    card_form=old_form,
                    region=old_region
                ).update(
                    card_type=new_type,
                    card_form=new_form,
                    region=new_region
                )
                
                # Update Application requested values
                Application.objects.filter(
                    cardType=old_type,
                    cardForm=old_form
                ).update(
                    cardType=new_type,
                    cardForm=new_form
                )
                
                # Update Application allocated values
                Application.objects.filter(
                    allocatedCardType=old_type,
                    allocatedCardForm=old_form,
                    allocatedRegion=old_region
                ).update(
                    allocatedCardType=new_type,
                    allocatedCardForm=new_form,
                    allocatedRegion=new_region
                )
        except ResourceInventory.DoesNotExist:
            pass


@receiver(pre_save, sender=Application)
def pre_save_application_stats(sender, instance, **kwargs):
    # 计算卡数量
    cards = instance.allocatedCount if instance.allocatedCount is not None else instance.count
    instance.card_count = cards
    
    # 计算卡使用天数
    days = 14
    if instance.startDate and instance.endDate:
        days = (instance.endDate - instance.startDate).days
        if days <= 0:
            days = 1
    instance.card_days = cards * days


@receiver(pre_save, sender=ResourceAsset)
def capture_old_asset(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_asset = ResourceAsset.objects.get(pk=instance.pk)
        except ResourceAsset.DoesNotExist:
            instance._old_asset = None
    else:
        instance._old_asset = None

@receiver(post_save, sender=ResourceAsset)
def sync_inventory_on_asset_save(sender, instance, created, **kwargs):
    ctype = instance.card_type or '未知'
    cform = instance.card_form or '未知'
    cregion = instance.region or '未知'
    count = instance.card_count or 0

    if created:
        # 新增物料，增加大盘库存
        inv, _ = ResourceInventory.objects.get_or_create(
            cardType=ctype,
            cardForm=cform,
            region=cregion,
            defaults={'cardName': f'物理资产池_{ctype}'}
        )
        inv.totalCount += count
        inv.save()
    else:
        # 更新物料
        old = getattr(instance, '_old_asset', None)
        if old:
            old_ctype = old.card_type or '未知'
            old_cform = old.card_form or '未知'
            old_cregion = old.region or '未知'
            old_count = old.card_count or 0
            
            # 如果核心容量参数发生变化
            if (old_ctype != ctype or old_cform != cform or 
                old_cregion != cregion or old_count != count):
                
                # 1. 扣除旧资产
                old_invs = ResourceInventory.objects.filter(
                    cardType=old_ctype, cardForm=old_cform, region=old_cregion
                )
                if old_invs.exists():
                    old_inv = old_invs.first()
                    old_inv.totalCount = max(0, old_inv.totalCount - old_count)
                    old_inv.save()
                    
                # 2. 增加新资产
                new_inv, _ = ResourceInventory.objects.get_or_create(
                    cardType=ctype,
                    cardForm=cform,
                    region=cregion,
                    defaults={'cardName': f'物理资产池_{ctype}'}
                )
                new_inv.totalCount += count
                new_inv.save()

@receiver(post_delete, sender=ResourceAsset)
def sync_inventory_on_asset_delete(sender, instance, **kwargs):
    ctype = instance.card_type or '未知'
    cform = instance.card_form or '未知'
    cregion = instance.region or '未知'
    count = instance.card_count or 0
    
    invs = ResourceInventory.objects.filter(
        cardType=ctype, cardForm=cform, region=cregion
    )
    if invs.exists():
        inv = invs.first()
        inv.totalCount = max(0, inv.totalCount - count)
        inv.save()
