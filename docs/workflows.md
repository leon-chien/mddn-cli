# Workflows

## Standard HF Workflow

```bash
mddatanet init my_project
mddatanet prepare my_project --topology system.pdb --trajectory run.dcd
mddatanet analyze my_project --preset ligand_unbinding --ligand "resname LIG" --pocket protein
mddatanet package my_project
mddatanet validate my_project
mddatanet publish my_project --repo-id USER/my-dataset
```

## Custom Metric Workflow

```bash
mddatanet prepare my_project --topology system.pdb --trajectory run.xtc
mddatanet analyze my_project --custom-script metrics.py --func my_metric --primary-metric my_metric
mddatanet package my_project
```

The custom function must return one numeric scalar per frame.

## Manual Event Tagging

```bash
mddatanet tag my_project --event activation_transition --start-frame 2000 --end-frame 2400
```

The event must be listed in `mddatanet.yaml`.

## Metadata-First Search

After publishing, users can inspect the lightweight split first:

```python
from datasets import load_dataset

index = load_dataset("USER/my-dataset", split="metadata_index")
```

Then they can stream heavy rows:

```python
stream = load_dataset("USER/my-dataset", split="train", streaming=True)
```
