from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from resource_app.models import Application, ResourceAsset, ResourceInventory


class UserRoleTests(TestCase):
    def test_get_role_display_supports_multiple_roles(self):
        user = get_user_model().objects.create_user(
            username="multi_role",
            password="pass",
            roles="APPLICANT,APPROVER",
        )

        self.assertEqual(user.get_role_display(), "申请人,预审人/审批人")

    def test_user_roles_api_returns_configured_roles(self):
        get_user_model().objects.create_user(
            username="role_api_user",
            password="pass",
            roles="APPLICANT,TEAM_LEADER",
        )

        response = self.client.get("/api/user/roles/", {"username": "role_api_user"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["roles"], ["APPLICANT", "TEAM_LEADER"])


class ApplicationStatsSignalTests(TestCase):
    def setUp(self):
        self.applicant = get_user_model().objects.create_user(
            username="stats_applicant",
            password="pass",
            roles="APPLICANT",
            team="Batch Team",
        )

    def test_application_save_calculates_card_count_and_card_days(self):
        app = Application.objects.create(
            applicant=self.applicant,
            users="stats_applicant",
            team="Batch Team",
            cardForm="裸机",
            cardType="A100",
            purpose="batch stats",
            project="Batch Project",
            model_used="model-a",
            priority="MEDIUM",
            priorityReason="batch",
            count=3,
            minCount=1,
            startDate=date.today(),
            endDate=date.today() + timedelta(days=5),
            duration="5 days",
        )

        self.assertEqual(app.card_count, 3)
        self.assertEqual(app.card_days, 15)

    def test_allocated_count_is_used_for_card_statistics(self):
        app = Application.objects.create(
            applicant=self.applicant,
            users="stats_applicant",
            team="Batch Team",
            cardForm="裸机",
            cardType="A100",
            purpose="batch allocated stats",
            project="Batch Allocated Project",
            model_used="model-b",
            priority="MEDIUM",
            priorityReason="batch",
            count=8,
            minCount=1,
            startDate=date.today(),
            endDate=date.today() + timedelta(days=7),
            duration="7 days",
            allocatedCount=4,
        )

        self.assertEqual(app.card_count, 4)
        self.assertEqual(app.card_days, 28)


class AssetInventorySignalTests(TestCase):
    def test_asset_create_adds_capacity_to_existing_inventory(self):
        inventory = ResourceInventory.objects.create(
            cardName="A100 Pool",
            cardForm="裸机",
            cardType="A100",
            region="北京",
            totalCount=2,
            allocatedCount=0,
        )

        ResourceAsset.objects.create(
            name="A100 Node",
            card_type="A100",
            card_form="裸机",
            card_count=4,
            region="北京",
        )

        inventory.refresh_from_db()
        self.assertEqual(inventory.totalCount, 6)

    def test_asset_create_uses_first_matching_inventory_when_multiple_pools_exist(self):
        first = ResourceInventory.objects.create(
            cardName="A100 Pool A",
            cardForm="裸机",
            cardType="A100",
            region="北京",
            totalCount=1,
            allocatedCount=0,
        )
        second = ResourceInventory.objects.create(
            cardName="A100 Pool B",
            cardForm="裸机",
            cardType="A100",
            region="北京",
            totalCount=2,
            allocatedCount=0,
        )

        ResourceAsset.objects.create(
            name="A100 Node",
            card_type="A100",
            card_form="裸机",
            card_count=4,
            region="北京",
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.totalCount, 5)
        self.assertEqual(second.totalCount, 2)
