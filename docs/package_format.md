# Package Format

MDDataNet packages are either unpacked `.mddatanet/` directories or packed
`.mddatanet.zip` archives.

```text
dataset.mddatanet/
  dataset.zarr/
    trajectory/
      positions
      box_vectors
      frame_indices
      source_frame_indices
      frame_times
      trajectory_ids
      run_ids
    topology/
      atom_names
      atom_types
      residue_names
      residue_ids
      chain_ids
      masses
      charges
      bonds
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

`trajectory/` contains standardized frame data:

- `frame_indices`
- `source_frame_indices`
- `frame_times`
- `trajectory_ids`
- `run_ids`
- `positions`, included for `compressed` and `full` packages unless disabled
- `box_vectors`, unit-cell data when available

`topology/` contains atom-level topology metadata:

- `atom_names`
- `atom_types`
- `residue_names`
- `residue_ids`
- `chain_ids`
- `masses`
- `charges`
- `bonds`

Legacy packages may contain the older `arrays/` layout. Current writes use
`trajectory/` and `topology/`.

`features/` contains one array per feature.

`labels/{event}/` contains:

- `event_now`
- `event_future_{H}`
- `event_future_{H}_valid`
- `time_to_event`

`splits/` contains `train`, `val`, and `test` index arrays.

`index/` contains feature and event name indexes.

## Metadata And Provenance

`metadata.json` describes dataset identity, data mode, storage profile,
coordinate storage, sampling, trajectory summary, system metadata, source
metadata, features, labels, splits, license, and tags.

`provenance.json` records commands, source files, checksums, run records, frame
slicing, and whether positions were stored.

## Storage Profiles

- `compressed`: default. Stores coordinates as chunked compressed Zarr,
  normally `float32` with zstd compression.
- `full`: stores coordinates with maximum precision requested by the user,
  still chunked and compressed for practical access.
- `linked`: omits embedded coordinates and writes `download.yaml` with external
  coordinate/topology URLs and checksums.

Use `split-package` to separate a coordinate archive from a lightweight labels
package for large Hub-scale datasets.

## Metrics

`label_statistics.json` and `baseline_metrics.json` contain descriptive dataset
metrics such as positive rates, event durations, transition counts, and
time-to-event summaries. They are not model performance metrics.

## Checksums

`checksums.json` tracks package file integrity. `mddatanet validate` verifies
checksums by default.
