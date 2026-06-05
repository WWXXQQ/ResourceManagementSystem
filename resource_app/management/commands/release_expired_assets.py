import os
import sys
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from resource_app.models import Application, ResourceInventory, ResourceAsset, SystemSetting

class Command(BaseCommand):
    help = 'Automatically release card resource allocations that have exceeded their endDate'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting auto-release of expired resources..."))
        
        # 1. 检查自动释放功能开关
        auto_release_setting, _ = SystemSetting.objects.get_or_create(
            key='auto_release_enabled',
            defaults={'value': 'false', 'description': '是否启用自动释放已到期卡资源'}
        )
        if auto_release_setting.value != 'true':
            self.stdout.write(self.style.WARNING("自动释放功能当前已关闭，跳过释放逻辑。请在执行管理页面或后台中开启。"))
            return

        today = date.today()
        # 2. 查询所有已执行且超期的申请单
        expired_apps = Application.objects.filter(status='EXECUTED', endDate__lt=today)
        
        if not expired_apps.exists():
            self.stdout.write(self.style.SUCCESS("No expired resources to release."))
            return

        released_count = 0
        for app in expired_apps:
            try:
                with transaction.atomic():
                    # 行锁获取最新状态
                    application = Application.objects.select_for_update().get(id=app.id)
                    if application.status != 'EXECUTED':
                        continue
                    
                    # 恢复库存数量，使用 select_for_update
                    if application.allocation_details:
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
                        inventories = ResourceInventory.objects.select_for_update().filter(
                            cardName=application.allocatedCardName,
                            cardType=application.allocatedCardType,
                            cardForm=application.allocatedCardForm,
                            region=application.allocatedRegion
                        )
                        if inventories.exists():
                            inv = inventories.first()
                            inv.allocatedCount = max(0, inv.allocatedCount - application.allocatedCount)
                            inv.save()
                    
                    # 自动解绑并恢复物料资产为闲置，使用 select_for_update
                    from resource_app.models import AssetAllocation
                    allocations = AssetAllocation.objects.select_for_update().filter(application=application)
                    released_assets_count = allocations.count()
                    for alloc in allocations:
                        asset = alloc.asset
                        asset.used_cards = max(0, asset.used_cards - alloc.allocated_cards)
                        if asset.used_cards <= 0:
                            asset.status = 'IDLE'
                        else:
                            asset.status = 'PARTIAL'
                        asset.save()
                    allocations.delete()
                        
                    application.status = 'RELEASED'
                    audit_msg = f"[系统自动释放回收于 {today.isoformat()}]"
                    if application.note:
                        application.note = f"{application.note}\n{audit_msg}"
                    else:
                        application.note = audit_msg
                    application.save()
                    
                    released_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Released application ID {application.id} ({application.project}) - Expired on {application.endDate}. "
                        f"Unbound {released_assets_count} assets."
                    ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to automatically release Application ID {app.id}: {str(e)}"))
                
        self.stdout.write(self.style.SUCCESS(f"Auto-release run finished. Total applications released: {released_count}"))
