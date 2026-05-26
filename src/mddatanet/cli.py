"""Typer command surface for the Hugging Face-native MDDataNet CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from mddatanet.demo import run_ligand_unbinding_demo
from mddatanet.hf.workspace import (
    analyze_workspace,
    benchmark_registry,
    init_workspace,
    inspect_source,
    load_hf_dataset,
    package_workspace,
    prepare_workspace,
    publish_workspace,
    tag_workspace,
    validate_workspace,
    workspace_summary,
)
from mddatanet.presets.registry import registry as preset_registry
from mddatanet.utils.errors import MDDataNetError
from mddatanet.utils.logging import console, print_error, print_success
from mddatanet.utils.yaml import read_yaml

app = typer.Typer(
    name="mddatanet",
    help="Prepare MD trajectories as Hugging Face-native molecular ML datasets.",
)
presets_app = typer.Typer(help="Inspect built-in event presets.")
app.add_typer(presets_app, name="presets")


@app.command()
def init(
    project_root: Path = typer.Argument(Path("."), help="Project directory to initialize."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace an existing mddatanet.yaml."),
) -> None:
    """Create an MDDataNet project descriptor."""

    try:
        path = init_workspace(project_root, overwrite=overwrite)
        print_success(str(path))
        _next("edit mddatanet.yaml, then run `mddatanet inspect --topology system.pdb --trajectory run.dcd`.")
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def inspect(
    project_root: Path | None = typer.Argument(None, help="Prepared project directory to summarize."),
    topology: Path | None = typer.Option(None, "--topology", exists=False, help="Topology file for source inspection."),
    trajectory: list[Path] | None = typer.Option(None, "--trajectory", help="Trajectory file. Repeat for multiple runs."),
    coordinates: Path | None = typer.Option(None, "--coordinates", help="Optional coordinate file."),
) -> None:
    """Inspect source files or a prepared MDDataNet workspace."""

    try:
        if topology is not None:
            summary = inspect_source(topology=topology, trajectory=trajectory, coordinates=coordinates)
        else:
            summary = workspace_summary(project_root or Path("."))
        _print_mapping(summary)
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def prepare(
    project_root: Path = typer.Argument(Path("."), help="Project directory with mddatanet.yaml."),
    topology: Path = typer.Option(..., "--topology", exists=False, help="Topology file."),
    trajectory: list[Path] | None = typer.Option(None, "--trajectory", help="Trajectory file. Repeat for multiple runs."),
    coordinates: Path | None = typer.Option(None, "--coordinates", help="Optional coordinate file."),
    chunk_size: int = typer.Option(5000, "--chunk-size", min=1, help="Frames per Ray worker shard."),
    keep_solvent: bool = typer.Option(False, "--keep-solvent", help="Keep water/solvent atoms."),
    atom_selection: str | None = typer.Option(None, "--atom-selection", help="MDAnalysis atom selection override."),
    stride: int = typer.Option(1, "--stride", min=1, help="Store every Nth frame."),
    start: int | None = typer.Option(None, "--start", help="First source frame."),
    stop: int | None = typer.Option(None, "--stop", help="Stop source frame, exclusive."),
    ray_address: str | None = typer.Option(None, "--ray-address", help="Existing Ray cluster address."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace .mddn_cache."),
) -> None:
    """Convert raw MD files into Ray-written per-frame Parquet shards."""

    try:
        cache = prepare_workspace(
            project_root=project_root,
            topology=topology,
            trajectory=trajectory,
            coordinates=coordinates,
            chunk_size=chunk_size,
            keep_solvent=keep_solvent,
            atom_selection=atom_selection,
            stride=stride,
            start=start,
            stop=stop,
            ray_address=ray_address,
            overwrite=overwrite,
        )
        print_success(str(cache))
        _next(f"run `mddatanet analyze {project_root} --preset ligand_unbinding --ligand 'resname LIG' --pocket protein`.")
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def analyze(
    project_root: Path = typer.Argument(Path("."), help="Prepared project directory."),
    preset: str | None = typer.Option(None, "--preset", help="Built-in preset name."),
    custom_script: Path | None = typer.Option(None, "--custom-script", help="Python script with a custom metric function."),
    func: str | None = typer.Option(None, "--func", help="Custom metric function name."),
    primary_metric: str | None = typer.Option(None, "--primary-metric", help="Primary metric column name."),
    param: list[str] | None = typer.Option(None, "--param", help="Metric/event override key=value."),
    ligand: str | None = typer.Option(None, "--ligand", help="Ligand atom selection."),
    pocket: str | None = typer.Option(None, "--pocket", help="Pocket/protein atom selection."),
) -> None:
    """Calculate frame-aligned metrics and operational event labels."""

    try:
        cache = analyze_workspace(
            project_root=project_root,
            preset=preset,
            custom_script=custom_script,
            func=func,
            primary_metric=primary_metric,
            ligand=ligand,
            pocket=pocket,
            param_overrides=_parse_params(param or []),
        )
        print_success(str(cache))
        _next(f"run `mddatanet package {project_root}` or add interval labels with `mddatanet tag`.")
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def tag(
    project_root: Path = typer.Argument(Path("."), help="Prepared project directory."),
    event: str = typer.Option(..., "--event", help="Allowed event name from mddatanet.yaml."),
    start_frame: int = typer.Option(..., "--start-frame", min=0),
    end_frame: int = typer.Option(..., "--end-frame", min=1),
    confidence: float = typer.Option(1.0, "--confidence"),
) -> None:
    """Inject an explicit biological event interval."""

    try:
        cache = tag_workspace(
            project_root=project_root,
            event=event,
            start_frame=start_frame,
            end_frame=end_frame,
            confidence=confidence,
        )
        print_success(str(cache))
        _next(f"run `mddatanet package {project_root}`.")
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def package(
    project_root: Path = typer.Argument(Path("."), help="Project directory to package."),
    train_frac: float = typer.Option(0.8, "--train-frac"),
    validation_frac: float = typer.Option(0.1, "--validation-frac"),
    test_frac: float = typer.Option(0.1, "--test-frac"),
    hf_repo_link: str = typer.Option("", "--hf-repo-link", help="Repo link to place in metadata_index."),
) -> None:
    """Finalize official train/validation/test and metadata_index Parquet splits."""

    try:
        cache = package_workspace(
            project_root=project_root,
            train_frac=train_frac,
            validation_frac=validation_frac,
            test_frac=test_frac,
            hf_repo_link=hf_repo_link,
        )
        print_success(str(cache))
        _next(f"run `mddatanet validate {project_root}` then `mddatanet publish {project_root} --repo-id USER/DATASET`.")
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def validate(project_root: Path = typer.Argument(Path("."), help="Project directory to validate.")) -> None:
    """Validate the MDDataNet workspace and write validation_report.json."""

    errors = validate_workspace(project_root)
    if errors:
        for error in errors:
            console.print(f"✗ {error}")
        raise typer.Exit(1)
    console.print("MDDataNet workspace is valid.")


@app.command()
def publish(
    project_root: Path = typer.Argument(Path("."), help="Packaged project directory."),
    repo_id: str = typer.Option(..., "--repo-id", help="Hugging Face dataset repo ID."),
    private: bool = typer.Option(False, "--private", help="Create or update a private dataset repo."),
    token: str | None = typer.Option(None, "--token", help="Hugging Face token; defaults to local login."),
    dry_run_out: Path | None = typer.Option(None, "--dry-run-out", help="Copy upload files locally instead of uploading."),
) -> None:
    """Publish finalized Parquet assets to Hugging Face."""

    try:
        result = publish_workspace(
            project_root=project_root,
            repo_id=repo_id,
            private=private,
            token=token,
            dry_run_out=dry_run_out,
        )
        print_success(str(result))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def load(
    repo_id: str = typer.Argument(..., help="Hugging Face dataset repo ID."),
    split: str = typer.Option("train", "--split"),
    streaming: bool = typer.Option(True, "--streaming/--no-streaming"),
) -> None:
    """Load a Hugging Face dataset through datasets.load_dataset."""

    try:
        dataset = load_hf_dataset(repo_id, split=split, streaming=streaming)
        console.print(dataset)
    except MDDataNetError as exc:
        _fail(exc.display_message())


@app.command()
def benchmark(
    name: str | None = typer.Argument(None, help="Benchmark name to show."),
    load_dataset_flag: bool = typer.Option(False, "--load", help="Load the benchmark with datasets."),
    split: str = typer.Option("train", "--split"),
) -> None:
    """List or load pinned MDDataNet benchmark repositories."""

    benchmarks = benchmark_registry()
    if name is None:
        for item in benchmarks:
            console.print(f"{item['name']}: {item['repo_id']} ({item['task']})")
        return
    matches = [item for item in benchmarks if item["name"] == name]
    if not matches:
        _fail(f"Unknown benchmark: {name}")
    item = matches[0]
    if load_dataset_flag:
        dataset = load_hf_dataset(item["repo_id"], split=split, streaming=True)
        console.print(dataset)
    else:
        _print_mapping(item)


@app.command()
def demo(
    name: str = typer.Argument("ligand_unbinding", help="Demo name."),
    out_dir: Path = typer.Option(Path("outputs"), "--out-dir", help="Directory for generated demo output."),
    overwrite: bool = typer.Option(True, "--overwrite/--no-overwrite", help="Overwrite existing demo output."),
) -> None:
    """Run a generated HF-native ligand-unbinding demo."""

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
    for category, names in categories.items():
        console.print(f"{category}:")
        for name in names:
            console.print(f"  {name}")


@presets_app.command("show")
def presets_show(name: str) -> None:
    """Show exact preset definition."""

    try:
        import yaml

        console.print(yaml.safe_dump(preset_registry.get(name), sort_keys=False))
    except MDDataNetError as exc:
        _fail(exc.display_message())


@presets_app.command("validate-yaml")
def presets_validate_yaml(preset_file: Path) -> None:
    """Validate a user preset YAML file."""

    try:
        from mddatanet.presets.resolver import validate_preset_definition

        validate_preset_definition(read_yaml(preset_file))
        print_success(f"{preset_file} is a valid MDDataNet preset YAML.")
    except MDDataNetError as exc:
        _fail(exc.display_message())


@presets_app.command("explain")
def presets_explain(name: str) -> None:
    """Explain a preset scientifically and computationally."""

    try:
        preset = preset_registry.get(name)
    except MDDataNetError as exc:
        _fail(exc.display_message())
    console.print(preset.get("description", f"No explanation available for {name}."))


def _print_mapping(data: dict[str, object]) -> None:
    for key, value in data.items():
        console.print(f"{key}: {value}")


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


def _next(message: str) -> None:
    console.print(f"What's next? {message}")


def _fail(message: str) -> None:
    print_error(message)
    raise typer.Exit(1)


def _command_string() -> str:
    return " ".join(sys.argv)


if __name__ == "__main__":
    app()
