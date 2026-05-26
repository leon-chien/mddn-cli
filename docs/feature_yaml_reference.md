# Feature And Metric Reference

The Hugging Face-native CLI centers on frame-aligned metric vectors rather than
standalone feature YAML files.

## Built-In Metric Sources

`mddatanet analyze --preset ...` currently computes metrics for:

- ligand binding/unbinding minimum distance;
- protein radius of gyration;
- RMSD when a reference structure is supplied.

These metrics are written back into per-frame Parquet columns such as `rmsd`,
`radius_of_gyration`, `event_label`, and `event_confidence`.

## Custom Metrics

Custom Python metric scripts are supported:

```python
def my_metric(positions, metadata):
    return positions[:, :, 0].max(axis=1)
```

```bash
mddatanet analyze \
  local_scratch/ \
  --custom-script metrics.py \
  --func my_metric
```

The function must return one numeric scalar per frame.

## Selection Syntax

The MVP supports simple staging selections in presets:

- `protein`
- `resname LIG`
- `name CA`

Raw preparation supports full MDAnalysis syntax through `--atom-selection`.
