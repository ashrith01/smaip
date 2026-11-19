# Preserve the Vultr GPU before destroying it

Prepared October 31, 2026. The owner runs these commands manually. The assistant
has not connected to, stopped, snapshotted or destroyed the instance.

The original probe parameters and returned development results are already preserved
in the Mac repository. This additional archive captures the known GPU project
directories and environment inventory. A separate Vultr disk snapshot preserves the
installed environment and cached Qwen weights. The current GPU source is checkpoint
`9d40bd7`; newer protocol-4 repairs are in the local repository and must be transferred
to the replacement instance before using them.

## 1. Upload the helper from a Mac terminal

```bash
scp "/Users/ashrithvadde/Documents/GitHub/smaip/scripts/gpu/backup_before_destroy.sh" root@45.63.76.130:/root/smaip-backup-before-destroy.sh
ssh root@45.63.76.130
```

## 2. Create and test the backup on the GPU

```bash
nvidia-smi
```

Wait for any remaining model/training job to finish before backing up.

```bash
bash /root/smaip-backup-before-destroy.sh
```

Continue only after it prints `Archive created and integrity check passed`. It
creates `/root/smaip-preserve-2026-10-31.tar.gz` and a `.sha256` checksum. It includes
the known `smaip`, recovery and open-model checkout folders that exist, with their
source/results/probes, plus package/Python/OS/GPU inventory. Virtual environments,
Git metadata, caches and `.env` files are excluded. The snapshot preserves the
environment/cache. The helper refuses to overwrite an existing backup.

If this name already exists, preserve it. For a genuinely new backup choose a fresh
name with `SMAIP_BACKUP_NAME=smaip-preserve-2026-10-31-02`; use that name consistently
in the download/checksum commands below.

## 3. Download and verify on the Mac

Exit the SSH session:

```bash
exit
```

Then, on the Mac:

```bash
mkdir -p "$HOME/Downloads/smaip-gpu-backup-2026-10-31"
cd "$HOME/Downloads/smaip-gpu-backup-2026-10-31"
scp root@45.63.76.130:/root/smaip-preserve-2026-10-31.tar.gz .
scp root@45.63.76.130:/root/smaip-preserve-2026-10-31.tar.gz.sha256 .
shasum -a 256 -c smaip-preserve-2026-10-31.tar.gz.sha256
```

Require `smaip-preserve-2026-10-31.tar.gz: OK`. Keep the downloaded archive outside
the Git repository. This checks transfer integrity; it is not an independent
restore test of the full GPU environment.

## 4. Create and retain the Vultr snapshot

In Vultr: Products → Compute → the GPU instance → Snapshots. Enter
`smaip-before-v2-2026-10-31` as the label and create the snapshot. Wait until the
provider reports it completed/available, and record its ID. This snapshot includes
the instance disk. Any separately attached external storage needs its own backup.
[Vultr GPU snapshot instructions](https://docs.vultr.com/products/compute/instances/cloud-gpu/features/snapshots).

Only after the Mac checksum passes and the snapshot completes, use **Destroy
Server** on this GPU instance. Retain the snapshot. Destruction deletes the server
and releases its public IP; it cannot be undone without saved data.
[Vultr destruction instructions](https://docs.vultr.com/products/compute/instances/cloud-gpu/management/destroy-instance).

Snapshots continue to incur storage charges separately from the destroyed GPU.
[Snapshot billing](https://docs.vultr.com/product-overviews/snapshots).

## Later: create the replacement GPU

Deploy a compatible GPU instance from the retained snapshot. Use the new instance's
IP for SSH; do not assume the old address remains yours. Verify `nvidia-smi`, the
Python environment and pinned cached model before resuming. Transfer the latest
source bundle from the Mac repository; the snapshot contains the old GPU checkout,
not later local changes.

If deploying a fresh OS instead, upload the local backup and extract into a staging
directory first. Its source/results/probes are portable, but its environment inventory
is a record, not a promise that installing every old package version on a new OS/GPU
will work. Rebuild the environment and re-download the pinned Qwen model as needed.
Do not start V2 fitting until the planned protocol-4 clean regression and pinned
feature-extractor smoke checks pass on that instance.

## Helper verification

The helper was syntax-checked and run locally against temporary fixture directories.
The check confirmed preservation of results/metadata, exclusion of virtual
environments/cache/environment-secret files, readable gzip/tar output, matching
SHA-256, and refusal to overwrite. It was not run by the assistant on the rental.
