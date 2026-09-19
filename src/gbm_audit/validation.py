"""Validation helpers for versioned pipeline artifacts and cross-stage provenance."""

import hashlib
import json


SCHEMA_VERSION = 1


class ArtifactValidationError(ValueError):
    """Raised when a pipeline artifact violates its declared contract."""


def canonical_sha256(payload: dict) -> str:
    """Hash a JSON-compatible mapping using the repository's canonical encoding."""
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(rendered).hexdigest()


def _require_mapping(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise ArtifactValidationError(f"{label} must be a JSON object")
    return value


def _require_keys(payload: dict, keys: tuple[str, ...], label: str) -> None:
    missing = [key for key in keys if key not in payload]
    if missing:
        raise ArtifactValidationError(f"{label} missing required keys: {', '.join(missing)}")


def validate_schema_version(payload: dict, label: str) -> None:
    _require_mapping(payload, label)
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ArtifactValidationError(
            f"{label} schema_version must be {SCHEMA_VERSION}; found {version!r}"
        )


def validate_manifest(manifest: dict) -> None:
    validate_schema_version(manifest, "reference manifest")
    _require_keys(manifest, ("dataset", "split_policy", "sequences"), "reference manifest")
    sequences = _require_mapping(manifest["sequences"], "reference manifest sequences")
    if not sequences:
        raise ArtifactValidationError("reference manifest must contain at least one sequence")
    for sequence_id, sequence in sequences.items():
        _require_mapping(sequence, f"reference sequence {sequence_id}")
        _require_keys(sequence, ("sequence_id", "split", "frames", "shape_pixels", "tracks"),
                      f"reference sequence {sequence_id}")
        if str(sequence["sequence_id"]) != str(sequence_id):
            raise ArtifactValidationError(
                f"reference sequence key {sequence_id!r} does not match sequence_id {sequence['sequence_id']!r}"
            )
        if not isinstance(sequence["tracks"], list):
            raise ArtifactValidationError(f"reference sequence {sequence_id} tracks must be a list")


def scenario_map(payload: dict, label: str) -> dict[str, dict]:
    validate_schema_version(payload, label)
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list):
        raise ArtifactValidationError(f"{label} scenarios must be a list")
    indexed: dict[str, dict] = {}
    for index, scenario in enumerate(scenarios):
        _require_mapping(scenario, f"{label} scenario {index}")
        _require_keys(scenario, ("scenario_id", "corruption", "severity"),
                      f"{label} scenario {index}")
        scenario_id = scenario["scenario_id"]
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ArtifactValidationError(f"{label} scenario {index} has invalid scenario_id")
        if scenario_id in indexed:
            raise ArtifactValidationError(f"{label} contains duplicate scenario_id {scenario_id!r}")
        if not isinstance(scenario.get("sequence_results", scenario.get("sequences")), dict):
            raise ArtifactValidationError(
                f"{label} scenario {scenario_id!r} must contain sequences or sequence_results"
            )
        indexed[scenario_id] = scenario
    return indexed


def validate_corruptions(corruptions: dict, manifest: dict | None = None) -> None:
    validate_schema_version(corruptions, "corruption benchmark")
    _require_keys(corruptions, ("dataset", "reference_manifest_sha256", "seed", "scenarios"),
                  "corruption benchmark")
    scenario_map(corruptions, "corruption benchmark")
    if manifest is not None:
        validate_manifest(manifest)
        expected = canonical_sha256(manifest)
        actual = corruptions["reference_manifest_sha256"]
        if actual != expected:
            raise ArtifactValidationError(
                "corruption benchmark reference_manifest_sha256 does not match the supplied manifest"
            )
        if corruptions["dataset"] != manifest["dataset"]:
            raise ArtifactValidationError("corruption benchmark dataset does not match the supplied manifest")


def validate_stage_artifact(payload: dict, label: str, corruptions: dict) -> None:
    """Validate schema, scenario identity, reference hash, seed and sequence keys."""
    validate_schema_version(payload, label)
    _require_keys(payload, ("reference_manifest_sha256", "corruption_seed", "scenarios"), label)
    if payload["reference_manifest_sha256"] != corruptions["reference_manifest_sha256"]:
        raise ArtifactValidationError(f"{label} reference manifest hash does not match corruptions")
    if payload["corruption_seed"] != corruptions["seed"]:
        raise ArtifactValidationError(f"{label} corruption seed does not match corruptions")
    reference = scenario_map(corruptions, "corruption benchmark")
    stage = scenario_map(payload, label)
    if set(stage) != set(reference):
        missing = sorted(set(reference) - set(stage))
        extra = sorted(set(stage) - set(reference))
        raise ArtifactValidationError(
            f"{label} scenario IDs do not match corruptions; missing={missing}, extra={extra}"
        )
    for scenario_id, expected in reference.items():
        actual = stage[scenario_id]
        if actual["corruption"] != expected["corruption"] or actual["severity"] != expected["severity"]:
            raise ArtifactValidationError(f"{label} metadata mismatch for scenario {scenario_id!r}")
        expected_sequences = set(expected["sequences"])
        actual_sequences = set(actual["sequence_results"])
        if actual_sequences != expected_sequences:
            raise ArtifactValidationError(
                f"{label} sequence IDs do not match corruptions for scenario {scenario_id!r}"
            )


def align_scenarios(primary: dict, secondary: dict, primary_label: str,
                    secondary_label: str) -> list[tuple[dict, dict]]:
    """Return scenarios aligned by ID after checking metadata and sequence identities."""
    primary_map = scenario_map(primary, primary_label)
    secondary_map = scenario_map(secondary, secondary_label)
    if set(primary_map) != set(secondary_map):
        missing = sorted(set(primary_map) - set(secondary_map))
        extra = sorted(set(secondary_map) - set(primary_map))
        raise ArtifactValidationError(
            f"{secondary_label} scenario IDs do not match {primary_label}; missing={missing}, extra={extra}"
        )
    aligned = []
    for scenario in primary["scenarios"]:
        other = secondary_map[scenario["scenario_id"]]
        if other["corruption"] != scenario["corruption"] or other["severity"] != scenario["severity"]:
            raise ArtifactValidationError(
                f"{secondary_label} metadata mismatch for scenario {scenario['scenario_id']!r}"
            )
        primary_sequences = scenario.get("sequences", scenario.get("sequence_results", {}))
        secondary_sequences = other.get("sequences", other.get("sequence_results", {}))
        if set(primary_sequences) != set(secondary_sequences):
            raise ArtifactValidationError(
                f"{secondary_label} sequence IDs do not match {primary_label} for scenario {scenario['scenario_id']!r}"
            )
        aligned.append((scenario, other))
    return aligned
