import os
import sys
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gpu_management.settings")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import django

django.setup()

from django.contrib.auth import get_user_model

from resource_app.models import (
    Application,
    AssetAllocation,
    ResourceAsset,
    ResourceInventory,
    SystemNotificationLog,
    SystemOption,
    SystemSetting,
)


PASSWORD = "TestPass123!"
TEAMS = ["E2EC-Alpha团队", "E2EC-Beta团队", "E2EC-Gamma团队", "E2EC-Delta团队"]
CARD_FORMS = ["裸机", "推理池", "训练池", "开发池"]
CARD_TYPES = ["A100", "A800", "H100", "H200", "L40S"]
REGIONS = ["北京", "上海", "深圳"]
PROJECTS = [
    "E2EC-Normal-Alpha-01",
    "E2EC-Normal-Alpha-02",
    "E2EC-Normal-Alpha-03",
    "E2EC-Normal-Beta-01",
    "E2EC-Normal-Beta-02",
    "E2EC-Normal-Beta-03",
    "E2EC-Normal-Gamma-01",
    "E2EC-Normal-Gamma-02",
    "E2EC-Normal-Delta-01",
    "E2EC-Normal-Delta-02",
    "E2EC-Emergency-Donor",
    "E2EC-Emergency-Urgent",
]


def ensure_option(category, value):
    SystemOption.objects.get_or_create(category=category, value=value)


def create_user(username, roles, team="", is_superuser=False):
    user_model = get_user_model()
    if is_superuser:
        return user_model.objects.create_superuser(
            username=username,
            password=PASSWORD,
            roles=roles,
            team=team,
            email=f"{username}@example.test",
        )
    return user_model.objects.create_user(
        username=username,
        password=PASSWORD,
        roles=roles,
        team=team,
        email=f"{username}@example.test",
    )


def main():
    user_model = get_user_model()

    AssetAllocation.objects.filter(application__project__startswith="E2EC-").delete()
    Application.objects.filter(project__startswith="E2EC-").delete()
    ResourceAsset.objects.filter(name__startswith="E2EC-").delete()
    ResourceInventory.objects.filter(cardName__startswith="E2EC-").delete()
    SystemNotificationLog.objects.filter(sender__username__startswith="e2ec_").delete()
    user_model.objects.filter(username__startswith="e2ec_").delete()

    for team in TEAMS:
        ensure_option("TEAM", team)
    for form in CARD_FORMS:
        ensure_option("CARD_FORM", form)
    for card_type in CARD_TYPES:
        ensure_option("CARD_TYPE", card_type)
    for region in REGIONS:
        ensure_option("REGION", region)
    for project in PROJECTS:
        ensure_option("PROJECT", project)

    users = {
        "alpha_01": create_user("e2ec_alpha_applicant_01", "APPLICANT", TEAMS[0]),
        "alpha_02": create_user("e2ec_alpha_applicant_02", "APPLICANT", TEAMS[0]),
        "alpha_03": create_user("e2ec_alpha_applicant_03", "APPLICANT", TEAMS[0]),
        "beta_01": create_user("e2ec_beta_applicant_01", "APPLICANT", TEAMS[1]),
        "beta_02": create_user("e2ec_beta_applicant_02", "APPLICANT", TEAMS[1]),
        "beta_03": create_user("e2ec_beta_applicant_03", "APPLICANT", TEAMS[1]),
        "gamma_01": create_user("e2ec_gamma_applicant_01", "APPLICANT", TEAMS[2]),
        "gamma_02": create_user("e2ec_gamma_applicant_02", "APPLICANT", TEAMS[2]),
        "delta_01": create_user("e2ec_delta_applicant_01", "APPLICANT", TEAMS[3]),
        "delta_02": create_user("e2ec_delta_applicant_02", "APPLICANT", TEAMS[3]),
        "alpha_leader": create_user("e2ec_alpha_leader", "TEAM_LEADER", TEAMS[0]),
        "beta_leader": create_user("e2ec_beta_leader", "TEAM_LEADER", TEAMS[1]),
        "gamma_leader": create_user("e2ec_gamma_leader", "TEAM_LEADER", TEAMS[2]),
        "delta_leader": create_user("e2ec_delta_leader", "TEAM_LEADER", TEAMS[3]),
        "pre": create_user("e2ec_pre_approver", "APPROVER"),
        "dept": create_user("e2ec_dept_head", "DEPT_HEAD"),
        "executor": create_user("e2ec_executor_full", "EXECUTOR"),
        "admin": create_user("e2ec_admin_full", "ADMIN", is_superuser=True),
    }

    ResourceInventory.objects.create(
        cardName="E2EC-A100-BareMetal-Beijing",
        cardForm="裸机",
        cardType="A100",
        region="北京",
        totalCount=12,
        allocatedCount=0,
    )
    ResourceInventory.objects.create(
        cardName="E2EC-A800-Inference-Shanghai",
        cardForm="推理池",
        cardType="A800",
        region="上海",
        totalCount=10,
        allocatedCount=0,
    )
    ResourceInventory.objects.create(
        cardName="E2EC-H100-Training-Beijing",
        cardForm="训练池",
        cardType="H100",
        region="北京",
        totalCount=8,
        allocatedCount=0,
    )
    ResourceInventory.objects.create(
        cardName="E2EC-H200-BareMetal-Shenzhen",
        cardForm="裸机",
        cardType="H200",
        region="深圳",
        totalCount=8,
        allocatedCount=0,
    )
    ResourceInventory.objects.create(
        cardName="E2EC-L40S-Dev-Beijing",
        cardForm="开发池",
        cardType="L40S",
        region="北京",
        totalCount=12,
        allocatedCount=0,
    )
    emergency_inventory = ResourceInventory.objects.create(
        cardName="E2EC-Emergency-A100-Beijing",
        cardForm="裸机",
        cardType="A100",
        region="北京",
        totalCount=2,
        allocatedCount=2,
    )

    assets = [
        ("E2EC-FULL-A100-Node-01", "A100", "裸机", "北京", 4, "full-a100-secret-01"),
        ("E2EC-FULL-A100-Node-02", "A100", "裸机", "北京", 4, "full-a100-secret-02"),
        ("E2EC-FULL-A100-Node-03", "A100", "裸机", "北京", 4, "full-a100-secret-03"),
        ("E2EC-FULL-A800-Pool-01", "A800", "推理池", "上海", 5, ""),
        ("E2EC-FULL-A800-Pool-02", "A800", "推理池", "上海", 5, ""),
        ("E2EC-FULL-H100-Train-01", "H100", "训练池", "北京", 4, ""),
        ("E2EC-FULL-H100-Train-02", "H100", "训练池", "北京", 4, ""),
        ("E2EC-FULL-H200-Node-01", "H200", "裸机", "深圳", 4, "full-h200-secret-01"),
        ("E2EC-FULL-H200-Node-02", "H200", "裸机", "深圳", 4, "full-h200-secret-02"),
        ("E2EC-FULL-L40S-Dev-01", "L40S", "开发池", "北京", 4, ""),
        ("E2EC-FULL-L40S-Dev-02", "L40S", "开发池", "北京", 4, ""),
        ("E2EC-FULL-L40S-Dev-03", "L40S", "开发池", "北京", 4, ""),
    ]
    for index, (name, card_type, card_form, region, card_count, password) in enumerate(assets, 1):
        ResourceAsset.objects.create(
            name=name,
            ip=f"10.40.0.{index}",
            password=password,
            card_type=card_type,
            card_form=card_form,
            card_count=card_count,
            status="IDLE",
            region=region,
            specifications=f"{card_count} card E2EC asset",
        )

    donor_app = Application.objects.create(
        applicant=users["alpha_01"],
        users="e2ec_alpha_applicant_01",
        team=TEAMS[0],
        cardForm="裸机",
        cardType="A100",
        purpose="E2EC emergency donor",
        project="E2EC-Emergency-Donor",
        model_used="donor-model",
        priority="LOW",
        priorityReason="donor",
        count=2,
        minCount=1,
        startDate=date.today(),
        endDate=date.today() + timedelta(days=7),
        duration="7 days",
        status="EXECUTED",
        allocatedCount=2,
        allocatedCardType="A100",
        allocatedCardForm="裸机",
        allocatedRegion="北京",
        allocatedCardName=emergency_inventory.cardName,
        allocation_details=[
            {
                "inventory_id": emergency_inventory.id,
                "cardName": emergency_inventory.cardName,
                "region": emergency_inventory.region,
                "count": 2,
            }
        ],
        executionResult="E2EC donor already executed",
    )
    donor_asset = ResourceAsset.objects.create(
        name="E2EC-EMERG-A100-Donor-01",
        ip="10.40.9.1",
        password="emergency-donor-secret",
        card_type="A100",
        card_form="裸机",
        card_count=2,
        used_cards=2,
        status="IN_USE",
        region="北京",
        specifications="2 card emergency donor",
        owner=users["alpha_01"],
        current_users="e2ec_alpha_applicant_01",
        app_name="E2EC-Emergency-Donor",
    )
    AssetAllocation.objects.create(asset=donor_asset, application=donor_app, allocated_cards=2)

    ResourceInventory.objects.filter(cardType="A100", cardForm="裸机", region="北京").update(
        totalCount=0,
        allocatedCount=0,
    )
    ResourceInventory.objects.filter(cardName="E2EC-A100-BareMetal-Beijing").update(
        totalCount=4,
        allocatedCount=0,
    )
    ResourceInventory.objects.filter(cardName="E2EC-Emergency-A100-Beijing").update(
        totalCount=2,
        allocatedCount=2,
    )
    ResourceInventory.objects.filter(cardName="E2EC-A800-Inference-Shanghai").update(
        totalCount=10,
        allocatedCount=0,
    )
    ResourceInventory.objects.filter(cardName="E2EC-H100-Training-Beijing").update(
        totalCount=8,
        allocatedCount=0,
    )
    ResourceInventory.objects.filter(cardName="E2EC-H200-BareMetal-Shenzhen").update(
        totalCount=8,
        allocatedCount=0,
    )
    ResourceInventory.objects.filter(cardName="E2EC-L40S-Dev-Beijing").update(
        totalCount=12,
        allocatedCount=0,
    )

    SystemSetting.objects.update_or_create(
        key="auto_release_enabled",
        defaults={"value": "false", "description": "是否启用自动释放已到期卡资源"},
    )

    print("Comprehensive E2E seed data ready")


if __name__ == "__main__":
    main()
