-- Real check: VMs in "VM stopped" power state, not "VM deallocated" --
-- Azure's own az vm stop help text says it plainly: "The VM will continue
-- to be billed." This is a genuinely common trap: stopping a VM from the
-- portal's power icon, or a script that calls stop instead of deallocate,
-- looks identical to a real user (VM is off) but keeps billing compute.
-- billed_cost here is a placeholder using a real observed B1s Linux
-- price ($0.0104/hr, confirmed live via the Retail Prices API elsewhere
-- in this project) -- a real per-VM live price lookup by size, matching
-- the vm_sizing_recommendation check's approach, would replace this if
-- extended to cover arbitrary VM sizes.
SELECT
    'azure' AS provider,
    resource_id,
    'Virtual Machines' AS service_name,
    ROUND(0.0104 * 730, 2) AS billed_cost,
    resource_name,
    resource_group,
    vm_size,
    'VM stopped but not deallocated -- still billing compute (' || vm_size || ')' AS evidence_reason
FROM fact_stopped_not_deallocated_vms;
