# Troubleshooting

## `No module named pip`

Install pip inside the active Conda environment:

```bash
conda install pip
```

Then reinstall:

```bash
python -m pip install -e ".[dev]"
```

## Ray Cannot Start

`mddatanet prepare` requires Ray. Install dependencies with:

```bash
python -m pip install -e ".[dev]"
```

On restricted macOS sandboxes, Ray process inspection can be blocked. MDDataNet
falls back to an in-process worker path only for that permission failure so tests
and demos can still run. Normal user environments should use Ray workers.

## Invalid Selection

Use MDAnalysis selection syntax. For the MVP, common selections include:

```text
protein
resname LIG
name CA
```

## Forces Are Missing

Many trajectory formats do not store forces. MDDataNet records `has_forces:
false` and writes null force tensors. It does not synthesize zeros.

## Old Commands Are Gone

The public CLI no longer exposes `convert`, `push-to-hub`, `split`, `pack`,
`unpack`, or `export-manifest`. Use:

```text
init -> prepare -> analyze/tag -> package -> validate -> publish
```
