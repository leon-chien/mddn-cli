# Event YAML Reference

Event YAML files turn feature arrays into supervised labels.

Each event writes:

- `event_now`
- `event_future_{H}`
- `event_future_{H}_valid`
- `time_to_event`

`event_future_{H}` is fixed-horizon and run-aware. It is true only if the event
occurs from frame `t` through `t + H` inside the same run. Tail frames without a
full future horizon are marked false in `event_future_{H}_valid`.

## `feature_threshold`

```yaml
events:
  - name: ligand_unbinding
    type: feature_threshold
    feature: ligand_pocket_min_distance
    operator: greater_than
    threshold: 15.0
    horizon_frames: 500
```

Operators:

- `greater_than`
- `greater_equal`
- `less_than`
- `less_equal`
- `equal`
- `not_equal`

## `feature_window`

True when a feature lies inside a closed interval.

```yaml
events:
  - name: alanine_phi_state
    type: feature_window
    feature: phi
    lower_bound: -120.0
    upper_bound: -40.0
    horizon_frames: 100
```

## `feature_bool`

Uses a boolean feature directly.

```yaml
events:
  - name: ligand_contact_formed
    type: feature_bool
    feature: ligand_contact
    horizon_frames: 100
```

## `composite`

Combines multiple threshold conditions.

```yaml
events:
  - name: protein_unfolding
    type: composite
    logic: all
    horizon_frames: 500
    conditions:
      - feature: rmsd_to_native
        operator: greater_than
        threshold: 8.0
      - feature: native_contact_fraction
        operator: less_than
        threshold: 0.4
```

`logic` can be `all` or `any`.

## Scientific Meaning

Events are reproducible operational labels. They should be described as task
definitions, not universal biological truth.
