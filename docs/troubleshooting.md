# Troubleshooting

## `No module named pip`

Your Python environment does not have `pip`.

```bash
python -m ensurepip --upgrade
python -m pip install -e ".[dev]"
```

In Conda environments, `conda install pip` is also fine.

## Invalid Selection

Example:

```text
selection 'resid 42 and name CA' matched 0 atoms
```

Check that the topology contains the residue/atom names you expect. MDDataNet
uses MDAnalysis selection syntax.

## Topology And Trajectory Mismatch

If conversion fails because atom counts do not match, confirm that all
trajectories share the same topology and atom ordering. Multi-run packages
currently require one compatible system.

## Missing Raw Files During Featurization

Current packages store compressed trajectory coordinates by default. If you
created a `features-only`, `--no-coordinates`, or `linked` package,
featurization may need the original raw files recorded in provenance. Restore
those files or rerun with embedded coordinates:

```bash
mddatanet convert ... --data-mode hybrid --storage-profile compressed
```

For very large Hub datasets, use `--storage-profile linked` and make sure
`download.yaml` contains coordinate URLs and checksums.

## Units And PBC

MDDataNet records distances as Angstrom and times as picoseconds when available
through MDAnalysis. Periodic boundary behavior depends on unit-cell information
being present in the trajectory.

## Huge Files

Use unpacked `.mddatanet/` directories during active processing. Packing to zip
is best for sharing or archiving.

For Hub-scale sharing, use either `--storage-profile linked` or:

```bash
mddatanet split-package --input ready.mddatanet.zip --out-labels dataset.labels.mddatanet.zip --out-coordinates dataset.coordinates.zarr.zip
```

## Validation Fails After Manual Edits

Run:

```bash
mddatanet validate package.mddatanet --no-checksums
```

If validation then passes, regenerate checksums by rerunning the relevant
MDDataNet command or repacking the package.
