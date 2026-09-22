import json

from typer.testing import CliRunner

from cloudcost.cli import app


runner = CliRunner()


def test_report_generates_html_summary(tmp_path) -> None:
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps(
            [
                {
                    "policy_name": "idle_app_service_plans",
                    "provider": "azure",
                    "service_name": "App Service Plan",
                    "severity": "high",
                    "estimated_impact": 125.5,
                    "resource_id": "plan-1",
                },
                {
                    "policy_name": "idle_bastion",
                    "provider": "azure",
                    "service_name": "Bastion",
                    "severity": "medium",
                    "estimated_impact": 50.25,
                    "resource_id": "bastion-1",
                },
            ]
        )
    )
    output_path = tmp_path / "report.html"

    result = runner.invoke(
        app,
        ["report", "--input", str(findings_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.stdout
    assert output_path.exists()
    html = output_path.read_text()
    assert "CloudCost Findings Report" in html
    assert "125.50" in html
    assert "$175.75" in html
