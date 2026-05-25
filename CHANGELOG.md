# Changelog

All notable changes to MDDataNet will be documented here.

MDDataNet follows semantic versioning for the Python package and CLI. The
package format version is tracked separately in generated package metadata.

## 0.1.0 - Unreleased

### Added

- Typer CLI with `convert`, `featurize`, `label`, `analyze`, `split`,
  `validate`, `inspect`, `pack`, `unpack`, `split-package`, `card`, `demo`,
  `export-manifest`, `export-schema`, and preset inspection/validation
  commands.
- MDAnalysis-backed conversion for raw topology/trajectory workflows.
- Chunked Zarr package storage with metadata, provenance, checksums, dataset
  cards, and optional stored positions.
- Feature computation for distances, contacts, dihedrals, RMSD, radius of
  gyration, and native contact fraction.
- Custom event YAML and built-in presets including ligand unbinding.
- Fixed-horizon future labels, valid masks, time-to-event labels, split
  generation, and descriptive label metrics.
- Runtime-generated ligand unbinding demo.
- Hub-schema manifest export for future registry workflows, including
  Hub-shaped `metadata.json`, `manifest.json`, `download.yaml`,
  `checksums.json`, task metadata, named assets, descriptive metrics, and
  optional `citation.bib`.
- GitHub Actions CI and manual TestPyPI workflow.

### Notes

- Hub upload, Hub PR submission, and Hub website functionality are intentionally
  out of scope for this release.
