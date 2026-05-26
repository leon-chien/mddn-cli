# Command Reference

MDDataNet is now workspace-first and Hugging Face-native.

## `mddatanet init`

Create `mddatanet.yaml`.

```bash
mddatanet init my_project
```

Fails if the descriptor already exists unless `--overwrite` is passed.

## `mddatanet inspect`

Inspect raw MD sources:

```bash
mddatanet inspect --topology system.pdb --trajectory run.dcd
```

Or inspect a prepared workspace:

```bash
mddatanet inspect my_project
```

## `mddatanet prepare`

Use Ray workers to convert source trajectory frame ranges into per-frame Parquet
shards under `.mddn_cache/data/`.

```bash
mddatanet prepare my_project \
  --topology system.pdb \
  --trajectory run.dcd \
  --chunk-size 5000
```

Solvent is stripped by default. Use `--keep-solvent` or `--atom-selection`.

## `mddatanet analyze`

Append frame-aligned metrics and operational labels.

```bash
mddatanet analyze my_project \
  --preset ligand_unbinding \
  --ligand "resname LIG" \
  --pocket protein \
  --param distance_threshold=15.0
```

Custom metric:

```bash
mddatanet analyze my_project --custom-script metric.py --func my_metric
```

## `mddatanet tag`

Inject explicit interval labels after validating against
`mddatanet.yaml labels.allowed_events`.

```bash
mddatanet tag my_project --event ligand_unbinding --start-frame 1000 --end-frame 1300
```

## `mddatanet package`

Create official Hugging Face split files and `metadata_index`.

```bash
mddatanet package my_project --train-frac 0.8 --validation-frac 0.1 --test-frac 0.1
```

## `mddatanet validate`

Validate project config, structural manifest, Parquet schemas, frame coverage,
and metadata index.

```bash
mddatanet validate my_project
```

Writes `.mddn_cache/validation_report.json`.

## `mddatanet publish`

Upload finalized assets to Hugging Face.

```bash
mddatanet publish my_project --repo-id USER/my-dataset
```

Use `--dry-run-out` to materialize upload files locally without network access.

## `mddatanet load`

Thin wrapper over `datasets.load_dataset`.

```bash
mddatanet load USER/my-dataset --split train
```

## `mddatanet benchmark`

List or load pinned benchmark repositories.

```bash
mddatanet benchmark
mddatanet benchmark ligand_unbinding_demo --load
```
