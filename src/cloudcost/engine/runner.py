from cloudcost.config.loader import PipelineConfig
from cloudcost.core.registry import registry
from rich.console import Console

console = Console()

# We need to import the plugins so they register themselves
import cloudcost.sources.local.file_sources
try:
    import cloudcost.sources.aws.billing
    import cloudcost.sources.azure.billing
    import cloudcost.sources.azure.metrics
    import cloudcost.sources.azure.unattached_disks
    import cloudcost.sources.azure.unassociated_public_ips
    import cloudcost.sources.azure.vm_sizing
    import cloudcost.sources.azure.untagged_resources
    import cloudcost.sources.azure.idle_load_balancers
    import cloudcost.sources.azure.old_snapshots
    import cloudcost.sources.azure.sql_dtu_metrics
    import cloudcost.sources.azure.stopped_not_deallocated_vms
    import cloudcost.sources.azure.empty_storage_accounts
    import cloudcost.sources.azure.idle_app_service_plans
    import cloudcost.sources.azure.orphaned_nsgs
    import cloudcost.sources.azure.premium_disk_downsize
    import cloudcost.sources.azure.idle_nat_gateways
    import cloudcost.sources.azure.idle_container_registries
    import cloudcost.sources.azure.idle_app_gateways
    import cloudcost.sources.azure.redis_idle_metrics
    import cloudcost.sources.azure.idle_bastion
    import cloudcost.sources.azure.idle_private_endpoints
    import cloudcost.sources.azure.cosmosdb_idle_ru
    import cloudcost.sources.azure.idle_firewall
    import cloudcost.sources.azure.idle_vpn_gateway
    import cloudcost.sources.azure.log_analytics_idle_commitment
    import cloudcost.sources.azure.idle_container_instances
    import cloudcost.sources.azure.idle_eventhub
    import cloudcost.sources.azure.idle_servicebus_premium
    import cloudcost.sources.azure.aks_idle_nodepool
    import cloudcost.sources.azure.idle_vmss
    import cloudcost.sources.azure.idle_front_door
    import cloudcost.sources.azure.postgres_idle_flexible
    import cloudcost.sources.azure.mysql_idle_flexible
    import cloudcost.sources.azure.idle_signalr
    import cloudcost.sources.azure.idle_traffic_manager
    import cloudcost.sources.azure.idle_dns_zone
    import cloudcost.sources.azure.idle_app_configuration
    import cloudcost.sources.azure.idle_managed_grafana
    import cloudcost.sources.azure.idle_static_web_app
    import cloudcost.sources.azure.idle_batch_pool
    import cloudcost.sources.azure.idle_premiumv2_disk_overage
    import cloudcost.sources.azure.cosmosdb_mongo_idle_ru
    import cloudcost.sources.azure.cosmosdb_cassandra_idle_ru
    import cloudcost.sources.azure.cosmosdb_gremlin_idle_ru
    import cloudcost.sources.azure.idle_container_apps_dedicated
    import cloudcost.sources.azure.idle_acr_geo_replication
    import cloudcost.sources.azure.idle_functions_premium_min_instances
    import cloudcost.sources.azure.idle_logic_apps_standard
    import cloudcost.sources.azure.cosmosdb_table_idle_ru
    import cloudcost.sources.azure.idle_public_ip_prefix
    import cloudcost.sources.azure.idle_openai_ptu
    import cloudcost.sources.oci.billing
    import cloudcost.sources.alibaba.billing
except ImportError as e:
    # Handle if dependencies aren't installed yet, but they should be
    console.print(f"[yellow]Warning: Could not load some cloud sources: {e}[/yellow]")

try:
    import cloudcost.sources.github.wasted_actions_minutes
except ImportError as e:
    console.print(f"[yellow]Warning: Could not load GitHub sources: {e}[/yellow]")

try:
    import cloudcost.sources.aws.inventory
except ImportError:
    pass

import cloudcost.destinations.duckdb_dest
try:
    import cloudcost.destinations.postgres.dest
    import cloudcost.destinations.bigquery.dest
except ImportError as e:
    console.print(f"[yellow]Warning: Could not load some destinations: {e}[/yellow]")
import cloudcost.transforms.normalize
try:
    import cloudcost.transforms.join
except ImportError:
    pass

def run_pipeline(pipeline: PipelineConfig):
    console.print(f"[bold blue]Executing Pipeline:[/bold blue] {pipeline.pipeline.name}")
    
    # 1. Initialize all plugins
    sources = {}
    for src_cfg in pipeline.sources:
        PluginClass = registry.get_source(src_cfg.type)
        sources[src_cfg.name] = PluginClass(src_cfg.config)
        console.print(f"Initialized source: {src_cfg.name} ({src_cfg.type})")
        
    transforms = {}
    for tr_cfg in pipeline.transforms:
        PluginClass = registry.get_transform(tr_cfg.type)
        transforms[tr_cfg.name] = (PluginClass(tr_cfg.config or {}), tr_cfg)
        console.print(f"Initialized transform: {tr_cfg.name} ({tr_cfg.type})")

    destinations = {}
    for dest_cfg in pipeline.destinations:
        PluginClass = registry.get_destination(dest_cfg.type)
        destinations[dest_cfg.name] = PluginClass(dest_cfg.config)
        console.print(f"Initialized destination: {dest_cfg.name} ({dest_cfg.type})")

    # 2. Execute extraction
    # In a real system, this would be a DAG or streaming iterator
    extracted_data = {}
    for name, source_plugin in sources.items():
        console.print(f"[cyan]Extracting from source:[/cyan] {name}")
        table = source_plugin.extract()
        extracted_data[name] = table
        console.print(f"  -> Extracted {table.num_rows} rows")

    # 3. Execute transforms
    transformed_data = {}
    for name, (transform_plugin, tr_cfg) in transforms.items():
        console.print(f"[cyan]Transforming data:[/cyan] {name}")
        
        if tr_cfg.inputs:
            # Multi-input transform (like join)
            input_tables = {}
            for inp in tr_cfg.inputs:
                input_tables[inp] = transformed_data.get(inp, extracted_data.get(inp))
            table = transform_plugin.transform(input_tables)
        else:
            # Single input transform
            inp = tr_cfg.input
            input_table = transformed_data.get(inp, extracted_data.get(inp))
            table = transform_plugin.transform(input_table)
            
        transformed_data[name] = table
        console.print(f"  -> Transformed {table.num_rows if hasattr(table, 'num_rows') else 0} rows")

    # 4. Execute loads
    for load_cfg in pipeline.loads:
        console.print(f"[cyan]Loading data to destination:[/cyan] {load_cfg.destination}")
        input_name = load_cfg.input
        
        if input_name in transformed_data:
            input_table = transformed_data[input_name]
        else:
            input_table = extracted_data[input_name]
            
        dest_plugin = destinations[load_cfg.destination]
        dest_plugin.load(input_table, load_cfg)
        console.print(f"  -> Loaded {input_table.num_rows} rows into {load_cfg.destination}")

    console.print(f"[bold green]Pipeline {pipeline.pipeline.name} execution completed successfully![/bold green]")
