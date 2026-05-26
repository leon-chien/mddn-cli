# MDDataNet CLI Full Build Specification

MDDataNet is an open-source CLI and Python library that bridges molecular
dynamics simulations and machine learning by producing Hugging Face-native,
Parquet-backed trajectory datasets.

## Product Direction

The current architecture is a hard replacement of the earlier `.mddatanet.zip`
and custom Hub registry workflow. Hugging Face Datasets is the canonical storage,
registry, streaming, and discovery layer.

MDDataNet prepares:

```text
trajectory frames + physical metrics + event labels + metadata index
```

for downstream ML users.

## Workspace Blueprint

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

## Commands

- `mddatanet init`
- `mddatanet inspect`
- `mddatanet prepare`
- `mddatanet analyze`
- `mddatanet tag`
- `mddatanet package`
- `mddatanet validate`
- `mddatanet publish`
- `mddatanet load`
- `mddatanet benchmark`
- `mddatanet demo`

## Data Schemas

Heavy split Parquet rows:

- `frame_id`: int64
- `time_ps`: float64
- `coordinates`: variable-length `[atoms, 3]` float32 tensor
- `forces`: variable-length `[atoms, 3]` float32 tensor or null
- `rmsd`: float32 or null
- `radius_of_gyration`: float32 or null
- `event_label`: string
- `event_confidence`: float32

Metadata index rows:

- `dataset_name`
- `protein_name`
- `forcefield`
- `max_rmsd`
- `min_radius_of_gyration`
- `tagged_events`
- `hf_repo_link`

## Distributed Prepare Rules

`mddatanet prepare` uses Ray as the distributed execution dependency. Each worker
receives only frame-range arguments, reopens MDAnalysis locally, writes its own
Parquet shard, and returns only a lightweight summary dictionary.

Workers must not return coordinate arrays to the coordinator.

## Scientific Semantics

Labels are operational labels derived from reproducible metrics or explicit
user-provided event intervals. They should not be treated as universal biological
truth without reviewing the event definitions and project metadata.

## Publication

`mddatanet publish` uploads:

- `.mddn_cache/data/`
- `.mddn_cache/metadata_index/`
- `.mddn_cache/dataset_card.md` as `README.md`

to a Hugging Face dataset repository.
