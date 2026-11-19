# Vultr GPU decommission — completed October 31, 2026

The owner explicitly authorized a one-time Chrome action after a two-hour delay:
verify the completed recovery snapshot, then destroy only `smaip-gpu`.

- Instance: `smaip-gpu`, ID `d10de51e-b276-4fb8-ae63-6238b6b850a5`.
- Former public IP: `45.63.76.130`; do not assume it remains assigned to the owner.
- Scheduled earliest action: October 31, 2026, 07:45:13 UTC (02:45:13 America/Chicago).
- Execution/verification: approximately 07:48 UTC (02:48 America/Chicago), after the required delay.
- Before destruction, the instance snapshot table showed `smaip-before-v2-2026-10-31`,
  ID `81ac6673-bbcf-4e49-9c5d-0b0c4109e74c`, status **Available**, reported size **700 GB**.
- The destroy confirmation identified `45.63.76.130 smaip-gpu`. After submission,
  Vultr displayed **Your VPS has been terminated**. The instances list then contained
  only the unrelated `retrohabits` instance; `smaip-gpu` was absent.
- After destruction, the global snapshot list still showed the exact recovery
  snapshot, source instance ID matching the destroyed GPU, creation time
  `2026-10-31 05:37:18`, reported size **700 GB**, status **Complete**.
- No snapshot, other instance or other storage resource was deleted. No replacement
  instance was created. Snapshot storage is retained and separately billable.

Recovery snapshot page:
[smaip-before-v2-2026-10-31](https://console.vultr.com/snapshots/details/?id=81ac6673-bbcf-4e49-9c5d-0b0c4109e74c).

The UI status/size were verified; no replacement-instance restore test was performed.
GPU environment/source in the snapshot reflects the previous on-GPU checkout.
Transfer the latest local source and verify the environment, protocol-4 quality
regression and feature collection before V2 probe fitting.
