# Quickstart

## Install

```bash
python -m pip install -e ".[dev]"
```

## Run The Demo

```bash
mddatanet demo
mddatanet validate outputs/ligand_unbinding_demo_hf
mddatanet inspect outputs/ligand_unbinding_demo_hf
```

The demo writes:

```text
outputs/ligand_unbinding_demo_hf/
  mddatanet.yaml
  .mddn_cache/
    mddatanet.json
    dataset_card.md
    validation_report.json
    data/
    metadata_index/
```

## Prepare Your Own Data

```bash
mddatanet init my_project
mddatanet inspect --topology system.pdb --trajectory run.dcd
mddatanet prepare my_project --topology system.pdb --trajectory run.dcd
mddatanet analyze my_project --preset ligand_unbinding --ligand "resname LIG" --pocket protein
mddatanet package my_project
mddatanet validate my_project
```

## Publish

```bash
mddatanet publish my_project --repo-id USER/my-dataset
```

For a local upload preview:

```bash
mddatanet publish my_project --repo-id USER/my-dataset --dry-run-out /tmp/upload_preview
```
