# MDDataNet

MDDataNet is a Hugging Face-native CLI for turning molecular dynamics
trajectories into streaming-ready ML datasets.

It reads MDAnalysis-compatible topology and trajectory files, filters atoms,
writes per-frame coordinate/force tensors to Parquet, computes frame-aligned
metrics and event labels, creates train/validation/test splits plus a lightweight
`metadata_index`, validates the workspace, and publishes directly to Hugging Face
Datasets.

## Install

```bash
python -m pip install -e ".[dev]"
```

Ray is a required dependency for the `prepare` command.

## Five-Minute Demo

```bash
mddatanet demo
mddatanet validate outputs/ligand_unbinding_demo_hf
mddatanet inspect outputs/ligand_unbinding_demo_hf
```

The demo generates a tiny ligand-unbinding trajectory at runtime, prepares
per-frame Parquet shards, applies the ligand-unbinding analysis, packages local
Hugging Face split files, and performs a no-network publish dry run.

## Main Workflow

```bash
mddatanet init my_project

mddatanet inspect \
  --topology system.pdb \
  --trajectory trajectory.dcd

mddatanet prepare my_project \
  --topology system.pdb \
  --trajectory trajectory.dcd \
  --chunk-size 5000

mddatanet analyze my_project \
  --preset ligand_unbinding \
  --ligand "resname LIG" \
  --pocket "protein" \
  --param distance_threshold=15.0

mddatanet tag my_project \
  --event ligand_unbinding \
  --start-frame 1000 \
  --end-frame 1300

mddatanet package my_project --hf-repo-link USER/my-dataset
mddatanet validate my_project
mddatanet publish my_project --repo-id USER/my-dataset
```

For a no-network publish smoke test:

```bash
mddatanet publish my_project \
  --repo-id USER/my-dataset \
  --dry-run-out /tmp/mddatanet_upload_preview
```

## Local Workspace

```text
project_root/
  mddatanet.yaml
  .mddn_cache/
    mddatanet.json
    dataset_card.md
    validation_report.json
    data/
      train-00000-of-00001.parquet
      validation-00000-of-00001.parquet
      test-00000-of-00001.parquet
    metadata_index/
      index-00000-of-00001.parquet
```

## What MDDataNet Is Not

MDDataNet is not an MD simulation engine, not a custom archive registry, and no
longer targets `.mddatanet.zip` as the final product format. Hugging Face
Datasets is the storage and discovery layer.

## Docs

- [Quickstart](docs/quickstart.md)
- [Command Reference](docs/command_reference.md)
- [Package Format](docs/package_format.md)
- [Workflows](docs/workflows.md)
- [Troubleshooting](docs/troubleshooting.md)
