"""Typer command surface for MDDataNet."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from mddatanet.convert import convert_package
from mddatanet.demo import run_ligand_unbinding_demo
from mddatanet.features.compute import featurize_package
from mddatanet.format.dataset_card import write_dataset_card
from mddatanet.format.metadata import read_metadata
from mddatanet.format.provenance import read_provenance
from mddatanet.format.validation import (
    format_inspection,
    format_inspection_json,
    inspect_package,
    validate_package,
)
from mddatanet.hub import export_manifest
from mddatanet.io.checksums import write_checksums
from mddatanet.io.package import pack_package, unpack_package
from mddatanet.io.workspace import PackageWorkspace
from mddatanet.labels.service import label_package
from mddatanet.presets.registry import registry as preset_registry
from mddatanet.splits.service import split_package
from mddatanet.utils.errors import MDDataNetError
from mddatanet.utils.logging import console, print_error, print_step, print_success

app = typer.Typer(
    name="mddatanet",
    help="Convert MD simulations into labeled, ML-ready dataset packages.",
)
presets_app = typer.Typer(help="Inspect built-in event presets.")
app.add_typer(presets_app, name="presets")


@app.command()
def convert(
    topology: Path = typer.Option(..., "--topology", exists=False, help="Topology file."),
    trajectory: list[Path] | None = typer.Option(None, "--trajectory", help="Trajectory file. Repeat for multiple runs."),
    coordinates: Path | None = typer.Option(None, "--coordinates", help="Coordinate file."),
    name: str = typer.Option(..., "--name", help="Dataset name."),
    description: str | None = typer.Option(None, "--description", help="Short dataset description."),
    out: Path = typer.Option(..., "--out", help="Output .mddatanet directory or .mddatanet.zip."),
    stride: int = typer.Option(1, "--stride", min=1),
    start: int | None = typer.Option(None, "--start"),
    stop: int | None = typer.Option(None, "--stop"),
    chunk_size: int = typer.Option(100, "--chunk-size", help="Processing chunk size (frames)."),
    store_positions: bool = typer.Option(False, "--store-positions/--no-store-positions"),
    license: str = typer.Option("unknown", "--license", help="Dataset license."),
    source_url: str | None = typer.Option(None, "--source-url", help="Original source URL."),
    citation: str | None = typer.Option(None, "--citation", help="Citation or DOI."),
    run_id: list[str] | None = typer.Option(None, "--run-id", help="Run ID. Repeat once for each --trajectory."),
    simulation_engine: str | None = typer.Option(None, "--simulation-engine", help="MD engine, e.g. NAMD or GROMACS."),
    force_field: str | None = typer.Option(None, "--force-field", help="Force field name."),
    solvent: str | None = typer.Option(None, "--solvent", help="Solvent description."),
    ensemble: str | None = typer.Option(None, "--ensemble", help="Simulation ensemble."),
    organism: str | None = typer.Option(None, "--organism", help="Organism tag."),
    protein: str | None = typer.Option(None, "--protein", help="Protein target tag."),
    system_type: str | None = typer.Option(None, "--system-type", help="System type tag."),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Create an initial package from raw MD files."""

    try:
        print_step(1, 4, "Loading topology and trajectory...")
        result = convert_package(
            topology=topology,
            trajectory=trajectory,
            coordinates=coordinates,
            name=name,
            description=description,
            out=out,
            run_id=run_id,
            simulation_engine=simulation_engine,
            force_field=force_field,
            solvent=solvent,
            ensemble=ensemble,
            organism=organism,
            protein=protein,
            system_type=system_type,
            stride=stride,
            start=start,
            stop=stop,
            chunk_size=chunk_size,
            store_positions=store_positions,
            license=license,
            source_url=source_url,
            citation=citation,
            overwrite=overwrite,
            command=_command_string(),
        )
        print_step(4, 4, "Package written.")
        print_success(str(result))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def featurize(
    input_path: Path = typer.Option(..., "--input", help="Input package."),
    features: Path = typer.Option(..., "--features", help="Feature YAML."),
    out: Path = typer.Option(..., "--out", help="Output package."),
    chunk_size: int = typer.Option(100, "--chunk-size", help="Processing chunk size (frames)."),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Add trajectory-derived features to a package."""

    try:
        print_step(1, 4, "Loading feature config...")
        result = featurize_package(
            input_path=input_path,
            features_path=features,
            out=out,
            chunk_size=chunk_size,
            overwrite=overwrite,
            command=_command_string(),
        )
        print_step(4, 4, "Features written.")
        print_success(str(result))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def label(
    input_path: Path = typer.Option(..., "--input", help="Input package."),
    out: Path = typer.Option(..., "--out", help="Output package."),
    events: Path | None = typer.Option(None, "--events", help="Custom event YAML."),
    preset: str | None = typer.Option(None, "--preset", help="Built-in preset name."),
    param: list[str] | None = typer.Option(None, "--param", help="Preset parameter override key=value."),
    reference: Path | None = typer.Option(None, "--reference", help="Reference structure for presets."),
    ligand: str | None = typer.Option(None, "--ligand", help="Ligand atom selection."),
    pocket: str | None = typer.Option(None, "--pocket", help="Pocket/protein atom selection."),
    selection_a: str | None = typer.Option(None, "--selection-a", help="Generic selection A."),
    selection_b: str | None = typer.Option(None, "--selection-b", help="Generic selection B."),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Generate event labels from existing feature arrays."""

    try:
        print_step(1, 4, "Resolving events...")
        result = label_package(
            input_path=input_path,
            out=out,
            events_path=events,
            preset=preset,
            preset_args={
                "reference": str(reference) if reference is not None else None,
                "ligand": ligand,
                "pocket": pocket,
                "selection_a": selection_a,
                "selection_b": selection_b,
            },
            param_overrides=_parse_params(param or []),
            overwrite=overwrite,
            command=_command_string(),
        )
        print_step(4, 4, "Labels written.")
        print_success(str(result))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def split(
    input_path: Path = typer.Option(..., "--input", help="Input package."),
    out: Path = typer.Option(..., "--out", help="Output package."),
    strategy: str = typer.Option("temporal", "--strategy", help="temporal, random_window, or trajectory."),
    train: float = typer.Option(0.7, "--train"),
    val: float = typer.Option(0.15, "--val"),
    test: float = typer.Option(0.15, "--test"),
    gap: int = typer.Option(0, "--gap"),
    seed: int | None = typer.Option(None, "--seed"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Create train/validation/test split arrays."""

    try:
        print_step(1, 4, "Creating split arrays...")
        result = split_package(
            input_path=input_path,
            out=out,
            strategy=strategy,
            train=train,
            val=val,
            test=test,
            gap=gap,
            seed=seed,
            overwrite=overwrite,
        )
        print_step(4, 4, "Splits written.")
        print_success(str(result))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def validate(
    package: Path = typer.Argument(..., help="Package directory or .mddatanet.zip."),
    no_checksums: bool = typer.Option(False, "--no-checksums", help="Skip checksum validation."),
) -> None:
    """Validate package correctness."""

    result = validate_package(package, check_checksums=not no_checksums)
    for check in result.checks:
        console.print(f"✓ {check}")
    for warning in result.warnings:
        console.print(f"! {warning}")
    for error in result.errors:
        console.print(f"✗ {error}")
    for suggestion in result.suggestions:
        console.print(f"  → Suggestion: {suggestion}")
    if not result.ok:
        raise typer.Exit(1)
    console.print("Package is valid.")


@app.command()
def inspect(
    input_path: Path = typer.Argument(..., help="Package directory or .mddatanet.zip."),
    features: bool = typer.Option(False, "--features", help="Show detailed features."),
    labels: bool = typer.Option(False, "--labels", help="Show detailed labels."),
    splits: bool = typer.Option(False, "--splits", help="Show detailed splits."),
    json_output: bool = typer.Option(False, "--json", help="Print JSON output."),
) -> None:
    """Print a human-readable package summary."""

    summary = inspect_package(
        input_path,
        include_features=features,
        include_labels=labels,
        include_splits=splits,
    )
    console.print(format_inspection_json(summary) if json_output else format_inspection(summary))


@app.command()
def pack(
    source: Path = typer.Argument(..., help="Unpacked .mddatanet directory."),
    output: Path = typer.Argument(..., help="Output .mddatanet.zip."),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Pack an unpacked package directory."""

    try:
        print_step(1, 2, "Packing package...")
        packed = pack_package(source, output, overwrite=overwrite)
        print_step(2, 2, "Packed output.")
        print_success(str(packed))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def unpack(
    package: Path = typer.Argument(..., help="Input .mddatanet.zip."),
    out: Path = typer.Option(..., "--out", help="Output directory."),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Unpack a package zip."""

    try:
        print_step(1, 2, "Unpacking package...")
        unpacked = unpack_package(package, out, overwrite=overwrite)
        print_step(2, 2, "Unpacked output.")
        print_success(str(unpacked))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def card(
    input_path: Path = typer.Option(..., "--input", help="Input package."),
    out: Path = typer.Option(..., "--out", help="Output package."),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Generate or refresh dataset_card.md."""

    try:
        workspace = PackageWorkspace(input_path, out, overwrite=overwrite)
        with workspace as work_dir:
            metadata = read_metadata(work_dir)
            provenance = read_provenance(work_dir)
            write_dataset_card(work_dir, metadata, provenance)
            write_checksums(work_dir)
            workspace.finalize()
            print_success(str(out))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command("export-manifest")
def export_manifest_command(
    package: Path = typer.Argument(..., help="Input .mddatanet.zip or .mddatanet directory."),
    out: Path = typer.Option(..., "--out", help="Output Hub registry directory."),
    download_url: str | None = typer.Option(None, "--download-url", help="External package download URL."),
    dataset_id: str | None = typer.Option(None, "--dataset-id", help="Hub dataset ID."),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Export Hub-ready metadata registry files."""

    try:
        result = export_manifest(
            package,
            out=out,
            download_url=download_url,
            dataset_id=dataset_id,
            overwrite=overwrite,
        )
        print_success(str(result))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def demo(
    name: str = typer.Argument("ligand_unbinding", help="Demo name."),
    out_dir: Path = typer.Option(Path("outputs"), "--out-dir", help="Directory for generated demo output."),
    overwrite: bool = typer.Option(True, "--overwrite/--no-overwrite", help="Overwrite existing demo output."),
) -> None:
    """Run a complete demonstration pipeline."""

    if name == "alanine":
        console.print("The alanine demo is not implemented yet; running ligand_unbinding instead.")
        name = "ligand_unbinding"
    if name != "ligand_unbinding":
        _fail(f"Unknown demo: {name}")
    try:
        run_ligand_unbinding_demo(output_dir=out_dir, overwrite=overwrite)
    except MDDataNetError as exc:
        _fail(exc.display_message())


@presets_app.command("list")
def presets_list() -> None:
    """List built-in event presets."""

    categories = preset_registry.categories()
    if not categories:
        console.print("No built-in presets are currently available.")
        return
    for category, names in categories.items():
        console.print(f"{category}:")
        for name in names:
            console.print(f"  {name}")


@presets_app.command("show")
def presets_show(name: str) -> None:
    """Show exact preset definition."""

    try:
        console.print_json(data=preset_registry.get(name))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command("export-schema")
def export_schema(
    out_dir: Path = typer.Option(Path("schemas"), "--out-dir", help="Directory to write schemas."),
) -> None:
    """Export package format JSON Schemas."""

    import json
    from mddatanet.format.schema import Metadata, Provenance, FeatureConfig, EventConfig, SplitManifest
    
    out_dir.mkdir(parents=True, exist_ok=True)
    models = {
        "metadata": Metadata,
        "provenance": Provenance,
        "feature_config": FeatureConfig,
        "events": EventConfig,
        "splits": SplitManifest,
    }
    
    for name, model in models.items():
        schema = model.model_json_schema()
        path = out_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        console.print(f"Exported {path}")


@presets_app.command("explain")
def presets_explain(name: str) -> None:
    """Explain a preset scientifically and computationally."""

    try:
        preset = preset_registry.get(name)
    except MDDataNetError as exc:
        _fail(exc.display_message())
    console.print(preset.get("description", f"No explanation available for {name}."))


def _parse_params(params: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for raw in params:
        if "=" not in raw:
            raise typer.BadParameter(f"--param must be key=value, got: {raw}")
        key, value = raw.split("=", 1)
        parsed[key] = _coerce_param(value)
    return parsed


def _coerce_param(value: str) -> object:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." not in value:
            return int(value)
        return float(value)
    except ValueError:
        return value


def _command_string() -> str:
    return " ".join(sys.argv)


def _fail(message: str) -> None:
    print_error(message)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
