"""Chunked MDAnalysis-backed feature computation."""

from __future__ import annotations

import shutil
import json
from pathlib import Path
from typing import Any

from mddatanet.format.dataset_card import write_dataset_card
from mddatanet.format.metadata import read_metadata, write_metadata
from mddatanet.format.provenance import read_provenance, write_provenance
from mddatanet.format.schema import FeatureConfig, FeatureDefinition, RunRecord
from mddatanet.io.checksums import sha256_file, write_checksums
from mddatanet.io.loaders import load_universe
from mddatanet.io.source import require_source_path, source_path
from mddatanet.io.workspace import PackageWorkspace
from mddatanet.io.zarr_store import DEFAULT_POSITION_FRAME_CHUNK, create_array, open_zarr_group, write_index_names
from mddatanet.utils.errors import FeatureError, SelectionError
from mddatanet.utils.yaml import read_yaml, write_yaml


def featurize_package(
    *,
    input_path: Path,
    out: Path,
    features_path: Path | None = None,
    feature_config: FeatureConfig | dict[str, Any] | None = None,
    chunk_size: int = DEFAULT_POSITION_FRAME_CHUNK,
    overwrite: bool = False,
    command: str | None = None,
) -> Path:
    """Add feature arrays to an existing package."""

    if features_path is None and feature_config is None:
        raise FeatureError("featurize requires a feature config")
    if feature_config is None:
        feature_config = FeatureConfig.model_validate(read_yaml(features_path))
    elif isinstance(feature_config, dict):
        feature_config = FeatureConfig.model_validate(feature_config)

    workspace = PackageWorkspace(input_path, out, overwrite=overwrite)
    with workspace as work_dir:
        compute_features_in_place(
            work_dir,
            feature_config,
            chunk_size=chunk_size,
            config_base_dir=features_path.parent if features_path is not None else None,
        )
        metadata = read_metadata(work_dir)
        provenance = read_provenance(work_dir)
        feature_names = sorted(set(metadata.features.feature_names) | {feature.name for feature in feature_config.features})
        metadata.features.feature_names = feature_names
        metadata.features.num_features = len(feature_names)
        if command:
            provenance.commands.append(command)
        if features_path is not None:
            shutil.copyfile(features_path, work_dir / "feature_config.yaml")
            provenance.feature_config_checksum = sha256_file(features_path)
        else:
            write_yaml(feature_config.model_dump(mode="json", exclude_none=True), work_dir / "feature_config.yaml")
            provenance.feature_config_checksum = sha256_file(work_dir / "feature_config.yaml")
        (work_dir / "feature_metadata.json").write_text(
            json.dumps(
                {
                    "features": [
                        feature.model_dump(mode="json", exclude_none=True)
                        for feature in feature_config.features
                    ],
                    "feature_config_checksum": provenance.feature_config_checksum,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        zarr_root = open_zarr_group(work_dir / "dataset.zarr", mode="a")
        write_index_names(zarr_root, feature_names=feature_names)
        write_metadata(work_dir, metadata)
        write_provenance(work_dir, provenance)
        write_dataset_card(work_dir, metadata, provenance)
        write_checksums(work_dir)
        workspace.finalize()
    return out


def compute_features_in_place(
    package_dir: Path,
    feature_config: FeatureConfig,
    *,
    chunk_size: int = DEFAULT_POSITION_FRAME_CHUNK,
    config_base_dir: Path | None = None,
) -> None:
    """Compute features directly inside an unpacked package directory."""

    from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

    metadata = read_metadata(package_dir)
    provenance = read_provenance(package_dir)
    topology = require_source_path(provenance, "topology")
    coordinates = source_path(provenance, "coordinates")
    zarr_root = open_zarr_group(package_dir / "dataset.zarr", mode="a")
    arrays = zarr_root["arrays"]
    frame_indices = arrays["source_frame_indices"] if "source_frame_indices" in arrays else arrays["frame_indices"]
    if int(frame_indices.shape[0]) != int(metadata.system.num_frames):
        raise FeatureError("arrays/frame_indices length does not match metadata frame count")

    runs = _run_records(provenance, metadata)
    outputs = {
        definition.name: create_array(
            zarr_root["features"],
            definition.name,
            shape=(metadata.system.num_frames,),
            dtype=_feature_dtype(definition),
            chunks=(min(max(metadata.system.num_frames, 1), 65_536),),
            overwrite=True,
        )
        for definition in feature_config.features
    }

    positions = arrays["positions"] if "positions" in arrays else None
    stored_dimensions = arrays["dimensions"] if "dimensions" in arrays else None
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Computing features...", total=metadata.system.num_frames)
        for run in runs:
            universe, raw_available = _open_run_universe(
                topology=topology,
                coordinates=coordinates,
                run=run,
                positions_available=positions is not None,
            )
            evaluators = [
                _FeatureEvaluator(definition, universe, config_base_dir=config_base_dir)
                for definition in feature_config.features
            ]
            for start in range(run.package_start, run.package_stop, chunk_size):
                stop = min(start + chunk_size, run.package_stop)
                source_frames = frame_indices[start:stop]
                chunk_dimensions = stored_dimensions[start:stop] if stored_dimensions is not None else None
                chunk_values = {evaluator.definition.name: [] for evaluator in evaluators}
                for offset, source_frame in enumerate(source_frames):
                    box = None
                    if raw_available:
                        ts = universe.trajectory[int(source_frame)]
                        box = getattr(ts, "dimensions", None)
                    elif positions is not None:
                        universe.atoms.positions = positions[start + offset]
                        box = chunk_dimensions[offset] if chunk_dimensions is not None else None
                    else:
                        raise FeatureError(
                            "Cannot featurize because raw trajectory files are unavailable and positions were not stored.",
                            suggestion="Re-run `mddatanet convert --store-positions` or restore the original trajectory files.",
                        )
                    for evaluator in evaluators:
                        chunk_values[evaluator.definition.name].append(evaluator.compute(box=box))
                for evaluator in evaluators:
                    outputs[evaluator.definition.name][start:stop] = chunk_values[evaluator.definition.name]
                progress.update(task, advance=len(source_frames))



def _run_records(provenance, metadata) -> list[RunRecord]:
    if provenance.runs:
        return provenance.runs
    trajectory = source_path(provenance, "trajectory")
    return [
        RunRecord(
            run_id="run_0",
            trajectory_file=str(trajectory) if trajectory is not None else None,
            trajectory_format=trajectory.suffix.lower().lstrip(".") if trajectory is not None else metadata.source.trajectory_format,
            reader=None,
            atom_count=metadata.system.num_atoms,
            num_frames=metadata.system.num_frames,
            package_start=0,
            package_stop=metadata.system.num_frames,
            source_start=provenance.frame_start or 0,
            source_stop=provenance.frame_stop or metadata.system.num_frames,
            source_stride=provenance.frame_stride or 1,
            timestep_ps=metadata.system.timestep_ps,
            has_periodic_box=metadata.system.has_periodic_box,
        )
    ]


def _open_run_universe(
    *,
    topology: Path,
    coordinates: Path | None,
    run: RunRecord,
    positions_available: bool,
):
    trajectory = Path(run.trajectory_file) if run.trajectory_file else None
    try:
        if trajectory is not None and not trajectory.exists():
            raise FileNotFoundError(str(trajectory))
        return load_universe(topology, coordinates=coordinates, trajectory=trajectory), True
    except Exception as exc:
        if not positions_available:
            raise FeatureError(
                f"Recorded trajectory for run '{run.run_id}' is unavailable: {trajectory}",
                suggestion="Restore the raw trajectory file or re-run `mddatanet convert --store-positions`.",
            ) from exc
        return load_universe(topology, coordinates=coordinates, trajectory=None), False


class _FeatureEvaluator:
    def __init__(self, definition: FeatureDefinition, universe: Any, *, config_base_dir: Path | None) -> None:
        self.definition = definition
        self.universe = universe
        self.config_base_dir = config_base_dir
        self.dtype = _feature_dtype(definition)
        self.selection = _select(universe, definition.selection) if definition.selection else None
        self.selection_a = _select(universe, definition.selection_a) if definition.selection_a else None
        self.selection_b = _select(universe, definition.selection_b) if definition.selection_b else None
        self.dihedral_atoms = [_select_one(universe, atom_selection) for atom_selection in definition.atoms or []]
        self.reference_selection = None
        self.native_pairs: tuple[Any, Any] | None = None
        if definition.reference:
            reference_path = _resolve_reference(definition.reference, config_base_dir)
            reference_universe = load_universe(reference_path)
            if definition.selection:
                self.reference_selection = _select(reference_universe, definition.selection)
                if self.selection is not None and len(self.reference_selection) != len(self.selection):
                    raise FeatureError(
                        f"Feature '{definition.name}' selection has {len(self.selection)} atoms but reference has {len(self.reference_selection)} atoms."
                    )
            if definition.type == "native_contact_fraction":
                threshold = _required_float(definition.threshold_angstrom, "threshold_angstrom", definition.name)
                self.native_pairs = _native_pairs(self.reference_selection.positions, threshold)

    def compute(self, *, box=None) -> float | bool | int:
        definition = self.definition
        if box is None:
            box = getattr(self.universe.trajectory.ts, "dimensions", None)
        if definition.type == "distance":
            return _distance_feature(self.selection_a, self.selection_b, definition.mode, box=box)
        if definition.type == "min_distance":
            return _min_distance(self.selection_a.positions, self.selection_b.positions, box=box)
        if definition.type == "contact":
            threshold = _required_float(definition.threshold_angstrom, "threshold_angstrom", definition.name)
            return _has_contact(self.selection_a.positions, self.selection_b.positions, threshold, box=box)
        if definition.type == "contact_count":
            threshold = _required_float(definition.threshold_angstrom, "threshold_angstrom", definition.name)
            return _contact_count(self.selection_a.positions, self.selection_b.positions, threshold, box=box)
        if definition.type == "dihedral":
            from mddatanet.features.dihedrals import dihedral_angle

            units = definition.units or "degrees"
            return dihedral_angle(*(atom.position for atom in self.dihedral_atoms), units=units)
        if definition.type == "rmsd":
            from mddatanet.features.rmsd import rmsd

            return rmsd(self.selection.positions, self.reference_selection.positions)
        if definition.type == "radius_of_gyration":
            return float(self.selection.radius_of_gyration())
        if definition.type == "native_contact_fraction":
            return _native_contact_fraction(self.selection.positions, self.native_pairs, _required_float(definition.threshold_angstrom, "threshold_angstrom", definition.name), box=box)
        raise FeatureError(f"Unsupported feature type: {definition.type}")


def _feature_dtype(definition: FeatureDefinition) -> str:
    if definition.type == "contact":
        return "bool"
    if definition.type == "contact_count":
        return "int64"
    return "float32"


def _select(universe: Any, selection: str | None):
    if not selection:
        return None
    try:
        group = universe.select_atoms(selection)
    except Exception as exc:
        raise SelectionError(f"Invalid selection '{selection}': {exc}") from exc
    if len(group) == 0:
        raise SelectionError(
            f"selection '{selection}' matched 0 atoms.",
            suggestion="Check your topology file or selection syntax.",
        )
    return group


def _select_one(universe: Any, selection: str):
    group = _select(universe, selection)
    if len(group) != 1:
        raise SelectionError(f"selection '{selection}' matched {len(group)} atoms; expected exactly 1.")
    return group[0]


def _distance_feature(selection_a, selection_b, mode: str | None, *, box=None) -> float:
    if mode is None and len(selection_a) == 1 and len(selection_b) == 1:
        mode = "single_atom"
    mode = mode or "center_of_geometry"
    if mode == "single_atom":
        if len(selection_a) != 1 or len(selection_b) != 1:
            raise SelectionError("single_atom distance mode requires each selection to match exactly one atom.")
        point_a = selection_a.positions[0]
        point_b = selection_b.positions[0]
    elif mode == "center_of_geometry":
        point_a = selection_a.center_of_geometry()
        point_b = selection_b.center_of_geometry()
    elif mode == "center_of_mass":
        point_a = selection_a.center_of_mass()
        point_b = selection_b.center_of_mass()
    else:
        raise FeatureError(f"Unsupported distance mode: {mode}")

    import numpy as np

    if box is not None:
        from MDAnalysis.lib.distances import calc_bonds

        return float(calc_bonds(point_a, point_b, box=box))
    return float(np.linalg.norm(point_a - point_b))


def _min_distance(positions_a, positions_b, *, box=None, block_size: int = 512) -> float:
    from MDAnalysis.lib.distances import distance_array
    import numpy as np

    a = np.asarray(positions_a, dtype="float32")
    b = np.asarray(positions_b, dtype="float32")
    best = float("inf")
    for i in range(0, a.shape[0], block_size):
        a_block = a[i : i + block_size]
        for j in range(0, b.shape[0], block_size):
            b_block = b[j : j + block_size]
            dist = distance_array(a_block, b_block, box=box)
            value = float(dist.min())
            if value < best:
                best = value
    return best


def _has_contact(positions_a, positions_b, threshold: float, *, box=None, block_size: int = 512) -> bool:
    from MDAnalysis.lib.distances import distance_array
    import numpy as np

    a = np.asarray(positions_a, dtype="float32")
    b = np.asarray(positions_b, dtype="float32")
    for i in range(0, a.shape[0], block_size):
        a_block = a[i : i + block_size]
        for j in range(0, b.shape[0], block_size):
            b_block = b[j : j + block_size]
            dist = distance_array(a_block, b_block, box=box)
            if bool((dist <= threshold).any()):
                return True
    return False


def _contact_count(positions_a, positions_b, threshold: float, *, box=None, block_size: int = 512) -> int:
    from MDAnalysis.lib.distances import distance_array
    import numpy as np

    a = np.asarray(positions_a, dtype="float32")
    b = np.asarray(positions_b, dtype="float32")
    count = 0
    for i in range(0, a.shape[0], block_size):
        a_block = a[i : i + block_size]
        for j in range(0, b.shape[0], block_size):
            b_block = b[j : j + block_size]
            dist = distance_array(a_block, b_block, box=box)
            count += int((dist <= threshold).sum())
    return count


def _native_pairs(reference_positions, threshold: float):
    from MDAnalysis.lib.distances import self_distance_array
    import numpy as np

    positions = np.asarray(reference_positions, dtype="float32")
    # Reference is typically PDB, no box.
    dist = self_distance_array(positions)
    # self_distance_array returns condensed 1D array.
    # We need i, j indices.
    n = len(positions)
    triu_indices = np.triu_indices(n, k=1)
    hits = np.where(dist <= threshold)[0]
    return triu_indices[0][hits], triu_indices[1][hits]


def _native_contact_fraction(positions, native_pairs, threshold: float, *, box=None) -> float:
    from MDAnalysis.lib.distances import calc_bonds
    import numpy as np

    if native_pairs is None:
        return 0.0
    i_values, j_values = native_pairs
    if len(i_values) == 0:
        return 0.0
    positions = np.asarray(positions, dtype="float32")
    dist = calc_bonds(positions[i_values], positions[j_values], box=box)
    retained = int((dist <= threshold).sum())
    return float(retained / len(i_values))



def _resolve_reference(reference: str, config_base_dir: Path | None) -> Path:
    path = Path(reference)
    if path.is_absolute() or config_base_dir is None:
        return path
    return config_base_dir / path


def _required_float(value: float | None, field: str, feature_name: str) -> float:
    if value is None:
        raise FeatureError(f"Feature '{feature_name}' requires {field}.")
    return float(value)
