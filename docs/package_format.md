# Workspace And Data Format

MDDataNet no longer uses `.mddatanet.zip` as the canonical output. The local
format is a Hugging Face staging workspace.

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

During `prepare`, `.mddn_cache/data/` can contain `shard-*.parquet` files. The
`package` command replaces them with split files.

## Heavy Tensor Rows

Each row represents one frame:

- `frame_id`
- `time_ps`
- `coordinates`: variable-length `[atoms, 3]` float32 coordinates
- `forces`: variable-length `[atoms, 3]` float32 forces, or null
- `rmsd`
- `radius_of_gyration`
- `event_label`
- `event_confidence`

## Metadata Index

The `metadata_index` split is intentionally small:

- `dataset_name`
- `protein_name`
- `forcefield`
- `max_rmsd`
- `min_radius_of_gyration`
- `tagged_events`
- `hf_repo_link`

This lets users inspect and filter dataset metadata before streaming heavy
coordinate tensors.
