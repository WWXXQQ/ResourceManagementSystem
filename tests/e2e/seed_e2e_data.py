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
    IssueFeedback,
    ResourceAsset,
    ResourceInventory,
    SystemNotificationLog,
    SystemOption,
    SystemSetting,
)


PASSWORD = "TestPass123!"
TEAM = "\u5e73\u53f0\u56e2\u961f"
BARE_METAL = "\u88f8\u673a"
INFERENCE_POOL = "\u63a8\u7406\u6c60"
BEIJING = "\u5317\u4eac"


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

    AssetAllocation.objects.filter(application__applicant__username__startswith="e2e_").delete()
    Application.objects.filter(applicant__username__startswith="e2e_").delete()
    ResourceAsset.objects.filter(name__startswith="E2E-").delete()
    ResourceInventory.objects.filter(cardName__startswith="E2E-").delete()
    IssueFeedback.objects.filter(user__username__startswith="e2e_").delete()
    SystemNotificationLog.objects.filter(sender__username__startswith="e2e_").delete()
    SystemSetting.objects.all().delete()
    SystemOption.objects.all().delete()
    user_model.objects.filter(username__startswith="e2e_").delete()

    users = {
        "applicant": create_user("e2e_applicant", "APPLICANT", TEAM),
        "leader": create_user("e2e_leader", "TEAM_LEADER", TEAM),
        "approver": create_user("e2e_approver", "APPROVER"),
        "dept": create_user("e2e_dept", "DEPT_HEAD"),
        "executor": create_user("e2e_executor", "EXECUTOR"),
        "admin": create_user("e2e_admin", "ADMIN", is_superuser=True),
    }

    options = {
        "TEAM": [TEAM],
        "CARD_FORM": [BARE_METAL, INFERENCE_POOL],
        "CARD_TYPE": ["A100", "H100"],
        "PROJECT": ["E2E-Shortage", "E2E-Execution"],
        "REGION": [BEIJING],
    }
    for category, values in options.items():
        for value in values:
            SystemOption.objects.create(category=category, value=value)

    ResourceInventory.objects.create(
        cardName="E2E-A100-Beijing-Pool",
        cardForm=BARE_METAL,
        cardType="A100",
        region=BEIJING,
        totalCount=2,
        allocatedCount=0,
    )
    exec_inv = ResourceInventory.objects.create(
        cardName="E2E-H100-Beijing-Pool",
        cardForm=BARE_METAL,
        cardType="H100",
        region=BEIJING,
        totalCount=4,
        allocatedCount=2,
    )

    Application.objects.create(
        applicant=users["applicant"],
        users="e2e_applicant",
        team=TEAM,
        cardForm=BARE_METAL,
        cardType="A100",
        purpose="E2E shortage validation",
        project="E2E-Shortage",
        model_used="e2e-model",
        priority="HIGH",
        priorityReason="E2E",
        count=3,
        minCount=1,
        startDate=date.today(),
        endDate=date.today() + timedelta(days=7),
        duration="7 days",
        status="PENDING_PRE",
        team_leader_note="approved",
    )

    Application.objects.create(
        applicant=users["applicant"],
        users="e2e_applicant",
        team=TEAM,
        cardForm=BARE_METAL,
        cardType="H100",
        purpose="E2E execution validation",
        project="E2E-Execution",
        model_used="e2e-model",
        priority="MEDIUM",
        priorityReason="E2E",
        count=2,
        minCount=1,
        startDate=date.today(),
        endDate=date.today() + timedelta(days=7),
        duration="7 days",
        status="APPROVED",
        allocatedCount=2,
        allocatedCardType="H100",
        allocatedCardForm=BARE_METAL,
        allocatedRegion=BEIJING,
        allocatedCardName=exec_inv.cardName,
        final_approver_note="approved",
        allocation_details=[
            {
                "inventory_id": exec_inv.id,
                "cardName": exec_inv.cardName,
                "region": exec_inv.region,
                "count": 2,
            }
        ],
    )

    ResourceAsset.objects.create(
        name="E2E-H100-Node-1",
        ip="10.0.0.11",
        password="node-secret-1",
        card_type="H100",
        card_form=BARE_METAL,
        card_count=1,
        status="IDLE",
        region=BEIJING,
        specifications="1 card test node",
    )
    ResourceAsset.objects.create(
        name="E2E-H100-Node-2",
        ip="10.0.0.12",
        password="node-secret-2",
        card_type="H100",
        card_form=BARE_METAL,
        card_count=2,
        status="IDLE",
        region=BEIJING,
        specifications="2 card test node",
    )

    print("E2E seed data ready")


if __name__ == "__main__":
    main()
