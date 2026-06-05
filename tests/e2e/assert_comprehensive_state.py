import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gpu_management.settings")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import django

django.setup()

from django.db.models import Sum

from resource_app.models import Application, AssetAllocation, ResourceAsset, ResourceInventory


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    for inventory in ResourceInventory.objects.all():
        assert_true(inventory.allocatedCount >= 0, f"{inventory} allocatedCount is negative")
        assert_true(
            inventory.allocatedCount <= inventory.totalCount,
            f"{inventory} allocatedCount exceeds totalCount",
        )

    for asset in ResourceAsset.objects.all():
        allocation_sum = (
            AssetAllocation.objects.filter(asset=asset).aggregate(total=Sum("allocated_cards"))["total"]
            or 0
        )
        assert_true(asset.used_cards >= 0, f"{asset} used_cards is negative")
        assert_true(asset.used_cards <= asset.card_count, f"{asset} used_cards exceeds card_count")
        assert_true(
            asset.used_cards == allocation_sum,
            f"{asset} used_cards {asset.used_cards} != allocation sum {allocation_sum}",
        )

    expected_executed = [
        "E2EC-Normal-Alpha-02",
        "E2EC-Normal-Alpha-03",
        "E2EC-Normal-Beta-01",
        "E2EC-Normal-Beta-02",
        "E2EC-Normal-Beta-03",
        "E2EC-Normal-Gamma-01",
        "E2EC-Normal-Gamma-02",
        "E2EC-Normal-Delta-01",
        "E2EC-Normal-Delta-02",
        "E2EC-Emergency-Urgent",
    ]
    for project in expected_executed:
        app = Application.objects.get(project=project)
        assert_true(app.status == "EXECUTED", f"{project} expected EXECUTED, got {app.status}")

    partial = Application.objects.get(project="E2EC-Normal-Alpha-01")
    assert_true(partial.status == "EXECUTED", "partial release app should remain EXECUTED")
    assert_true(partial.allocatedCount == 1, "partial release app should have 1 card remaining")

    donor = Application.objects.get(project="E2EC-Emergency-Donor")
    assert_true(donor.allocatedCount == 0, "emergency donor should be fully preempted")
    assert_true(
        not donor.asset_allocations.exists(),
        "emergency donor should not retain active asset allocations after full preemption",
    )

    print("Comprehensive E2E invariants passed")


if __name__ == "__main__":
    main()
