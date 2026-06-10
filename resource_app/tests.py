from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from resource_app import views
from resource_app.models import Application, AssetAllocation, ResourceAsset, ResourceInventory, SystemOption


class AssetInventorySyncTests(TestCase):
    def test_asset_create_uses_existing_inventory_when_multiple_pools_share_dimensions(self):
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
            name="A100 Asset",
            card_type="A100",
            card_form="裸机",
            card_count=4,
            status="IDLE",
            region="北京",
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.totalCount, 5)
        self.assertEqual(second.totalCount, 2)


class PartialReleaseTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.executor = user_model.objects.create_user(
            username="partial_executor",
            password="pass",
            roles="EXECUTOR",
        )
        self.applicant = user_model.objects.create_user(
            username="partial_applicant",
            password="pass",
            roles="APPLICANT",
            team="Partial Team",
        )
        self.inventory = ResourceInventory.objects.create(
            cardName="Partial-A100-Pool",
            cardForm="裸机",
            cardType="A100",
            region="北京",
            totalCount=8,
            allocatedCount=4,
        )
        self.application = Application.objects.create(
            applicant=self.applicant,
            users="partial_applicant",
            team="Partial Team",
            cardForm="裸机",
            cardType="A100",
            purpose="partial release test",
            project="Partial Release Project",
            model_used="test-model",
            priority="MEDIUM",
            priorityReason="test",
            count=4,
            minCount=1,
            startDate=date.today(),
            endDate=date.today() + timedelta(days=7),
            duration="7 days",
            status="EXECUTED",
            allocatedCount=4,
            allocatedCardType="A100",
            allocatedCardForm="裸机",
            allocatedRegion="北京",
            allocatedCardName="Partial-A100-Pool",
            allocation_details=[
                {
                    "inventory_id": self.inventory.id,
                    "cardName": self.inventory.cardName,
                    "region": self.inventory.region,
                    "count": 4,
                }
            ],
            executionResult="executed",
        )
        self.asset = ResourceAsset.objects.create(
            name="Partial-A100-Node",
            password="secret",
            card_type="A100",
            card_form="裸机",
            card_count=4,
            used_cards=4,
            status="IN_USE",
            region="北京",
        )
        AssetAllocation.objects.create(
            asset=self.asset,
            application=self.application,
            allocated_cards=4,
        )

    def login_executor(self):
        self.client.force_login(self.executor)
        session = self.client.session
        session["active_role"] = "EXECUTOR"
        session.save()

    def test_partial_release_reduces_inventory_asset_and_keeps_application_executed(self):
        self.login_executor()

        response = self.client.post(
            "/execute/",
            {
                "action": "release",
                "app_id": str(self.application.id),
                "release_count": "2",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.inventory.refresh_from_db()
        self.asset.refresh_from_db()
        allocation = AssetAllocation.objects.get(application=self.application, asset=self.asset)

        self.assertEqual(self.application.status, "EXECUTED")
        self.assertEqual(self.application.allocatedCount, 2)
        self.assertEqual(self.application.allocation_details[0]["count"], 2)
        self.assertEqual(self.inventory.allocatedCount, 2)
        self.assertEqual(self.asset.used_cards, 2)
        self.assertEqual(self.asset.status, "PARTIAL")
        self.assertEqual(allocation.allocated_cards, 2)

    def test_full_release_without_release_count_releases_remaining_inventory_and_assets(self):
        self.login_executor()

        response = self.client.post(
            "/execute/",
            {
                "action": "release",
                "app_id": str(self.application.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.inventory.refresh_from_db()
        self.asset.refresh_from_db()

        self.assertEqual(self.application.status, "RELEASED")
        self.assertEqual(self.application.allocatedCount, 0)
        self.assertEqual(self.application.allocation_details, [])
        self.assertEqual(self.inventory.allocatedCount, 0)
        self.assertEqual(self.asset.used_cards, 0)
        self.assertEqual(self.asset.status, "IDLE")
        self.assertFalse(AssetAllocation.objects.filter(application=self.application).exists())

    def test_release_above_bound_asset_cards_does_not_change_state(self):
        allocation = AssetAllocation.objects.get(application=self.application, asset=self.asset)
        allocation.allocated_cards = 1
        allocation.save()
        self.asset.used_cards = 1
        self.asset.status = "PARTIAL"
        self.asset.save()
        self.login_executor()

        response = self.client.post(
            "/execute/",
            {
                "action": "release",
                "app_id": str(self.application.id),
                "release_count": "2",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.inventory.refresh_from_db()
        self.asset.refresh_from_db()
        allocation.refresh_from_db()

        self.assertEqual(self.application.status, "EXECUTED")
        self.assertEqual(self.application.allocatedCount, 4)
        self.assertEqual(self.application.allocation_details[0]["count"], 4)
        self.assertEqual(self.inventory.allocatedCount, 4)
        self.assertEqual(self.asset.used_cards, 1)
        self.assertEqual(self.asset.status, "PARTIAL")
        self.assertEqual(allocation.allocated_cards, 1)


class ApplicationStatisticsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            username="stats_admin",
            password="pass",
            roles="ADMIN",
            is_staff=True,
        )
        self.applicant = user_model.objects.create_user(
            username="stats_applicant",
            password="pass",
            roles="APPLICANT",
            team="Stats Team",
        )
        for card_type in ["A100", "H200"]:
            SystemOption.objects.get_or_create(category="CARD_TYPE", value=card_type)

    def create_application(self, **overrides):
        data = {
            "applicant": self.applicant,
            "users": self.applicant.username,
            "team": "Stats Team",
            "cardForm": "裸机",
            "cardType": "A100",
            "purpose": "statistics test",
            "project": "Stats Project",
            "model_used": "stats-model",
            "priority": "MEDIUM",
            "priorityReason": "statistics",
            "count": 1,
            "minCount": 1,
            "startDate": date.today(),
            "endDate": date.today() + timedelta(days=7),
            "duration": "7 days",
            "status": "PENDING_TEAM",
        }
        data.update(overrides)
        return Application.objects.create(**data)

    def login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session["active_role"] = "ADMIN"
        session.save()

    def test_application_statistics_aggregate_global_request_demand(self):
        self.create_application(project="Project Alpha", cardType="A100", cardForm="裸机", count=2)
        self.create_application(
            project="Project Alpha",
            cardType="A100",
            cardForm="推理池",
            count=3,
            status="APPROVED",
            allocatedCount=3,
            allocatedCardType="A100",
            allocatedCardForm="推理池",
        )
        self.create_application(
            project="Project Beta",
            cardType="H200",
            cardForm="裸机",
            count=4,
            status="EXECUTED",
            allocatedCount=2,
            allocatedCardType="H200",
            allocatedCardForm="裸机",
        )
        self.create_application(
            project="Project Cancelled",
            cardType="H200",
            cardForm="裸机",
            count=99,
            status="CANCELLED",
        )

        stats = views.build_application_statistics()

        self.assertEqual(stats["total_applications"], 3)
        self.assertEqual(stats["total_projects"], 2)
        self.assertEqual(stats["total_requested_cards"], 9)
        self.assertEqual(stats["status_summary"]["PENDING_TEAM"]["application_count"], 1)
        self.assertEqual(stats["status_summary"]["APPROVED"]["application_count"], 1)
        self.assertEqual(stats["status_summary"]["EXECUTED"]["application_count"], 1)
        self.assertEqual(stats["card_type_summary"][0]["card_type"], "A100")
        self.assertEqual(stats["card_type_summary"][0]["application_count"], 2)
        self.assertEqual(stats["card_type_summary"][0]["requested_count"], 5)
        self.assertEqual(stats["card_type_summary"][1]["card_type"], "H200")
        self.assertEqual(stats["card_type_summary"][1]["application_count"], 1)
        self.assertEqual(stats["card_type_summary"][1]["requested_count"], 4)
        self.assertEqual(stats["card_form_summary"][0]["card_form"], "裸机")
        self.assertEqual(stats["card_form_summary"][0]["requested_count"], 6)

    def test_dashboard_and_statistics_pages_expose_application_statistics(self):
        self.create_application(project="Project Alpha", cardType="A100", count=2)
        self.create_application(project="Project Beta", cardType="H200", count=4)
        self.login_admin()

        dashboard_response = self.client.get("/")
        statistics_response = self.client.get("/statistics/")

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(statistics_response.status_code, 200)
        self.assertEqual(dashboard_response.context["application_stats"]["total_applications"], 2)
        self.assertEqual(statistics_response.context["application_stats"]["total_projects"], 2)
