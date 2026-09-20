from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Markdown
from textual.containers import Container
import json
from cloudcost.core.capabilities import capabilities_registry

class CloudCostDashboard(App):
    """A Textual terminal dashboard for CloudCost CLI."""
    
    CSS = """
    DataTable {
        height: 1fr;
    }
    """
    
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"), ("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        self.table = DataTable()
        yield Container(self.table)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "CloudCost CLI Dashboard"
        self.table.add_columns("Finding ID", "Provider", "Service", "Severity", "Impact ($)", "Policy")
        
        # Load findings
        try:
            with open("data/findings.json", "r") as f:
                findings = json.load(f)
                
            for finding in findings:
                self.table.add_row(
                    finding.get("finding_id", "N/A")[:8],
                    finding.get("provider", "N/A"),
                    finding.get("service_name", "N/A"),
                    finding.get("severity", "N/A").upper(),
                    str(finding.get("estimated_impact", 0.0)),
                    finding.get("policy_name", "N/A")
                )
        except FileNotFoundError:
            self.table.add_row("No findings", "-", "-", "-", "-", "-")

def run_dashboard():
    app = CloudCostDashboard()
    app.run()
