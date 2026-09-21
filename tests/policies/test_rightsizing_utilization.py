import pyarrow as pa
import pytest

IDLE = "idle (high confidence)"
UNDERUTILIZED = "underutilized"


def cost(resource_id: str = "vm1", service: str = "Virtual Machines", billed: float = 30.0) -> dict:
    return {"resource_id": resource_id, "service_name": service, "billed_cost": billed}


def metric(
    resource_id: str = "vm1",
    cpu: float = 2.0,
    net_in: float = 0.0,
    net_out: float = 0.0,
    disk_read: float = 0.0,
    disk_write: float = 0.0,
) -> dict:
    return {
        "resource_id": resource_id,
        "avg_cpu_percent": cpu,
        "avg_network_in_bytes": net_in,
        "avg_network_out_bytes": net_out,
        "avg_disk_read_ops": disk_read,
        "avg_disk_write_ops": disk_write,
    }


def costs(*rows: dict) -> pa.Table:
    return pa.table(
        {
            "provider": pa.array(["azure" for _ in rows], type=pa.string()),
            "resource_id": pa.array([r["resource_id"] for r in rows], type=pa.string()),
            "service_name": pa.array([r["service_name"] for r in rows], type=pa.string()),
            "billed_cost": pa.array([r["billed_cost"] for r in rows], type=pa.float64()),
        }
    )


def metrics(*rows: dict) -> pa.Table:
    return pa.table(
        {
            "resource_id": pa.array([r["resource_id"] for r in rows], type=pa.string()),
            "avg_cpu_percent": pa.array([r["avg_cpu_percent"] for r in rows], type=pa.float64()),
            "avg_network_in_bytes": pa.array([r["avg_network_in_bytes"] for r in rows], type=pa.float64()),
            "avg_network_out_bytes": pa.array([r["avg_network_out_bytes"] for r in rows], type=pa.float64()),
            "avg_disk_read_ops": pa.array([r["avg_disk_read_ops"] for r in rows], type=pa.float64()),
            "avg_disk_write_ops": pa.array([r["avg_disk_write_ops"] for r in rows], type=pa.float64()),
        }
    )


def rightsizing(run_policy, cost_rows: pa.Table, metric_rows: pa.Table):
    return run_policy("rightsizing_utilization", {"fact_cost": cost_rows, "fact_metrics": metric_rows})


def test_vm_with_no_activity_on_any_axis_is_idle_with_high_confidence(run_policy) -> None:
    findings = rightsizing(
        run_policy,
        costs(cost(billed=30.0)),
        metrics(metric(cpu=2.0, net_in=100.0, net_out=100.0, disk_read=1.0, disk_write=1.0)),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "Virtual Machines"
    assert finding.estimated_impact == 30.0
    assert finding.evidence["confidence"] == IDLE
    assert finding.evidence["evidence_reason"].startswith("CPU 2.0%")


@pytest.mark.parametrize(
    "busy_axis",
    [
        {"net_in": 1_000_000.0},
        {"net_out": 1_000_000.0},
        {"disk_read": 50.0},
        {"disk_write": 50.0},
        {"net_in": 50_000.0},
        {"net_out": 50_000.0},
        {"disk_read": 5.0},
        {"disk_write": 5.0},
    ],
)
def test_low_cpu_with_activity_on_any_other_axis_is_only_underutilized(run_policy, busy_axis) -> None:
    findings = rightsizing(run_policy, costs(cost()), metrics(metric(cpu=2.0, **busy_axis)))

    assert findings[0].evidence["confidence"].startswith(UNDERUTILIZED)


def test_cpu_of_5_percent_is_no_longer_idle(run_policy) -> None:
    findings = rightsizing(run_policy, costs(cost()), metrics(metric(cpu=5.0)))

    assert findings[0].evidence["confidence"].startswith(UNDERUTILIZED)


def test_moderate_cpu_is_underutilized_even_with_no_other_traffic(run_policy) -> None:
    findings = rightsizing(run_policy, costs(cost()), metrics(metric(cpu=12.0)))

    assert findings[0].evidence["confidence"].startswith(UNDERUTILIZED)


def test_cpu_at_20_percent_is_not_reported(run_policy) -> None:
    findings = rightsizing(run_policy, costs(cost()), metrics(metric(cpu=20.0)))

    assert findings == []


def test_cpu_just_under_20_percent_is_reported(run_policy) -> None:
    findings = rightsizing(run_policy, costs(cost()), metrics(metric(cpu=19.9)))

    assert [f.resource_id for f in findings] == ["vm1"]


def test_metrics_are_averaged_across_rows_before_grading(run_policy) -> None:
    findings = rightsizing(run_policy, costs(cost()), metrics(metric(cpu=2.0), metric(cpu=8.0)))

    finding = findings[0]
    assert finding.evidence["evidence_reason"].startswith("CPU 5.0%")
    assert finding.evidence["confidence"].startswith(UNDERUTILIZED)


def test_costs_are_summed_per_vm(run_policy) -> None:
    findings = rightsizing(run_policy, costs(cost(billed=10.0), cost(billed=5.5)), metrics(metric()))

    assert len(findings) == 1
    assert findings[0].estimated_impact == 15.5


def test_resource_ids_are_matched_ignoring_case(run_policy) -> None:
    findings = rightsizing(
        run_policy,
        costs(cost(resource_id="/SUB/RG/VM1")),
        metrics(metric(resource_id="/sub/rg/vm1")),
    )

    assert [f.resource_id for f in findings] == ["/SUB/RG/VM1"]


def test_services_other_than_virtual_machines_are_ignored(run_policy) -> None:
    findings = rightsizing(run_policy, costs(cost(service="Storage")), metrics(metric()))

    assert findings == []


def test_vm_with_zero_cost_is_ignored(run_policy) -> None:
    findings = rightsizing(run_policy, costs(cost(billed=0.0)), metrics(metric()))

    assert findings == []


def test_vm_without_metrics_is_not_reported(run_policy) -> None:
    findings = rightsizing(run_policy, costs(cost()), metrics(metric(resource_id="other")))

    assert findings == []
