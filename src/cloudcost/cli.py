import typer
from rich.console import Console

app = typer.Typer(help="CloudCost CLI - Enterprise Multi-Cloud FinOps Data Platform")
console = Console()

@app.command()
def init():
    """Initialize a new CloudCost pipeline configuration."""
    console.print("[green]Initializing CloudCost project...[/green]")
    console.print("Created sample [bold]cloudcost.yml[/bold]")

from cloudcost.config.loader import load_config
import os
import sys

from cloudcost.core.capabilities import capabilities_registry
import json

providers_app = typer.Typer(help="Manage and discover cloud provider capabilities.")
app.add_typer(providers_app, name="providers")

@providers_app.command("list")
def list_providers():
    """List all registered cloud providers."""
    providers = capabilities_registry.list_providers()
    console.print("[blue]Registered Cloud Providers:[/blue]")
    for p in providers:
        console.print(f"  - [bold]{p}[/bold]")

@providers_app.command("inspect")
def inspect_provider(provider: str):
    """Inspect capabilities for a specific cloud provider."""
    caps = capabilities_registry.get_capabilities(provider)
    if not caps:
        console.print(f"[red]Provider '{provider}' not found.[/red]")
        sys.exit(1)
        
    console.print(f"[blue]Capabilities for [bold]{provider}[/bold]:[/blue]")
    # Dump the pydantic model directly to nice JSON formatting
    console.print_json(caps.model_dump_json())

from cloudcost.policies.runner import PolicyRunner
from cloudcost.config.loader import load_config

policy_app = typer.Typer(help="Manage and run governance policies.")
app.add_typer(policy_app, name="policy")

findings_app = typer.Typer(help="View and manage optimization findings.")
app.add_typer(findings_app, name="findings")

# In-memory mock store for findings (in a real app, this would write back to a DB)
_findings_store = []

@policy_app.command("run")
def run_policies(config: str = typer.Argument("cloudcost.yml", help="Path to configuration file")):
    """Run SQL policies defined in the configuration."""
    console.print(f"[blue]Running policies from {config}...[/blue]")
    try:
        pipeline = load_config(config)

        # PolicyRunner used to always default to "data/cloudcost.duckdb"
        # regardless of what the pipeline's own destinations actually
        # configured — sync would succeed against e.g.
        # "data/cloudcost-azure-real.duckdb" and policy run would then fail
        # with "database does not exist" against a file that was never
        # created. Use the first duckdb destination actually declared in
        # this pipeline's config instead.
        duckdb_destinations = [d for d in pipeline.destinations if d.type == "duckdb"]
        if not duckdb_destinations:
            raise ValueError(f"No duckdb destination found in {config} — policy run requires one to query.")
        db_path = duckdb_destinations[0].config.get("path")
        if not db_path:
            raise ValueError(f"duckdb destination '{duckdb_destinations[0].name}' has no 'path' configured.")

        runner = PolicyRunner(db_path=db_path)
        total_findings = 0
        
        for policy_cfg in pipeline.policies:
            console.print(f"Evaluating policy: [bold]{policy_cfg.name}[/bold]")
            findings = runner.run_policy(policy_cfg)
            _findings_store.extend(findings)
            total_findings += len(findings)
            console.print(f"  -> Generated {len(findings)} findings.")
            
        console.print(f"[green]Policy execution complete. Total findings: {total_findings}[/green]")

        # Real bug fixed: this used to open findings.json in "w" mode and
        # dump only _findings_store (a module-level list that starts empty
        # every process, since each `policy run` invocation is a fresh
        # CLI process) -- so every run silently discarded all findings
        # from every prior pipeline. Every check in this project lives in
        # its own YAML pipeline, so without this fix `findings list` and
        # the dashboard could only ever show the single most recently run
        # check, never the combined picture across checks.
        # Merge with whatever's already on disk, deduping by
        # (resource_id, policy_name) so a rerun of the same check updates
        # its entry instead of duplicating it, and write the union back.
        existing_findings = []
        if os.path.exists("data/findings.json"):
            try:
                with open("data/findings.json", "r") as f:
                    existing_findings = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                existing_findings = []

        merged = {(f["resource_id"], f["policy_name"]): f for f in existing_findings}
        for finding in _findings_store:
            data = finding.model_dump()
            merged[(data["resource_id"], data["policy_name"])] = json.loads(json.dumps(data, default=str))

        with open("data/findings.json", "w") as f:
            json.dump(list(merged.values()), f, default=str)
            
    except Exception as e:
        console.print(f"[red]Policy execution failed: {e}[/red]")
        sys.exit(1)

@findings_app.command("list")
def list_findings(severity: str = typer.Option(None, help="Filter by severity")):
    """List generated optimization findings."""
    try:
        with open("data/findings.json", "r") as f:
            findings = json.load(f)
            
        if severity:
            findings = [f for f in findings if f["severity"].lower() == severity.lower()]
            
        if not findings:
            console.print("[green]No findings to display![/green]")
            return
            
        console.print(f"[blue]Found {len(findings)} findings:[/blue]")
        for f in findings:
            color = "red" if f["severity"] == "high" else "yellow" if f["severity"] == "medium" else "cyan"
            console.print(f"[{color}][{f['severity'].upper()}][/{color}] {f['policy_name']} -> {f['provider']} ({f['service_name']}) Impact: ${f['estimated_impact']}")
    except FileNotFoundError:
        console.print("[yellow]No findings generated yet. Run `cloudcost policy run` first.[/yellow]")

@app.command()
def validate(config: str = typer.Argument("cloudcost.yml", help="Path to pipeline configuration file")):
    """Validate a CloudCost pipeline configuration file."""
    console.print(f"[blue]Validating pipeline config: {config}[/blue]")
    try:
        pipeline = load_config(config)
        console.print(f"[green]Configuration '{pipeline.pipeline.name}' is valid.[/green]")
    except Exception as e:
        console.print(f"[red]Configuration validation failed: {e}[/red]")
        sys.exit(1)

from cloudcost.engine.runner import run_pipeline

@app.command()
def sync(config: str = typer.Argument("cloudcost.yml", help="Path to pipeline configuration file")):
    """Execute a CloudCost pipeline sync."""
    console.print(f"[blue]Starting pipeline sync for {config}...[/blue]")
    try:
        pipeline = load_config(config)
        run_pipeline(pipeline)
    except Exception as e:
        console.print(f"[red]Pipeline sync failed: {e}[/red]")
        sys.exit(1)

iac_app = typer.Typer(help="Correlate cloud costs with Infrastructure-as-Code.")
app.add_typer(iac_app, name="iac")

@iac_app.command("map")
def iac_map(
    state: str = typer.Option(..., help="Path to terraform.tfstate file"),
    findings: str = typer.Option("data/findings.json", help="Path to findings JSON file")
):
    """Map infrastructure code directly to FinOps findings."""
    from cloudcost.iac.terraform import TerraformMapper
    
    console.print(f"[blue]Mapping Terraform state {state} to findings...[/blue]")
    try:
        mapper = TerraformMapper(state)
        mapped = mapper.map_findings(findings)
        
        if not mapped:
            console.print("[yellow]No direct mappings found between Terraform state and current findings.[/yellow]")
            return
            
        console.print(f"[green]Successfully mapped {len(mapped)} findings to Terraform source code![/green]")
        for m in mapped:
            console.print(f"- [red]{m['severity'].upper()}[/red] {m['policy_name']} on [bold]{m['terraform_address']}[/bold] (Cost Impact: ${m['estimated_impact']})")
            
    except Exception as e:
        console.print(f"[red]Failed to map IaC: {e}[/red]")
        sys.exit(1)

@app.command()
def dashboard():
    """Launch the interactive CloudCost terminal dashboard."""
    from cloudcost.tui.app import run_dashboard
    run_dashboard()

@app.command()
def query(
    sql: str = typer.Argument(..., help="SQL query to execute against the unified data warehouse")
):
    """Run an ad-hoc SQL query against your multi-cloud data."""
    import duckdb
    from rich.table import Table
    
    try:
        with duckdb.connect("data/cloudcost.duckdb", read_only=True) as conn:
            result = conn.execute(sql)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            
            table = Table(title="Query Results")
            for col in columns:
                table.add_column(col, style="cyan")
                
            for row in rows:
                table.add_row(*[str(val) for val in row])
                
            console.print(table)
    except Exception as e:
        console.print(f"[red]Query failed: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    app()
