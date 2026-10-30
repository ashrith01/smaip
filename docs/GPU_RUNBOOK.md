# Week 7 GPU runbook

One GPU is enough. Qwen2.5-3B-Instruct in fp16 is about 6 GB of weights. A single NVIDIA GPU with 24 GB of VRAM holds the weights, the residual-stream forwards for the probe, and a small vLLM batch. Do not provision a cluster. The makefile does not start a multi-GPU job.

This repository does not create cloud resources. You create the instance, run the commands below, copy the tarball off, and destroy the instance.

## Instance

- Ubuntu image with an NVIDIA driver new enough that `nvidia-smi` prints a GPU.
- One GPU, 24 GB of VRAM or more. A 16 GB card can hold the 3B weights and still run out of room once vLLM allocates a KV cache. Prefer 24 GB.
- Examples of that shape: one L4 24 GB, one A10 24 GB, one L40S, or one A100. The exact Vultr plan name changes. Pick by VRAM, not by GPU count.
- Disk: 80 GB free is comfortable. PyTorch, vLLM, and the Hugging Face cache are the bulky pieces. The 3B checkpoint itself is small next to those.
- No extra nodes, no shared file system, no scheduler.

The CPU smoke (`make week7-cpu` with `SMAIP_PROBE_BACKEND=mock`) is what CI runs. Run that on a laptop before you pay for the GPU hour. It does not download weights. The real CPU check, once `.[hf]` is installed, is the same command without the mock backend: it loads `Qwen/Qwen2.5-0.5B-Instruct` on CPU over the tiny subset.

## Steps

1. Create one Ubuntu GPU instance and SSH in. Confirm the driver:

   ```bash
   nvidia-smi
   ```

2. Install git and clone this repository. From the checkout:

   ```bash
   bash scripts/gpu/bootstrap.sh
   source .venv/bin/activate
   set -a && source .venv/smaip-gpu.env && set +a
   ```

   Bootstrap creates `.venv`, installs `.[dev,hf]`, attempts the `gpu` extra (vLLM), and creates the Hugging Face cache directory (`HF_HOME`, default `$HOME/.cache/huggingface`). A vLLM install failure is printed and does not stop bootstrap. It does not download the model yet. The first `make week7-gpu` does that into `HF_HOME`.

3. Run the weekend command:

   ```bash
   make week7-gpu
   ```

   That installs the extras if bootstrap was skipped, then:

   - collects residual-stream activations for the Week 5 and Week 6 pages and the original tool-output set
   - trains a logistic probe per layer for the last-token linear probe and the mean-pooled activation probe
   - remeasures the six ablations with those probes
   - runs the HF versus vLLM benchmark when both CUDA and vLLM import
   - writes `reports/week7-gpu-results.tar.gz`

   The default model is `Qwen/Qwen2.5-3B-Instruct`. Override it for this run only with `SMAIP_PROBE_MODEL` or `--model`. Do not point it at a 70B checkpoint on a 24 GB card.

   Layer choice is a sweep over every transformer block unless `SMAIP_PROBE_LAYERS` or `--layers` is a comma-separated list such as `8,16,24`.

4. Copy the tarball off the box before you tear it down:

   ```bash
   scp <host>:~/smaip/reports/week7-gpu-results.tar.gz .
   ```

   The archive contains `reports/RESULTS_week7.md`, `reports/week7_eval.json`, `reports/week7_bench.json`, and `artifacts/probes/` (weights, chosen layer, threshold, AUROC, F1, FPR at the target TPR). Raw activations stay in `artifacts/activations/` on the box and are not in the tarball.

## What the command does, and how long it takes

On a fresh box the long parts are the pip install of vLLM and the download of the 3B weights. After that, collection is one forward per record (the Week 5 and Week 6 pages plus the tool-output file, on the order of a hundred sequences). Training the logistic probes is a CPU loop over saved vectors and finishes in well under a minute. The ablation remeasure runs a forward when a trained probe scores a page. The benchmark loads the model once in Hugging Face and once in vLLM and times a few concurrency levels (1, 4, and 8).

Plan on about an hour on a fresh 24 GB box, most of it installation and the weight download. The collection, training, ablations, and benchmark after the weights are local are tens of minutes, not a multi-hour distributed job. A second run with the cache warm is the shorter of those two.

If vLLM failed to install, `python3 -m smaip.cli bench` still exits 0 and writes `skipped: true` with the reason. CUDA missing does the same. Neither case downloads a model inside the benchmark.

## Outputs

| path | contents |
| --- | --- |
| `artifacts/probes/linear.json` | last-token logistic probe: weights, layer, threshold, metrics |
| `artifacts/probes/activation.json` | mean-pooled logistic probe, same fields |
| `artifacts/activations/summary.json` | record count, layer list, hidden size, backend |
| `reports/RESULTS_week7.md` | probe table and the six ablations on both suites |
| `reports/week7_eval.json` | the same numbers as JSON |
| `reports/week7_bench.json` | tokens/s, TTFT, p50/p95, defense overhead, or a skip |
| `reports/week7-gpu-results.tar.gz` | the report, the eval JSON, the bench JSON, and the probe files |

The file `reports/RESULTS_week7.md` committed in git is the CPU smoke (mock backend, tiny subset, 0.5B model id). The GPU command overwrites it on the box. It does not overwrite `reports/RESULTS.md`, which stays the Week 6 stub measurement.

## Teardown

GPU instances bill while they exist. After the tarball is on your laptop, destroy the instance in the Vultr dashboard. Stopping it is not the same as destroying it: a stopped GPU node can keep a charge on the disk or the card. Delete the instance when you have the archive. Nothing in this repo deletes it for you.
