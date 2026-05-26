# Event Semantics Reference

MDDataNet event labels are reproducible operational task labels.

In the HF-native MVP, event metadata is stored per frame row:

- `event_label`
- `event_confidence`
- metric columns such as `rmsd` and `radius_of_gyration`

One heavy row represents:

```text
frame t
```

Rows preserve frame order. Future window loaders can build `t-W:t -> t:t+H`
views from the published Parquet rows.

## Preset Events

Preset events are threshold rules over frame-aligned metrics:

- `ligand_unbinding`: ligand-pocket minimum distance greater than a threshold.
- `ligand_binding`: ligand-pocket minimum distance less than a threshold.
- `protein_unfolding`: first MVP path uses RMSD or radius of gyration threshold.

Use `--param` to override thresholds and horizons:

```bash
mddatanet analyze \
  scratch/ \
  --preset ligand_unbinding \
  --param distance_threshold=15.0
```

## Scientific Meaning

Events are task definitions, not universal biological truth. Always inspect the
metric, threshold, and horizon before treating a dataset as a benchmark.
