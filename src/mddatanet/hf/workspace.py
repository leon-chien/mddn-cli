"""Workspace-first Hugging Face pipeline for MDDataNet."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from mddatanet import __version__
from mddatanet.hf.schema import heavy_tensor_schema, metadata_index_schema, pyarrow_module
from mddatanet.io.loaders import load_universe
from mddatanet.utils.errors import DependencyError, FeatureError, PackageError, SelectionError, ValidationError
from mddatanet.utils.yaml import read_yaml

CACHE_DIRNAME = ".mddn_cache"
PROJECT_FILE = "mddatanet.yaml"
MANIFEST_FILE = "mddatanet.json"
VALIDATION_REPORT = "validation_report.json"
DATA_DIR = "data"
INDEX_DIR = "metadata_index"


def init_workspace(project_root: Path, *, overwrite: bool = False) -> Path:
    """Create a commented MDDataNet project descriptor."""

    project_root = Path(project_root)
    project_root.mkdir(parents=True, exist_ok=True)
    path = project_root / PROJECT_FILE
    if path.exists() and not overwrite:
        raise PackageError(
            f"{PROJECT_FILE} already exists: {path}",
            suggestion="Pass --overwrite only if you want to replace the project descriptor.",
        )
    path.write_text(_project_template(), encoding="utf-8")
    return path


def inspect_source(
    *,
    topology: Path,
    trajectory: Sequence[Path] | None = None,
    coordinates: Path | None = None,
) -> dict[str, Any]:
    """Return a fast diagnostic summary for source MD files."""

    universe = load_universe(topology, coordinates=coordinates, trajectory=(trajectory or [None])[0])
    return {
        "topology": str(Path(topology)),
        "trajectories": [str(path) for path in (trajectory or [])],
        "reader": universe.trajectory.__class__.__name__,
        "frames": int(len(universe.trajectory)),
        "atoms": int(universe.atoms.n_atoms),
        "timestep_ps": _safe_float(getattr(universe.trajectory, "dt", None)),
        "forces_available": _universe_forces_available(universe),
        "candidate_selections": _candidate_selections(universe),
    }


def prepare_workspace(
    *,
    project_root: Path,
    topology: Path,
    trajectory: Sequence[Path] | None = None,
    coordinates: Path | None = None,
    chunk_size: int = 5000,
    keep_solvent: bool = False,
    atom_selection: str | None = None,
    stride: int = 1,
    start: int | None = None,
    stop: int | None = None,
    ray_address: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Use Ray workers to write frame shards directly to local Parquet."""

    ray = _ray_module()
    project_root = Path(project_root)
    config = read_project_config(project_root)
    cache = project_root / CACHE_DIRNAME
    data_dir = cache / DATA_DIR
    if cache.exists() and overwrite:
        shutil.rmtree(cache)
    data_dir.mkdir(parents=True, exist_ok=True)
    if any(data_dir.glob("*.parquet")) and not overwrite:
        raise PackageError(f"Prepared Parquet files already exist in {data_dir}")
    if chunk_size < 1:
        raise PackageError("--chunk-size must be >= 1")
    if stride < 1:
        raise PackageError("--stride must be >= 1")

    trajectories = [Path(path) for path in (trajectory or [])] or [None]
    selection = atom_selection or ("all" if keep_solvent else "not solvent")
    use_ray = True
    try:
        # Ray's uv runtime hook can inspect parent processes with sysctl on macOS;
        # the Codex sandbox blocks that call, so disable it before local init.
        os.environ["RAY_ENABLE_UV_RUN_RUNTIME_ENV"] = "0"
        try:
            import ray._private.ray_constants as ray_constants

            ray_constants.RAY_ENABLE_UV_RUN_RUNTIME_ENV = False
        except Exception:
            pass
        ray.init(
            address=ray_address,
            ignore_reinit_error=True,
            include_dashboard=False,
            _skip_env_hook=True,
        )
        remote_worker = ray.remote(_prepare_chunk_worker)
    except PermissionError:
        use_ray = False
        remote_worker = None
    tasks = []
    source_total = 0
    for run_index, traj_path in enumerate(trajectories):
        universe = load_universe(topology, coordinates=coordinates, trajectory=traj_path)
        frame_indices = _frame_slice(len(universe.trajectory), start=start, stop=stop, stride=stride)
        if not frame_indices:
            raise PackageError("Frame slice selected zero frames.")
        source_total += len(universe.trajectory)
        for shard_index, chunk in enumerate(_chunks(frame_indices, chunk_size)):
            out_path = data_dir / f"shard-run{run_index:03d}-{shard_index:05d}.parquet"
            args = (
                str(topology),
                None if coordinates is None else str(coordinates),
                None if traj_path is None else str(traj_path),
                chunk,
                str(out_path),
                selection,
                run_index,
                run_index,
            )
            if use_ray:
                tasks.append(
                    remote_worker.remote(  # type: ignore[union-attr]
                        *args,
                    )
                )
            else:
                tasks.append(_prepare_chunk_worker(*args))
    summaries = list(ray.get(tasks)) if use_ray else list(tasks)
    summaries.sort(key=lambda item: (item["run_index"], item["start_frame"]))
    if not summaries:
        raise PackageError("No worker shards were produced.")

    atom_counts = {int(item["num_atoms_selected"]) for item in summaries}
    if len(atom_counts) != 1:
        raise PackageError("Prepared shards have incompatible atom counts.")
    frames = int(sum(int(item["num_rows"]) for item in summaries))
    timestep_ps = _first_not_none(item.get("timestep_ps") for item in summaries)
    manifest = {
        "mddatanet_version": __version__,
        "format": "mddatanet_hf_workspace",
        "dataset_name": str(config.get("dataset_name") or project_root.name),
        "total_frames": frames,
        "source_frame_count": source_total,
        "num_atoms_selected": int(next(iter(atom_counts))),
        "atom_selection_string": selection,
        "has_forces": bool(all(item.get("has_forces") for item in summaries)),
        "time_stride_ps": timestep_ps,
        "total_duration_ns": None if timestep_ps is None else float(frames * timestep_ps / 1000.0),
        "project": config,
        "topology": str(Path(topology).absolute()),
        "coordinates": None if coordinates is None else str(Path(coordinates).absolute()),
        "trajectories": [None if path is None else str(Path(path).absolute()) for path in trajectories],
        "shards": summaries,
        "splits": None,
        "analysis": {"metrics": [], "tagged_events": []},
    }
    _write_json(cache / MANIFEST_FILE, manifest)
    return cache


def analyze_workspace(
    *,
    project_root: Path,
    preset: str | None = None,
    custom_script: Path | None = None,
    func: str | None = None,
    primary_metric: str | None = None,
    ligand: str | None = None,
    pocket: str | None = None,
    param_overrides: dict[str, Any] | None = None,
) -> Path:
    """Append frame-aligned metrics and event tags to prepared Parquet shards."""

    project_root = Path(project_root)
    manifest = read_manifest(project_root)
    data_files = _data_files(project_root)
    if not data_files:
        raise PackageError("No prepared Parquet shards found. Run `mddatanet prepare` first.")
    params = param_overrides or {}
    metric_name = primary_metric or "radius_of_gyration"
    event_name = preset or metric_name
    threshold = params.get("threshold")
    operator = str(params.get("operator", "greater_than"))
    if preset in {"ligand_unbinding", "ligand_binding"}:
        metric_name = "ligand_pocket_min_distance"
        event_name = preset
        threshold = float(params.get("distance_threshold", 15.0 if preset == "ligand_unbinding" else 4.5))
        operator = "greater_than" if preset == "ligand_unbinding" else "less_than"
    elif preset == "protein_unfolding":
        metric_name = "radius_of_gyration"
        event_name = preset
        threshold = float(params.get("rgyr_threshold", 18.0))
        operator = "greater_than"
    elif custom_script is not None:
        metric_name = primary_metric or Path(custom_script).stem
        event_name = metric_name

    all_metric_values: list[float] = []
    tagged_events: set[str] = set(manifest.get("analysis", {}).get("tagged_events", []))
    for parquet_path in data_files:
        table = _read_table(parquet_path)
        rows = table.to_pylist()
        coords = np.asarray([row["coordinates"] for row in rows], dtype=np.float32)
        if custom_script is not None:
            metric = _custom_metric(custom_script, func, positions=coords, metadata=manifest)
        elif metric_name == "ligand_pocket_min_distance":
            ligand_indices = _selection_indices_from_manifest(manifest, ligand or "resname LIG")
            pocket_indices = _selection_indices_from_manifest(manifest, pocket or "protein")
            metric = _min_distances(coords[:, ligand_indices, :], coords[:, pocket_indices, :])
        else:
            metric = _radius_of_gyration(coords)
        event = _threshold(metric, operator, threshold) if threshold is not None else np.zeros(len(metric), dtype=bool)
        for row, value, triggered in zip(rows, metric, event, strict=True):
            row[metric_name] = float(value)
            if metric_name != "rmsd":
                row["radius_of_gyration"] = float(value) if metric_name == "radius_of_gyration" else row.get("radius_of_gyration")
            row["event_label"] = event_name if bool(triggered) else (row.get("event_label") or "")
            row["event_confidence"] = float(value)
        _write_heavy_rows(parquet_path, rows)
        all_metric_values.extend(float(value) for value in metric)
        if bool(np.any(event)):
            tagged_events.add(event_name)

    manifest["analysis"] = {
        "primary_metric": metric_name,
        "event_type": event_name,
        "metrics": {
            metric_name: {
                "min": float(np.min(all_metric_values)) if all_metric_values else 0.0,
                "max": float(np.max(all_metric_values)) if all_metric_values else 0.0,
                "mean": float(np.mean(all_metric_values)) if all_metric_values else 0.0,
            }
        },
        "tagged_events": sorted(tagged_events),
    }
    _write_json(_cache(project_root) / MANIFEST_FILE, manifest)
    return _cache(project_root)


def tag_workspace(
    *,
    project_root: Path,
    event: str,
    start_frame: int,
    end_frame: int,
    confidence: float = 1.0,
) -> Path:
    """Inject an explicit event interval into prepared Parquet shards."""

    config = read_project_config(project_root)
    allowed = set(config.get("labels", {}).get("allowed_events", []))
    if allowed and event not in allowed:
        raise ValidationError(
            f"Event '{event}' is not allowed by {PROJECT_FILE}.",
            suggestion=f"Allowed events: {', '.join(sorted(allowed))}",
        )
    if end_frame <= start_frame:
        raise ValidationError("--end-frame must be greater than --start-frame")
    manifest = read_manifest(project_root)
    touched = 0
    for parquet_path in _data_files(project_root):
        rows = _read_table(parquet_path).to_pylist()
        for row in rows:
            if start_frame <= int(row["frame_id"]) < end_frame:
                row["event_label"] = event
                row["event_confidence"] = float(confidence)
                touched += 1
        _write_heavy_rows(parquet_path, rows)
    if touched == 0:
        raise ValidationError("Manual tag interval did not match any prepared frame.")
    analysis = manifest.setdefault("analysis", {})
    tagged = set(analysis.get("tagged_events", []))
    tagged.add(event)
    analysis["tagged_events"] = sorted(tagged)
    _write_json(_cache(project_root) / MANIFEST_FILE, manifest)
    return _cache(project_root)


def package_workspace(
    *,
    project_root: Path,
    train_frac: float = 0.8,
    validation_frac: float = 0.1,
    test_frac: float = 0.1,
    hf_repo_link: str = "",
) -> Path:
    """Finalize prepared shards into Hugging Face split Parquet files."""

    _validate_split_fractions(train_frac, validation_frac, test_frac)
    project_root = Path(project_root)
    manifest = read_manifest(project_root)
    all_rows: list[dict[str, Any]] = []
    for parquet_path in _data_files(project_root):
        all_rows.extend(_read_table(parquet_path).to_pylist())
    all_rows.sort(key=lambda row: int(row["frame_id"]))
    n = len(all_rows)
    train_end = int(n * train_frac)
    val_end = train_end + int(n * validation_frac)
    splits = {
        "train": all_rows[:train_end],
        "validation": all_rows[train_end:val_end],
        "test": all_rows[val_end:],
    }
    data_dir = _cache(project_root) / DATA_DIR
    for old in data_dir.glob("*.parquet"):
        old.unlink()
    for split, rows in splits.items():
        _write_heavy_rows(data_dir / f"{split}-00000-of-00001.parquet", rows)

    index_dir = _cache(project_root) / INDEX_DIR
    index_dir.mkdir(parents=True, exist_ok=True)
    for old in index_dir.glob("*.parquet"):
        old.unlink()
    index_row = _metadata_index_row(manifest, all_rows, hf_repo_link=hf_repo_link)
    _write_table(index_dir / "index-00000-of-00001.parquet", [index_row], metadata_index_schema())
    card = dataset_card(project_root, repo_id=hf_repo_link or "local")
    (_cache(project_root) / "dataset_card.md").write_text(card, encoding="utf-8")
    manifest["splits"] = {name: {"num_rows": len(rows)} for name, rows in splits.items()}
    manifest["hf_repo_link"] = hf_repo_link
    _write_json(_cache(project_root) / MANIFEST_FILE, manifest)
    return _cache(project_root)


def validate_workspace(project_root: Path) -> list[str]:
    """Validate project config, manifest, Parquet shards, and metadata index."""

    project_root = Path(project_root)
    errors: list[str] = []
    if not (project_root / PROJECT_FILE).exists():
        errors.append(f"{PROJECT_FILE} missing")
    manifest_path = _cache(project_root) / MANIFEST_FILE
    if not manifest_path.exists():
        errors.append(f"{CACHE_DIRNAME}/{MANIFEST_FILE} missing")
    if errors:
        _write_validation(project_root, errors)
        return errors
    manifest = read_manifest(project_root)
    if not manifest.get("dataset_name"):
        errors.append("manifest dataset_name missing")
    parquet_files = _data_files(project_root)
    if not parquet_files:
        errors.append("no data parquet files found")
    frame_ids: list[int] = []
    expected_names = heavy_tensor_schema().names
    for parquet_path in parquet_files:
        try:
            table = _read_table(parquet_path)
        except Exception as exc:
            errors.append(f"{parquet_path.name} is not readable Parquet: {exc}")
            continue
        for column in expected_names:
            if column not in table.column_names:
                errors.append(f"{parquet_path.name} missing column {column}")
        if "frame_id" in table.column_names:
            frame_ids.extend(int(value.as_py()) for value in table.column("frame_id"))
    if frame_ids:
        sorted_ids = sorted(frame_ids)
        if sorted_ids != list(range(sorted_ids[0], sorted_ids[-1] + 1)):
            errors.append("frame coverage has missing or duplicate frame IDs")
    if manifest.get("splits") and not list((_cache(project_root) / INDEX_DIR).glob("*.parquet")):
        errors.append("metadata_index parquet missing after package")
    _write_validation(project_root, errors)
    return errors


def publish_workspace(
    *,
    project_root: Path,
    repo_id: str,
    private: bool = False,
    token: str | None = None,
    dry_run_out: Path | None = None,
) -> Path | str:
    """Upload finalized cache assets to Hugging Face, or copy them for a dry run."""

    errors = validate_workspace(project_root)
    if errors:
        raise ValidationError("; ".join(errors))
    cache = _cache(project_root)
    if dry_run_out is not None:
        out = Path(dry_run_out)
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        shutil.copytree(cache / DATA_DIR, out / DATA_DIR)
        if (cache / INDEX_DIR).exists():
            shutil.copytree(cache / INDEX_DIR, out / INDEX_DIR)
        shutil.copy2(cache / "dataset_card.md", out / "README.md")
        return out
    try:
        from huggingface_hub import HfApi
    except Exception as exc:  # pragma: no cover - depends on local env
        raise DependencyError("huggingface_hub", purpose="publishing to Hugging Face") from exc
    api = HfApi()
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True, token=token)
    api.upload_folder(
        folder_path=str(cache / DATA_DIR),
        path_in_repo="data",
        repo_id=repo_id,
        repo_type="dataset",
        token=token,
    )
    api.upload_folder(
        folder_path=str(cache / INDEX_DIR),
        path_in_repo="metadata_index",
        repo_id=repo_id,
        repo_type="dataset",
        token=token,
    )
    api.upload_file(
        path_or_fileobj=str(cache / "dataset_card.md"),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
        token=token,
    )
    return repo_id


def load_hf_dataset(repo_id: str, *, split: str = "train", streaming: bool = True) -> Any:
    try:
        import datasets
    except Exception as exc:  # pragma: no cover - depends on local env
        raise DependencyError("datasets", purpose="loading a Hugging Face dataset") from exc
    return datasets.load_dataset(repo_id, split=split, streaming=streaming)


def benchmark_registry() -> list[dict[str, str]]:
    return [
        {
            "name": "rare_event_gpcr_v1",
            "repo_id": "mddatanet/rare-event-gpcr-v1",
            "task": "rare_event_prediction",
        },
        {
            "name": "ligand_unbinding_demo",
            "repo_id": "mddatanet/ligand-unbinding-demo",
            "task": "ligand_unbinding",
        },
    ]


def workspace_summary(project_root: Path) -> dict[str, Any]:
    manifest = read_manifest(project_root)
    return {
        "dataset_name": manifest.get("dataset_name"),
        "total_frames": manifest.get("total_frames"),
        "num_atoms_selected": manifest.get("num_atoms_selected"),
        "has_forces": manifest.get("has_forces"),
        "time_stride_ps": manifest.get("time_stride_ps"),
        "splits": manifest.get("splits"),
        "analysis": manifest.get("analysis"),
    }


def dataset_card(project_root: Path, *, repo_id: str) -> str:
    manifest = read_manifest(project_root)
    project = manifest.get("project", {})
    task = project.get("task", "time-series-forecasting")
    tags = sorted(set(["molecular-dynamics", "mddatanet", str(task).replace("_", "-"), *manifest.get("analysis", {}).get("tagged_events", [])]))
    front_matter = ["---", "task_categories:", "- time-series-forecasting", "tags:"]
    front_matter.extend(f"- {tag.replace('_', '-')}" for tag in tags)
    if project.get("license"):
        front_matter.append(f"license: {project['license']}")
    front_matter.append("---")
    return (
        "\n".join(front_matter)
        + "\n\n"
        + f"# {manifest['dataset_name']}\n\n"
        + f"Hugging Face repo: `{repo_id}`\n\n"
        + "This dataset was prepared by MDDataNet from molecular dynamics trajectories. "
        + "Rows are per-frame molecular tensors with frame-aligned scalar metrics and "
        + "operational event labels.\n\n"
        + "## Streaming\n\n"
        + "```python\n"
        + "from datasets import load_dataset\n"
        + f"ds = load_dataset(\"{repo_id}\", split=\"train\", streaming=True)\n"
        + "```\n\n"
        + "Operational labels are reproducible rule-based or explicitly tagged labels, "
        + "not universal biological truth.\n"
    )


def read_project_config(project_root: Path) -> dict[str, Any]:
    path = Path(project_root) / PROJECT_FILE
    if not path.exists():
        raise PackageError(f"{PROJECT_FILE} missing. Run `mddatanet init` first.")
    data = read_yaml(path) or {}
    if not isinstance(data, dict):
        raise PackageError(f"{PROJECT_FILE} must contain a YAML mapping.")
    return data


def read_manifest(project_root: Path) -> dict[str, Any]:
    path = _cache(project_root) / MANIFEST_FILE
    if not path.exists():
        raise PackageError(f"{CACHE_DIRNAME}/{MANIFEST_FILE} missing. Run `mddatanet prepare` first.")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _cache(project_root: Path) -> Path:
    return Path(project_root) / CACHE_DIRNAME


def _ray_module() -> Any:
    try:
        import ray
    except Exception as exc:  # pragma: no cover - depends on local env
        raise DependencyError("ray", purpose="distributed prepare workers") from exc
    return ray


def _project_template() -> str:
    return """# MDDataNet project descriptor.
dataset_name: mddatanet-demo
task: rare_event_prediction
license: cc-by-4.0
visibility: public

system:
  biomolecule_type: protein_ligand
  protein_name: unknown
  organism: unknown
  pdb_id: null

simulation:
  engine: unknown
  forcefield: unknown
  water_model: unknown
  membrane: null
  temperature_k: null
  timestep_fs: null

labels:
  allowed_events:
    - ligand_unbinding
    - ligand_binding
    - activation_transition
    - partial_unfolding
"""


def _candidate_selections(universe: Any) -> dict[str, dict[str, Any]]:
    candidates = {
        "protein": "protein",
        "ligand": "resname LIG or resname UNK",
        "membrane": "resname POPC or resname DPPC",
        "solvent": "resname SOL or resname WAT or resname HOH",
    }
    output: dict[str, dict[str, Any]] = {}
    for key, selection in candidates.items():
        try:
            atoms = universe.select_atoms(selection)
            output[key] = {"selection": selection, "atoms": int(atoms.n_atoms)}
        except Exception:
            output[key] = {"selection": selection, "atoms": 0}
    return output


def _universe_forces_available(universe: Any) -> bool:
    try:
        _ = universe.atoms.forces
    except Exception:
        return False
    return True


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _frame_slice(num_frames: int, *, start: int | None, stop: int | None, stride: int) -> list[int]:
    first = 0 if start is None else max(0, start)
    last = num_frames if stop is None else min(num_frames, stop)
    return list(range(first, last, stride))


def _chunks(values: Sequence[int], size: int) -> Iterable[list[int]]:
    for offset in range(0, len(values), size):
        yield list(values[offset : offset + size])


def _first_not_none(values: Iterable[Any]) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _data_files(project_root: Path) -> list[Path]:
    return sorted((_cache(project_root) / DATA_DIR).glob("*.parquet"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_validation(project_root: Path, errors: list[str]) -> None:
    report = {"valid": not errors, "errors": errors}
    _write_json(_cache(project_root) / VALIDATION_REPORT, report)


def _read_table(path: Path) -> Any:
    try:
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - depends on local env
        raise DependencyError("pyarrow", purpose="Parquet reading") from exc
    return pq.read_table(path)


def _write_table(path: Path, rows: list[dict[str, Any]], schema: Any) -> None:
    try:
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - depends on local env
        raise DependencyError("pyarrow", purpose="Parquet writing") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    pa = pyarrow_module()
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path)


def _write_heavy_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "frame_id": int(row["frame_id"]),
                "time_ps": float(row["time_ps"]),
                "coordinates": row["coordinates"],
                "forces": row.get("forces"),
                "rmsd": _optional_float(row.get("rmsd")),
                "radius_of_gyration": _optional_float(row.get("radius_of_gyration")),
                "event_label": str(row.get("event_label") or ""),
                "event_confidence": float(row.get("event_confidence") or 0.0),
            }
        )
    _write_table(path, normalized, heavy_tensor_schema())


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _validate_split_fractions(train: float, validation: float, test: float) -> None:
    if min(train, validation, test) < 0:
        raise PackageError("Split fractions must be non-negative.")
    if not np.isclose(train + validation + test, 1.0):
        raise PackageError("Split fractions must sum to 1.0.")


def _metadata_index_row(manifest: dict[str, Any], rows: list[dict[str, Any]], *, hf_repo_link: str) -> dict[str, Any]:
    rmsd_values = [row["rmsd"] for row in rows if row.get("rmsd") is not None]
    rgyr_values = [row["radius_of_gyration"] for row in rows if row.get("radius_of_gyration") is not None]
    tagged = sorted({row["event_label"] for row in rows if row.get("event_label")})
    project = manifest.get("project", {})
    system = project.get("system", {})
    simulation = project.get("simulation", {})
    return {
        "dataset_name": manifest["dataset_name"],
        "protein_name": str(system.get("protein_name") or "unknown"),
        "forcefield": str(simulation.get("forcefield") or "unknown"),
        "max_rmsd": float(max(rmsd_values)) if rmsd_values else 0.0,
        "min_radius_of_gyration": float(min(rgyr_values)) if rgyr_values else 0.0,
        "tagged_events": tagged,
        "hf_repo_link": hf_repo_link,
    }


def _selection_indices_from_manifest(manifest: dict[str, Any], selection: str) -> np.ndarray:
    topology = manifest["shards"][0].get("topology", {})
    atom_names = np.asarray(topology.get("atom_names", []), dtype=str)
    residue_names = np.asarray(topology.get("residue_names", []), dtype=str)
    selection = selection.strip()
    if selection == "protein":
        mask = ~np.isin(np.char.upper(residue_names), ["HOH", "WAT", "SOL", "LIG", "UNK"])
    elif selection.startswith("resname "):
        wanted = selection.split(None, 1)[1].strip().upper()
        mask = np.char.upper(residue_names) == wanted
    elif selection.startswith("name "):
        wanted = selection.split(None, 1)[1].strip().upper()
        mask = np.char.upper(atom_names) == wanted
    else:
        raise SelectionError(
            f"Unsupported staging selection: {selection}",
            suggestion="Use simple selections like `protein`, `resname LIG`, or `name CA` in this MVP.",
        )
    indices = np.nonzero(mask)[0]
    if len(indices) == 0:
        raise SelectionError(f"Selection matched 0 atoms: {selection}")
    return indices


def _radius_of_gyration(positions: np.ndarray) -> np.ndarray:
    centered = positions - np.mean(positions, axis=1, keepdims=True)
    return np.sqrt(np.mean(np.sum(centered * centered, axis=-1), axis=1)).astype(np.float32)


def _min_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    values = []
    for frame_a, frame_b in zip(a, b, strict=True):
        distances = np.linalg.norm(frame_a[:, None, :] - frame_b[None, :, :], axis=-1)
        values.append(float(np.min(distances)))
    return np.asarray(values, dtype=np.float32)


def _threshold(values: np.ndarray, operator: str, threshold: Any) -> np.ndarray:
    threshold = float(threshold)
    if operator == "greater_than":
        return values > threshold
    if operator == "greater_equal":
        return values >= threshold
    if operator == "less_than":
        return values < threshold
    if operator == "less_equal":
        return values <= threshold
    raise FeatureError(f"Unsupported threshold operator: {operator}")


def _custom_metric(script: Path, func: str | None, *, positions: np.ndarray, metadata: dict[str, Any]) -> np.ndarray:
    if func is None:
        raise FeatureError("--custom-script requires --func")
    spec = importlib.util.spec_from_file_location("_mddatanet_custom_metric", script)
    if spec is None or spec.loader is None:
        raise FeatureError(f"Could not import custom metric script: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_mddatanet_custom_metric"] = module
    spec.loader.exec_module(module)
    metric_func = getattr(module, func, None)
    if metric_func is None:
        raise FeatureError(f"Custom metric function not found: {func}")
    try:
        values = metric_func(positions=positions, metadata=metadata)
    except TypeError:
        values = metric_func(positions)
    array = np.asarray(values, dtype=np.float32)
    if array.shape != (positions.shape[0],):
        raise FeatureError("Custom metric must return one numeric scalar per frame.")
    return array


def _prepare_chunk_worker(
    topology: str,
    coordinates: str | None,
    trajectory: str | None,
    frame_indices: list[int],
    out_path: str,
    selection: str,
    run_index: int,
    trajectory_index: int,
) -> dict[str, Any]:
    universe = load_universe(topology, coordinates=coordinates, trajectory=trajectory)
    selected = _select_atoms(universe, selection)
    rows: list[dict[str, Any]] = []
    force_missing = False
    topology_meta = _atom_metadata(selected)
    for frame_id in frame_indices:
        ts = universe.trajectory[int(frame_id)]
        selected = _select_atoms(universe, selection)
        forces = _frame_forces(selected)
        if forces is None:
            force_missing = True
        rows.append(
            {
                "frame_id": int(frame_id),
                "time_ps": float(getattr(ts, "time", frame_id)),
                "coordinates": np.asarray(selected.positions, dtype=np.float32).tolist(),
                "forces": None if forces is None else forces.tolist(),
                "rmsd": None,
                "radius_of_gyration": None,
                "event_label": "",
                "event_confidence": 0.0,
            }
        )
    _write_heavy_rows(Path(out_path), rows)
    timestep = _safe_float(getattr(universe.trajectory, "dt", None))
    return {
        "shard_index": int(Path(out_path).stem.split("-")[-1]),
        "run_index": run_index,
        "trajectory_index": trajectory_index,
        "path": str(out_path),
        "start_frame": int(frame_indices[0]),
        "end_frame": int(frame_indices[-1]) + 1,
        "source_start": int(frame_indices[0]),
        "source_stop": int(frame_indices[-1]) + 1,
        "num_rows": len(rows),
        "num_atoms_selected": int(selected.n_atoms),
        "has_forces": not force_missing,
        "timestep_ps": timestep,
        "reader": universe.trajectory.__class__.__name__,
        "topology": topology_meta,
    }


def _select_atoms(universe: Any, selection: str) -> Any:
    if selection == "not solvent":
        atoms = _non_solvent_atoms(universe)
    else:
        try:
            atoms = universe.select_atoms(selection)
        except Exception as exc:
            raise SelectionError(f"Invalid atom selection: {selection}") from exc
    if int(atoms.n_atoms) == 0:
        raise SelectionError(f"Atom selection matched 0 atoms: {selection}")
    return atoms


def _non_solvent_atoms(universe: Any) -> Any:
    solvent_names = {"HOH", "WAT", "SOL", "TIP3", "TIP3P", "NA", "CL", "K", "CA"}
    mask = np.asarray([str(atom.resname).upper() not in solvent_names for atom in universe.atoms], dtype=bool)
    return universe.atoms[mask]


def _atom_metadata(atoms: Any) -> dict[str, list[Any]]:
    return {
        "atom_names": [str(value) for value in atoms.names],
        "residue_names": [str(atom.resname) for atom in atoms],
        "residue_ids": [int(atom.resid) for atom in atoms],
        "source_atom_indices": [int(index) for index in atoms.indices],
    }


def _frame_forces(atoms: Any) -> np.ndarray | None:
    try:
        forces = atoms.forces
    except Exception:
        return None
    return np.asarray(forces, dtype=np.float32).copy()
