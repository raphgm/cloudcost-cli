import glob
import json
import os

import duckdb
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)


def _discover_duckdb_files(data_dir: str = "data") -> list[str]:
    # Real architecture fact: every check's pipeline YAML writes to its
    # own separate .duckdb file (e.g. data/idle-batch-real.duckdb,
    # data/cosmosdb-table-idle-real.duckdb) -- there is no single
    # unified inventory database. Discovering all of them here is what
    # makes a "view your whole cloud estate" tab possible without a
    # pipeline redesign: browse across every file a check has ever
    # written to.
    if not os.path.isdir(data_dir):
        return []
    return sorted(glob.glob(os.path.join(data_dir, "*.duckdb")))


class CloudCostDashboard(App):
    """A Textual terminal dashboard for CloudCost CLI."""

    CSS = """
    DataTable {
        height: 1fr;
    }
    #estate-controls, #query-controls {
        height: auto;
        padding: 1;
    }
    #query-input {
        width: 1fr;
    }
    #query-status {
        height: auto;
        padding: 0 1;
    }
    """

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"), ("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent():
            with TabPane("Findings", id="findings-tab"):
                yield DataTable(id="findings-table")
            with TabPane("Cloud Estate", id="estate-tab"):
                with Horizontal(id="estate-controls"):
                    yield Select([], id="estate-db-select", prompt="Select a .duckdb file")
                    yield Select([], id="estate-table-select", prompt="Select a table")
                yield DataTable(id="estate-table")
            with TabPane("Query", id="query-tab"):
                with Horizontal(id="query-controls"):
                    yield Select([], id="query-db-select", prompt="Select a .duckdb file")
                    yield Input(placeholder="SELECT * FROM ...", id="query-input")
                yield Static("", id="query-status")
                yield DataTable(id="query-results")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "CloudCost CLI Dashboard"
        self._load_findings()
        self._load_db_file_lists()

    def _load_findings(self) -> None:
        table = self.query_one("#findings-table", DataTable)
        table.add_columns("Finding ID", "Provider", "Service", "Severity", "Impact ($)", "Policy")
        try:
            with open("data/findings.json", "r") as f:
                findings = json.load(f)
            for finding in findings:
                table.add_row(
                    finding.get("finding_id", "N/A")[:8],
                    finding.get("provider", "N/A"),
                    finding.get("service_name", "N/A"),
                    finding.get("severity", "N/A").upper(),
                    str(finding.get("estimated_impact", 0.0)),
                    finding.get("policy_name", "N/A"),
                )
        except FileNotFoundError:
            table.add_row("No findings", "-", "-", "-", "-", "-")

    def _load_db_file_lists(self) -> None:
        db_files = _discover_duckdb_files()
        options = [(os.path.basename(p), p) for p in db_files]
        self.query_one("#estate-db-select", Select).set_options(options)
        self.query_one("#query-db-select", Select).set_options(options)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "estate-db-select" and event.value != Select.BLANK:
            self._load_estate_tables(event.value)
        elif event.select.id == "estate-table-select" and event.value != Select.BLANK:
            db_path = self.query_one("#estate-db-select", Select).value
            self._load_estate_table_rows(db_path, event.value)

    def _load_estate_tables(self, db_path: str) -> None:
        table_select = self.query_one("#estate-table-select", Select)
        try:
            with duckdb.connect(db_path, read_only=True) as conn:
                tables = conn.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
                ).fetchall()
            table_select.set_options([(t[0], t[0]) for t in tables])
        except Exception as e:
            table_select.set_options([])
            self._show_estate_error(str(e))

    def _load_estate_table_rows(self, db_path: str, table_name: str) -> None:
        estate_table = self.query_one("#estate-table", DataTable)
        estate_table.clear(columns=True)
        try:
            with duckdb.connect(db_path, read_only=True) as conn:
                result = conn.execute(f"SELECT * FROM {table_name} LIMIT 200")
                columns = [desc[0] for desc in result.description]
                rows = result.fetchall()
            estate_table.add_columns(*columns)
            for row in rows:
                estate_table.add_row(*[str(v) for v in row])
        except Exception as e:
            estate_table.add_columns("Error")
            estate_table.add_row(str(e))

    def _show_estate_error(self, message: str) -> None:
        estate_table = self.query_one("#estate-table", DataTable)
        estate_table.clear(columns=True)
        estate_table.add_columns("Error")
        estate_table.add_row(message)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "query-input":
            return
        db_select = self.query_one("#query-db-select", Select)
        status = self.query_one("#query-status", Static)
        results_table = self.query_one("#query-results", DataTable)
        results_table.clear(columns=True)

        db_path = db_select.value
        if db_path == Select.BLANK or db_path is None:
            status.update("[red]Select a .duckdb file first.[/red]")
            return

        sql = event.value.strip()
        if not sql:
            return

        try:
            with duckdb.connect(db_path, read_only=True) as conn:
                result = conn.execute(sql)
                columns = [desc[0] for desc in result.description]
                rows = result.fetchall()
            results_table.add_columns(*columns)
            for row in rows:
                results_table.add_row(*[str(v) for v in row])
            status.update(f"[green]{len(rows)} row(s) returned.[/green]")
        except Exception as e:
            status.update(f"[red]{e}[/red]")


def run_dashboard():
    app = CloudCostDashboard()
    app.run()
