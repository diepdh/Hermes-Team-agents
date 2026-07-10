"""Unit tests for generated_data checker (verifier.py)."""

import json

import pytest

from hermes.core.verifier import CHECKER_REGISTRY, verify_artifact
from hermes.rubrics import load_rubric


@pytest.fixture
def rubric():
    return load_rubric("generated_data")


def _make_artifact_payload(**overrides):
    """Build a valid generated_data artifact payload with defaults."""
    base = {
        "code": "import json\nwith open('input.json') as f:\n    data = json.load(f)\nprint('mean = 3.5')\nwith open('output.json', 'w') as f:\n    json.dump({'m': 3.5}, f)\n",
        "execution_log": {"stdout": "mean = 3.5\n", "stderr": "", "exit_code": 0, "elapsed_seconds": 0.5, "timeout": False},
        "extracted_values": {"mean": "3.5"},
        "extraction_method": "regex — rule-based, no LLM interpretation",
        "static_scan_result": {"passed": True, "violations": [], "reads_input": True},
        "verification": {
            "input_hash": "a" * 64,
            "output_hash_1": "b" * 64,
            "output_hash_2": "b" * 64,
            "reproducible": True,
            "sandbox_workspace_A": "/tmp/a",
            "sandbox_workspace_B": "/tmp/b",
        },
        "_timeout": False,
    }
    base.update(overrides)
    return json.dumps(base)


def _score(content, rubric):
    result = verify_artifact("generated_data", content, rubric)
    return result["score"], result["passed"]


# ============================================================================
# Happy path — all criteria pass
# ============================================================================

def test_checker_all_pass(rubric):
    content = _make_artifact_payload()
    score, passed = _score(content, rubric)
    assert score == 1.0, f"Expected 1.0, got {score}"
    assert passed


# ============================================================================
# Fail: static_scan_passed = False → must fail hard
# ============================================================================

def test_checker_static_scan_fail_blocks_all(rubric):
    """static_scan_passed=False → max score ≤ 0.85 → fail."""
    content = _make_artifact_payload(
        static_scan_result={"passed": False, "violations": ["import os"], "reads_input": False},
        execution_log={"stdout": "", "stderr": "not executed", "exit_code": -2, "elapsed_seconds": 0, "timeout": False},
        extracted_values={},
        verification={"input_hash": "", "output_hash_1": "", "output_hash_2": "", "reproducible": False, "sandbox_workspace_A": "", "sandbox_workspace_B": ""},
    )
    score, passed = _score(content, rubric)
    assert score < 0.90, f"static_scan_passed=False should fail, got {score}"
    assert not passed


# ============================================================================
# Fail: reproducible = False
# ============================================================================

def test_checker_reproducible_false_fails(rubric):
    content = _make_artifact_payload(
        verification={
            "input_hash": "a" * 64,
            "output_hash_1": "b" * 64,
            "output_hash_2": "c" * 64,
            "reproducible": False,
            "sandbox_workspace_A": "/tmp/a",
            "sandbox_workspace_B": "/tmp/b",
        }
    )
    score, passed = _score(content, rubric)
    assert score < 0.90, f"reproducible=False should fail, got {score}"
    assert not passed


# ============================================================================
# Fail: reads_input = False
# ============================================================================

def test_checker_reads_input_false_fails(rubric):
    content = _make_artifact_payload(
        static_scan_result={"passed": True, "violations": [], "reads_input": False},
        code="print('hello')\n",  # no input.json read
    )
    score, passed = _score(content, rubric)
    assert score < 0.90, f"reads_input=False should fail, got {score}"
    assert not passed


# ============================================================================
# Fail: empty code
# ============================================================================

def test_checker_empty_code_fails(rubric):
    # has_code=0 + reads_input=0 + has_execution_log=0 (empty stdout)
    # = max 1.0 - 0.10 - 0.15 - 0.10 = 0.65 < 0.90 → fail
    content = _make_artifact_payload(
        code="   \n",
        static_scan_result={"passed": True, "violations": [], "reads_input": False},
        execution_log={"stdout": "", "stderr": "", "exit_code": 0, "elapsed_seconds": 0, "timeout": False},
        extracted_values={},
        verification={"input_hash": "a"*64, "output_hash_1": "b"*64, "output_hash_2": "b"*64, "reproducible": True, "sandbox_workspace_A": "", "sandbox_workspace_B": ""},
    )
    score, passed = _score(content, rubric)
    assert score < 0.90, f"Empty code should fail, got {score}"


# ============================================================================
# Fail: malformed JSON
# ============================================================================

def test_checker_malformed_json_handled(rubric):
    score, passed = _score("not json at all {{{", rubric)
    assert score < 0.90
    assert not passed


# ============================================================================
# Edge cases
# ============================================================================

def test_checker_empty_stdout_but_no_patterns_ok(rubric):
    """stdout empty with no extractable patterns → extraction_consistent=1.0 (principle 9)."""
    content = _make_artifact_payload(
        execution_log={"stdout": "", "stderr": "", "exit_code": 0, "elapsed_seconds": 0.1, "timeout": False},
        extracted_values={},
    )
    score, passed = _score(content, rubric)
    # With empty stdout: has_code=1, has_log=1, exec_ok=1, log_not_empty=0,
    # static_scan=1, reproducible=1, input_hash=1, reads_input=1, extract_ok=1
    # Score = 0.10+0.10+0.15+0+0.15+0.15+0.10+0.15+0.05 = 0.95 ≥ 0.90 → pass
    assert passed


def test_checker_stdout_has_patterns_but_no_extraction(rubric):
    """stdout has patterns but extracted is empty → extraction_consistent=0."""
    content = _make_artifact_payload(
        execution_log={"stdout": "mean = 3.5\np_value = 0.01", "stderr": "", "exit_code": 0, "elapsed_seconds": 0.1, "timeout": False},
        extracted_values={},
    )
    score, passed = _score(content, rubric)
    # extraction_consistent=0 → max = 1.0 - 0.05 = 0.95 ≥ 0.90 → still pass
    assert passed


# ============================================================================
# Registration check
# ============================================================================

def test_generated_data_checker_registered():
    assert "generated_data" in CHECKER_REGISTRY, (
        "check_generated_data must be registered in CHECKER_REGISTRY"
    )
