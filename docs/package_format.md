# Package Format

MDDataNet packages are either unpacked `.mddatanet/` directories or packed
`.mddatanet.zip` archives.

```text
dataset.mddatanet/
  dataset.zarr/
    arrays/
    features/
    labels/
    splits/
    index/
  metadata.json
  provenance.json
  feature_config.yaml
  events.yaml
  presets_used.json
  splits.json
  checksums.json
  label_statistics.json
  baseline_metrics.json
  dataset_card.md
  README.md
  LICENSE
```

Not every file exists at every stage. A raw converted package may not have
features, labels, or splits yet.

## Zarr Arrays

`arrays/` contains frame and atom metadata:

- `frame_indices`
- `source_frame_indices`
- `frame_times`
- `trajectory_ids`
- `run_ids`
- `atom_names`
- `residue_ids`
- `residue_names`
- `positions`, optional and chunked
- `dimensions`, optional unit-cell data

`features/` contains one array per feature.

`labels/{event}/` contains:

- `event_now`
- `event_future_{H}`
- `event_future_{H}_valid_mask`
- `time_to_event`

`splits/` contains `train`, `val`, and `test` index arrays.

`index/` contains feature and event name indexes.

## Metadata And Provenance

`metadata.json` describes dataset identity, system metadata, source metadata,
features, labels, splits, license, and tags.

`provenance.json` records commands, source files, checksums, run records, frame
slicing, and whether positions were stored.

## Metrics

`label_statistics.json` and `baseline_metrics.json` contain descriptive dataset
metrics such as positive rates, event durations, transition counts, and
time-to-event summaries. They are not model performance metrics.

## Checksums

`checksums.json` tracks package file integrity. `mddatanet validate` verifies
checksums by default.
