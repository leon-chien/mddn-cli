# MDDataNet

MDDataNet CLI converts molecular dynamics simulations into standardized,
labeled, machine-learning-ready dataset packages.

The CLI reads raw topology and trajectory files, extracts trajectory-derived
features, applies reproducible event definitions, generates current-event and
future-event labels, creates train/validation/test splits, tracks provenance,
and packages everything into a `.mddatanet.zip` file.

This repository is in an active build phase. The current implementation
can convert large MDAnalysis-readable trajectories into MDDataNet
packages with chunking and progress reporting, compute trajectory features
with PBC awareness, generate fixed-horizon event labels with validity masks,
create splits with leakage protection, validate packages with repair suggestions, 
export Hub-ready manifests, and export JSON Schemas for interoperability.

Example datasets and user config templates are intentionally deferred. 
The demo generates tiny synthetic data at runtime.

## Quickstart

```bash
python -m pip install -e ".[dev]"
mddatanet demo
mddatanet inspect outputs/ligand_unbinding_demo.mddatanet.zip --labels
mddatanet validate outputs/ligand_unbinding_demo.mddatanet.zip
mddatanet export-schema --out-dir schemas
```

The demo creates a small synthetic protein-ligand trajectory, applies the
`ligand_unbinding` preset, generates future-event labels, creates splits,
validates the package, and writes:

```text
outputs/ligand_unbinding_demo.mddatanet.zip
```

## What MDDataNet Is Not

MDDataNet is not an MD simulation engine. It does not run NAMD, GROMACS, AMBER,
OpenMM, or WESTPA. It does not host public datasets yet, train universal ML
models, manually annotate events, or replace MDAnalysis, MDTraj, MDDB, MDRepo,
ATLAS, or mdCATH.

It sits above trajectory readers and below the future MDDataNet Hub.

## Intended CLI

```bash
# Convert with explicit chunking for large files
mddatanet convert \
  --topology system.psf \
  --coordinates system.pdb \
  --trajectory run.dcd \
  --name kinase_run1 \
  --system-type protein_ligand \
  --simulation-engine NAMD \
  --force-field CHARMM36 \
  --out kinase.mddatanet \
  --chunk-size 1000

# Featurize with automatic PBC handling (if box info exists)
mddatanet featurize --input kinase.mddatanet --features features.yaml --out kinase_feat.mddatanet

# Label with scientific presets
mddatanet label --input kinase_feat.mddatanet --preset ligand_unbinding --ligand "resname LIG" --pocket "protein" --out kinase_labeled.mddatanet

# Split with leakage protection gaps
mddatanet split --input kinase_labeled.mddatanet --strategy temporal --gap 100 --out kinase_ready.mddatanet

# Validate and get repair suggestions
mddatanet validate kinase_ready.mddatanet

# Export Schemas for tool integration
mddatanet export-schema --out-dir schemas
```

Multiple replicate trajectories can be packaged together with repeated
`--trajectory` and `--run-id` options:

```bash
mddatanet convert --topology system.psf --trajectory run1.dcd --trajectory run2.dcd --run-id run1 --run-id run2 --name kinase_replicates --out kinase_replicates.mddatanet.zip
```

## Scientific Labeling Best Practices

MDDataNet labels are reproducible operational labels. They are meant to define
clear ML tasks, not universal biological truth.

- Prefer event rules that can be recomputed from stored feature arrays.
- Record thresholds, horizons, selections, units, and preset parameters.
- Use `event_future_H_valid_mask` when training future-event models; tail frames
  without a full horizon are not valid training labels.
- Use temporal gaps or trajectory-level splits to reduce leakage.
- Inspect `baseline_metrics.json` before publishing a dataset. It contains
  descriptive dataset metrics such as event duration and transition rates, not
  model performance.

## Machine Learning Integration

MDDataNet packages are designed for easy ingestion into ML pipelines. 
You can use the built-in windowing utilities to generate samples:

```python
from pathlib import Path
from mddatanet.utils.windows import iter_windows

package = Path("kinase_ready.mddatanet")
for sample in iter_windows(package, window_size=50, label_name="ligand_unbinding/event_future_500"):
    X = sample["features"] # shape (50, num_features)
    y = sample["label"]    # future label at end of window; invalid masks are skipped
    # train model...
```

## Package Format

An unpacked package is a `.mddatanet/` directory containing:

```text
dataset.zarr/
metadata.json
provenance.json
checksums.json
label_statistics.json
baseline_metrics.json
dataset_card.md
README.md
LICENSE
```

The Zarr store uses these root groups:

```text
arrays/
features/
labels/
splits/
index/
```

Large arrays should always be written incrementally with explicit chunking and
compression. Raw positions are optional and should not be stored unless the user
requests them.

For very large trajectories, prefer working with unpacked `.mddatanet/`
directories during active processing and create `.mddatanet.zip` archives when
you are ready to share or export.

## Hub Registry Workflow

The future MDDataNet Hub should be a curated metadata registry, not a raw file
dump. Use:

```bash
mddatanet export-manifest my_dataset.mddatanet.zip --out hub_dataset_dir
```

This writes Hub-ready `metadata.json`, `dataset_card.md`, `checksums.json`,
`manifest.json`, `download.yaml`, optional `citation.bib`, and optional metrics
files. The large `.mddatanet.zip` should live on Hugging Face Datasets, Zenodo,
S3/R2, GCS, or institutional storage.

If the package has already been uploaded externally, include its URL:

```bash
mddatanet export-manifest my_dataset.mddatanet.zip --out hub_dataset_dir --download-url https://example.org/my_dataset.mddatanet.zip
```

Use `--verify-download` only when the URL is reachable and should be checked
during manifest export.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
ruff check src tests
python -m build
```

The source of truth for the full build is
`docs/MDDataNet_CLI_Full_Build_Specification.md`.
