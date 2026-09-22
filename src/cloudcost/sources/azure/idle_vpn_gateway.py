import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry

AZ_CLI = shutil.which("az.cmd") or shutil.which("az") or "az"

def _normalize_region(location: str) -> str:
    """Normalize Azure CLI display region for the Retail Prices API."""
    return location.lower().replace(" ", "")


def _fetch_hourly_price(sku_name: str, region: str) -> float:
    """Fetch the live hourly VPN Gateway deployment price."""
    region = _normalize_region(region)

    filter_str = (
        f"armRegionName eq '{region}' "
        f"and serviceName eq 'VPN Gateway' "
        f"and skuName eq '{sku_name}' "
        f"and meterName eq '{sku_name}' "
        f"and priceType eq 'Consumption'"
    )

    try:
        raw = subprocess.run(
            [
                "curl",
                "-s",
                "-G",
                "https://prices.azure.com/api/retail/prices",
                "--data-urlencode",
                f"$filter={filter_str}",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout

        data = json.loads(raw)

        items = [
            item
            for item in data.get("Items", [])
            if (
                item.get("unitOfMeasure") == "1 Hour"
                and item.get("meterName") == sku_name
            )
        ]

        return float(items[0]["retailPrice"]) if items else 0.0

    except Exception:
        return 0.0


# Real Azure VPN Gateway metric:
# "AverageBandwidth" with Average aggregation and PT1H interval.
# Verified against a live Azure VPN Gateway during real-world testing.
@registry.register_source("azure.idle_vpn_gateway")
class AzureIdleVpnGatewaySource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)

        if not self.resource_group:
            raise ValueError(
                "azure.idle_vpn_gateway requires 'resource_group' in config"
            )

    def extract(self, context: Any = None) -> pa.Table:
        gateways_raw = subprocess.run(
            [
                AZ_CLI,
                "network",
                "vnet-gateway",
                "list",
                "--resource-group",
                self.resource_group,
                "--query",
                "[?gatewayType=='Vpn'].{id:id,name:name,sku:sku.name,location:location}",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        gateways = json.loads(gateways_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []

        for gateway in gateways:
            raw = subprocess.run(
                [
                    AZ_CLI,
                    "monitor",
                    "metrics",
                    "list",
                    "--resource",
                    gateway["id"],
                    "--metric",
                    "AverageBandwidth",
                    "--aggregation",
                    "Average",
                    "--interval",
                    "PT1H",
                    "--start-time",
                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time",
                    end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            parsed = json.loads(raw)

            bandwidth_values = []

            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        average = point.get("average")

                        if average is not None:
                            bandwidth_values.append(float(average))

            avg_bandwidth = (
                sum(bandwidth_values) / len(bandwidth_values)
                if bandwidth_values
                else 0.0
            )

            sku_name = gateway.get("sku", "unknown")
            location = gateway.get("location", "eastus")

            rows.append(
                {
                    "resource_id": gateway["id"].lower(),
                    "resource_name": gateway["name"],
                    "sku": sku_name,
                    "location": _normalize_region(location),
                    "avg_bandwidth_bps": avg_bandwidth,
                    "hourly_price": _fetch_hourly_price(
                        sku_name,
                        location,
                    ),
                    "lookback_days": self.lookback_days,
                }
            )

        if not rows:
            return pa.table(
                {
                    "resource_id": pa.array([], type=pa.string()),
                    "resource_name": pa.array([], type=pa.string()),
                    "sku": pa.array([], type=pa.string()),
                    "location": pa.array([], type=pa.string()),
                    "avg_bandwidth_bps": pa.array([], type=pa.float64()),
                    "hourly_price": pa.array([], type=pa.float64()),
                    "lookback_days": pa.array([], type=pa.int64()),
                }
            )

        return pa.table(
            {
                "resource_id": [r["resource_id"] for r in rows],
                "resource_name": [r["resource_name"] for r in rows],
                "sku": [r["sku"] for r in rows],
                "location": [r["location"] for r in rows],
                "avg_bandwidth_bps": [r["avg_bandwidth_bps"] for r in rows],
                "hourly_price": [r["hourly_price"] for r in rows],
                "lookback_days": [r["lookback_days"] for r in rows],
            }
        )
