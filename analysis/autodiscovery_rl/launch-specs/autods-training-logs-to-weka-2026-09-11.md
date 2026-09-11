# AutoDiscovery-RL training logs → Weka

Completed on 2026-09-11 PDT.

## Destination

- Path: `/weka/nora-default/sijial/training-logs/autodiscovery-rl-2026-09-11`
- Disk usage reported on Weka: 5.8 GiB
- Extracted files: 194
- Top-level contents: `collected-runs-2026-09-06`, nine `fmt*` result directories, `launch-specs`, `results_2026-08-27_28.tsv`, and `.DS_Store`

## Transfer provenance

- Local archive: `/private/tmp/autodiscovery-rl-training-logs-2026-09-11.tar.gz`
- Compressed archive size: 1,745,194,511 bytes
- Archive SHA-256: `cfc59538cb195100244de973ef7e459cb1a3cd9edb6b131193d2e7ee4794ea7b`
- Beaker staging dataset: `01M290EXVHSY41S4SKBDPZ3VRJ`
- Successful Beaker experiment: `01M291TJTE5N6XWJT3FHZVPF81`
- Successful job: `01M291TJYNFTGMVT0C139BN818`
- Verification result dataset: `01M291TJTPP7DV7A05WG03WSAJ`
- Exit code: 0

The job verified the compressed archive hash, extracted to a temporary Weka directory, checked the 194-file count, synchronized writes, and atomically renamed the directory into its final path.

## Earlier attempts

- Experiment `01M290ZBHVT6QA32R2E8VVPGEK` was canceled while unallocated on Jupiter.
- Experiment `01M2918ZF7WNGMB17JPGM961B4` extracted successfully but exited 1 because its expected file count was incorrectly set to 190. The cleanup trap removed its temporary extraction directory, so it did not publish an incomplete destination.
