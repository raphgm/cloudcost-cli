import json

from typer.testing import CliRunner

from cloudcost.cli import app


runner = CliRunner()


def _write_findings(tmp_path):
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps(
            [
                {"resource_id": "/sub/vm-a", "policy_name": "stopped_not_deallocated_vms", "severity": "high", "estimated_impact": 100.0},
                {"resource_id": "/sub/vm-a", "policy_name": "untagged_resources", "severity": "low", "estimated_impact": 0.0},
                {"resource_id": "/sub/disk-b", "policy_name": "unattached_disks", "severity": "medium", "estimated_impact": 250.5},
                {"resource_id": None, "policy_name": "github_wasted_actions_minutes", "severity": "low", "estimated_impact": 5.0},
            ]
        )
    )
    return findings_path


def test_findings_summary_groups_by_resource_sorted_by_impact(tmp_path) -> None:
    findings_path = _write_findings(tmp_path)

    result = runner.invoke(app, ["findings", "summary", "--input", str(findings_path)])

    assert result.exit_code == 0, result.stdout
    assert "2 resources" in result.stdout
    # Rich folds long cells at the test runner's 80-col width, so check the
    # combined impact per resource rather than the full policy list.
    assert "$100.00" in result.stdout
    assert "$250.50" in result.stdout
    # Highest combined impact first.
    assert result.stdout.index("disk-b") < result.stdout.index("vm-a")
    assert "$350.50" in result.stdout


def test_findings_summary_min_findings_filters_single_hit_resources(tmp_path) -> None:
    findings_path = _write_findings(tmp_path)

    result = runner.invoke(app, ["findings", "summary", "--input", str(findings_path), "--min-findings", "2"])

    assert result.exit_code == 0, result.stdout
    assert "1 resources" in result.stdout
    assert "vm-a" in result.stdout
    assert "disk-b" not in result.stdout
    assert "$100.00" in result.stdout


def test_findings_summary_missing_file(tmp_path) -> None:
    result = runner.invoke(app, ["findings", "summary", "--input", str(tmp_path / "nope.json")])

    assert result.exit_code == 0
    assert "No findings generated yet" in result.stdout
