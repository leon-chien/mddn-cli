"""Pydantic schemas for the MDDataNet package format."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SystemMetadata(StrictModel):
    system_type: str = "unknown"
    num_atoms: int = Field(ge=0)
    num_residues: int = Field(ge=0)
    num_frames: int = Field(ge=0)
    num_runs: int = Field(default=1, ge=0)
    timestep_ps: float | None = None
    time_unit: str = "ps"
    distance_unit: str = "angstrom"
    has_periodic_box: bool | None = None
    organism: str | None = None
    protein: str | None = None
    ligand_present: bool | None = None


class SourceMetadata(StrictModel):
    topology_file: str | None = None
    coordinates_file: str | None = None
    trajectory_file: str | None = None
    trajectory_files: list[str] = Field(default_factory=list)
    topology_format: str | None = None
    coordinates_format: str | None = None
    trajectory_format: str | None = None
    source_url: str | None = None
    citation: str | None = None


class SimulationMetadata(StrictModel):
    engine: str | None = None
    force_field: str | None = None
    solvent: str | None = None
    ensemble: str | None = None


class FeatureSummary(StrictModel):
    num_features: int = Field(default=0, ge=0)
    feature_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def count_matches_names(self) -> "FeatureSummary":
        if self.num_features != len(self.feature_names):
            self.num_features = len(self.feature_names)
        return self


class LabelSummary(StrictModel):
    num_events: int = Field(default=0, ge=0)
    event_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def count_matches_names(self) -> "LabelSummary":
        if self.num_events != len(self.event_names):
            self.num_events = len(self.event_names)
        return self


class SplitSummary(StrictModel):
    strategy: str | None = None
    train: int | None = None
    val: int | None = None
    test: int | None = None
    gap: int | None = None


class Metadata(StrictModel):
    mddatanet_version: str = "0.1.0"
    format_version: str = "1.0"
    dataset_name: str
    description: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    system: SystemMetadata
    source: SourceMetadata = Field(default_factory=SourceMetadata)
    simulation: SimulationMetadata = Field(default_factory=SimulationMetadata)
    features: FeatureSummary = Field(default_factory=FeatureSummary)
    labels: LabelSummary = Field(default_factory=LabelSummary)
    splits: SplitSummary | None = None
    license: str = "unknown"
    tags: dict[str, Any] = Field(default_factory=dict)


class SourceFile(StrictModel):
    path: str
    sha256: str
    role: str | None = None
    run_id: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    format: str | None = None
    resolved_path: str | None = None


class RunRecord(StrictModel):
    run_id: str
    trajectory_file: str | None = None
    trajectory_format: str | None = None
    reader: str | None = None
    atom_count: int = Field(ge=0)
    num_frames: int = Field(ge=0)
    package_start: int = Field(ge=0)
    package_stop: int = Field(ge=0)
    source_start: int = Field(ge=0)
    source_stop: int = Field(ge=0)
    source_stride: int = Field(ge=1)
    timestep_ps: float | None = None
    time_unit: str = "ps"
    has_periodic_box: bool | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> "RunRecord":
        if self.package_stop < self.package_start:
            raise ValueError("package_stop must be >= package_start")
        if self.source_stop < self.source_start:
            raise ValueError("source_stop must be >= source_start")
        return self


class CommandRecord(StrictModel):
    command: str
    executed_at: str = Field(default_factory=utc_now_iso)


class Provenance(StrictModel):
    created_by: str = "mddatanet"
    mddatanet_version: str = "0.1.0"
    python_version: str | None = None
    platform: str | None = None
    commands: list[str | CommandRecord] = Field(default_factory=list)
    source_files: list[SourceFile] = Field(default_factory=list)
    runs: list[RunRecord] = Field(default_factory=list)
    frame_start: int | None = None
    frame_stop: int | None = None
    frame_stride: int | None = None
    stored_positions: bool = False
    conversion_time_seconds: float | None = None
    feature_config_checksum: str | None = None
    event_config_checksum: str | None = None


FeatureType = Literal[
    "distance",
    "min_distance",
    "contact",
    "contact_count",
    "dihedral",
    "rmsd",
    "radius_of_gyration",
    "native_contact_fraction",
    "contact_map",
]


class FeatureDefinition(StrictModel):
    name: str
    type: FeatureType
    selection_a: str | None = None
    selection_b: str | None = None
    selection: str | None = None
    atoms: list[str] | None = None
    mode: str | None = None
    reference: str | None = None
    threshold_angstrom: float | None = None
    units: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not value or "/" in value or "\\" in value:
            raise ValueError("feature names must be non-empty path-safe names")
        return value

    @model_validator(mode="after")
    def validate_required_fields(self) -> "FeatureDefinition":
        if self.type in {"distance", "min_distance", "contact", "contact_count"}:
            if not self.selection_a or not self.selection_b:
                raise ValueError(f"{self.type} requires selection_a and selection_b")
        if self.type == "dihedral" and (not self.atoms or len(self.atoms) != 4):
            raise ValueError("dihedral requires exactly four atom selections")
        if self.type in {"rmsd", "radius_of_gyration", "native_contact_fraction"} and not self.selection:
            raise ValueError(f"{self.type} requires selection")
        if self.type in {"rmsd", "native_contact_fraction"} and not self.reference:
            raise ValueError(f"{self.type} requires reference")
        return self


class FeatureConfig(StrictModel):
    features: list[FeatureDefinition]

    @model_validator(mode="after")
    def validate_unique_names(self) -> "FeatureConfig":
        names = [feature.name for feature in self.features]
        if len(names) != len(set(names)):
            raise ValueError("feature names must be unique")
        return self


EventType = Literal["feature_threshold", "feature_window", "feature_bool", "composite"]
Operator = Literal[
    "greater_than",
    "greater_equal",
    "less_than",
    "less_equal",
    "equal",
    "not_equal",
]


class EventCondition(StrictModel):
    feature: str
    operator: Operator
    threshold: float


class EventDefinition(StrictModel):
    name: str
    type: EventType
    feature: str | None = None
    operator: Operator | None = None
    threshold: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    horizon_frames: int = Field(default=0, ge=0)
    logic: Literal["all", "any"] | None = None
    conditions: list[EventCondition] | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not value or "/" in value or "\\" in value:
            raise ValueError("event names must be non-empty path-safe names")
        return value

    @model_validator(mode="after")
    def validate_event_shape(self) -> "EventDefinition":
        if self.type == "feature_threshold":
            if not self.feature or self.operator is None or self.threshold is None:
                raise ValueError("feature_threshold requires feature, operator, and threshold")
        if self.type == "feature_window":
            if not self.feature or self.lower_bound is None or self.upper_bound is None:
                raise ValueError("feature_window requires feature, lower_bound, and upper_bound")
            if self.lower_bound > self.upper_bound:
                raise ValueError("lower_bound must be <= upper_bound")
        if self.type == "feature_bool" and not self.feature:
            raise ValueError("feature_bool requires feature")
        if self.type == "composite":
            if self.logic is None or not self.conditions:
                raise ValueError("composite requires logic and conditions")
        return self


class EventConfig(StrictModel):
    events: list[EventDefinition]

    @model_validator(mode="after")
    def validate_unique_names(self) -> "EventConfig":
        names = [event.name for event in self.events]
        if len(names) != len(set(names)):
            raise ValueError("event names must be unique")
        return self


class SplitManifest(StrictModel):
    strategy: Literal["temporal", "random_window", "trajectory"]
    train: int
    val: int
    test: int
    gap: int = 0
    seed: int | None = None
