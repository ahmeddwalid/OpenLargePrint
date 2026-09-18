"""Tests for SBOM validation, license compliance, and excluded model checks (LIC-001, LIC-002)."""

import json
from pathlib import Path
import pytest


def test_sbom_inventory_completeness():
    """Verify sbom.json exists and adheres to LIC-001 requirements."""
    repo_root = Path(__file__).resolve().parent.parent
    sbom_file = repo_root / "sbom.json"
    assert sbom_file.exists()

    with open(sbom_file, "r") as f:
        data = json.load(f)

    assert "dependencies" in data
    assert "models" in data
    assert "excluded_candidates" in data

    # Validate dependency fields
    required_dep_fields = {
        "component",
        "version",
        "code_license",
        "model_weight_license",
        "download_source",
        "native_code",
        "network_behavior",
        "parses_untrusted_content",
        "purpose",
    }

    recorded_components = set()
    for dep in data["dependencies"]:
        for field in required_dep_fields:
            assert field in dep, f"Missing {field} in dependency: {dep.get('component')}"
        recorded_components.add(dep["component"])

    # Ensure key core components are recorded
    expected_components = [
        "pydantic",
        "pypdfium2",
        "pikepdf",
        "python-docx",
        "rapidocr-onnxruntime",
        "reportlab",
        "arabic-reshaper",
        "python-pptx",
    ]
    for exp in expected_components:
        assert exp in recorded_components

    # Validate models fields
    required_model_fields = {
        "model_key",
        "version",
        "code_license",
        "weight_license",
        "sha256",
        "download_source",
        "native_code",
        "network_behavior",
        "parses_untrusted_content",
        "purpose",
    }

    for m in data["models"]:
        for field in required_model_fields:
            assert field in m, f"Missing {field} in model: {m.get('model_key')}"
        # Assert SHA-256 is 64 hex characters
        assert len(m["sha256"]) == 64


def test_excluded_candidates_policy():
    """Verify excluded candidate models are not silently included (LIC-002, DESIGN.md §4.1)."""
    repo_root = Path(__file__).resolve().parent.parent
    sbom_file = repo_root / "sbom.json"

    with open(sbom_file, "r") as f:
        data = json.load(f)

    dep_names = {d["component"].lower() for d in data["dependencies"]}
    model_names = {m["model_key"].lower() for m in data["models"]}

    # Named excluded candidates from DESIGN.md §4.1
    excluded_names = ["olmocr", "surya", "mineru"]

    for excl in excluded_names:
        assert excl not in dep_names, f"Excluded candidate '{excl}' found in active dependencies! (LIC-002)"
        assert excl not in model_names, f"Excluded candidate '{excl}' found in active models! (LIC-002)"

    # Check that reasons for exclusion are documented
    documented_exclusions = {e["name"].lower() for e in data["excluded_candidates"]}
    for excl in excluded_names:
        assert excl in documented_exclusions
