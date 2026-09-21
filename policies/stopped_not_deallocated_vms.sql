-- Real check: VMs in "VM stopped" power state, not "VM deallocated" --
-- Azure's own az vm stop help text says it plainly: "The VM will continue
-- to be billed." This is a genuinely common trap: stopping a VM from the
-- portal's power icon, or a script that calls stop instead of deallocate,
-- looks identical to a real user (VM is off) but keeps billing compute.
-- Price is fetched live per VM's real size via the Retail Prices API --
-- fixing a real bug where every stopped VM used to be priced as a flat
-- B1s ($0.0104/hr) regardless of actual size, which could underprice a
-- large VM's waste by 50x or more.
SELECT
    'azure' AS provider,
    resource_id,
    'Virtual Machines' AS service_name,
    ROUND(hourly_price * 730, 2) AS billed_cost,
    resource_name,
    resource_group,
    vm_size,
    'VM stopped but not deallocated -- still billing compute (' || vm_size || ')' AS evidence_reason
FROM fact_stopped_not_deallocated_vms
WHERE hourly_price > 0;
