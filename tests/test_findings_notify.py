import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from typer.testing import CliRunner

from cloudcost.cli import app


runner = CliRunner()


class CaptureHandler(BaseHTTPRequestHandler):
    payload = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        CaptureHandler.payload = json.loads(body.decode("utf-8"))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        return


def test_findings_notify_posts_summary_to_webhook(tmp_path) -> None:
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps(
            [
                {"policy_name": "idle_app_service_plans", "provider": "azure", "service_name": "App Service Plan", "severity": "high", "estimated_impact": 125.5},
                {"policy_name": "idle_bastion", "provider": "azure", "service_name": "Bastion", "severity": "medium", "estimated_impact": 50.25},
            ]
        )
    )

    server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        result = runner.invoke(
            app,
            ["findings", "notify", "--webhook-url", f"http://127.0.0.1:{port}", "--input", str(findings_path)],
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.exit_code == 0, result.stdout
    assert CaptureHandler.payload is not None
    assert CaptureHandler.payload["text"].startswith("CloudCost findings summary")
    assert "2 findings" in CaptureHandler.payload["text"]
    assert "$175.75" in CaptureHandler.payload["text"]
