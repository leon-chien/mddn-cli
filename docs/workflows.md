# Example Workflows

## Preset Labeling

```bash
mddatanet convert \
  --topology system.pdb \
  --trajectory traj.xtc \
  --name ligand_run \
  --system-type protein_ligand \
  --out ligand_raw.mddatanet

mddatanet label \
  --input ligand_raw.mddatanet \
  --preset ligand_unbinding \
  --ligand "resname LIG" \
  --pocket "protein" \
  --out ligand_labeled.mddatanet

mddatanet split --input ligand_labeled.mddatanet --strategy temporal --gap 100 --out ligand_ready.mddatanet.zip
mddatanet validate ligand_ready.mddatanet.zip
mddatanet inspect ligand_ready.mddatanet.zip --features --labels --splits
```

## Custom Features And Events

`features.yaml`:

```yaml
features:
  - name: ligand_pocket_min_distance
    type: min_distance
    selection_a: "resname LIG"
    selection_b: "protein"
    units: angstrom
```

`events.yaml`:

```yaml
events:
  - name: ligand_unbinding
    type: feature_threshold
    feature: ligand_pocket_min_distance
    operator: greater_than
    threshold: 15.0
    horizon_frames: 500
```

Run:

```bash
mddatanet featurize --input raw.mddatanet --features features.yaml --out features.mddatanet
mddatanet label --input features.mddatanet --events events.yaml --out labeled.mddatanet
```

## Multi-Run Package

```bash
mddatanet convert \
  --topology system.psf \
  --coordinates system.pdb \
  --trajectory run1.dcd \
  --trajectory run2.dcd \
  --run-id run1 \
  --run-id run2 \
  --name replicate_dataset \
  --out replicate_dataset.mddatanet

mddatanet split --input replicate_dataset.mddatanet --strategy trajectory --out replicate_ready.mddatanet
```

## Hub Manifest Export

```bash
mddatanet validate ready.mddatanet.zip
mddatanet export-manifest ready.mddatanet.zip --out hub_dataset_dir
```

After uploading the large package to external storage:

```bash
mddatanet export-manifest ready.mddatanet.zip \
  --out hub_dataset_dir \
  --download-url https://example.org/ready.mddatanet.zip \
  --overwrite
```
