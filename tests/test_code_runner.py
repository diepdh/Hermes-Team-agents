"""Unit tests for P5.7b — Code Runner agent (hermes/agents/code_runner.py)."""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hermes.agents.code_runner import (
    _build_code_generation_prompt,
    _clean_code,
    _serialize_input_data,
    run_code_runner,
)
from hermes.core.sandbox import ALLOWED_MODULES


# ============================================================================
# Helpers
# ============================================================================

def _make_mock_workspace(tmp_path):
    """Create a minimal mock workspace with artifact storage."""
    ws_root = tmp_path / "workspace"
    ws_root.mkdir()
    artifacts_dir = ws_root / "artifacts"
    artifacts_dir.mkdir()
    _logs_dir = ws_root / "logs"
    _logs_dir.mkdir()
    index_path = ws_root / "artifact_index.json"
    index_path.write_text("{}", encoding="utf-8")

    class MockWorkspace:
        log_dir = _logs_dir
        artifact_dir = artifacts_dir
        artifact_index_path = index_path
        root = ws_root

        def ensure_initialized(self):
            pass

        def relative(self, file_path):
            return file_path.relative_to(self.root)

    return MockWorkspace()


def _make_mock_source_analysis_artifact(ws, content=None):
    """Create a mock source_analysis artifact record with verified status."""
    if content is None:
        content = {
            "paragraphs_summary": "Test data with 100 samples.",
            "tables": [],
            "images": [],
            "key_statistics": ["42.5", "7.3", "0.05"],
        }

    # Save as file so read_artifact_content works
    artifact_id = f"A-{uuid.uuid4().hex[:4]}"
    file_path = ws.artifact_dir / f"{artifact_id}_v1.md"
    file_path.write_text(json.dumps(content), encoding="utf-8")

    # Update index
    index = json.loads(ws.artifact_index_path.read_text())
    key = f"{artifact_id}_v1"
    index[key] = {
        "artifact_id": artifact_id,
        "type": "source_analysis",
        "version": 1,
        "content_ref": ws.relative(file_path).as_posix(),
        "verification_status": "pass",
        "verification_notes": "",
        "produced_by_task": "T-20260709-001",
        "metadata": {},
        "parent_artifact_id": None,
        "created_at": "2026-07-09T00:00:00Z",
    }
    ws.artifact_index_path.write_text(json.dumps(index, indent=2))

    return index[key]


# ============================================================================
# Tests: _clean_code
# ============================================================================

def test_clean_code_strips_markdown_fences():
    raw = "```python\nimport json\ndata = json.load(open('input.json'))\n```"
    cleaned = _clean_code(raw)
    assert "```" not in cleaned
    assert "import json" in cleaned


def test_clean_code_strips_fence_without_lang():
    raw = "```\nimport json\n```"
    cleaned = _clean_code(raw)
    assert "```" not in cleaned


def test_clean_code_preserves_plain_code():
    raw = "import json\ndata = json.load(open('input.json'))"
    cleaned = _clean_code(raw)
    assert cleaned == raw


# ============================================================================
# Tests: _build_code_generation_prompt
# ============================================================================

def test_prompt_includes_allowed_modules():
    prompt = _build_code_generation_prompt(
        "Test data: 100 samples", "Compute mean and std"
    )
    assert "input.json" in prompt
    assert "output.json" in prompt
    assert "eval()" in prompt  # warning against eval


def test_prompt_includes_analysis_request():
    request = "Compute correlation between A and B"
    prompt = _build_code_generation_prompt("Data with A, B columns", request)
    assert request in prompt


# ============================================================================
# Tests: _serialize_input_data
# ============================================================================

def test_serialize_input_data_basic():
    source = {
        "paragraphs_summary": "Test summary",
        "key_statistics": [42.5, 7.3],
        "tables": [],
        "images": [],
    }
    input_json, desc = _serialize_input_data(source)
    parsed = json.loads(input_json)
    assert parsed["summary"] == "Test summary"
    assert "42.5" in parsed["key_statistics"]  # converted to str
    assert "statistics" in desc.lower()  # "Key statistics (2 values)"


def test_serialize_input_data_with_suggestions():
    source = {"paragraphs_summary": "Data", "key_statistics": [], "tables": [], "images": []}
    assessment = {"option_2_suggestions": ["Run t-test", "Compute ANOVA"]}
    input_json, desc = _serialize_input_data(source, assessment)
    assert "t-test" in desc
    assert "ANOVA" in desc


def test_serialize_input_data_minimal():
    source = {}
    input_json, desc = _serialize_input_data(source)
    parsed = json.loads(input_json)
    assert "key_statistics" in parsed
    assert parsed["key_statistics"] == []


# ============================================================================
# Tests: run_code_runner — static scan fail path
# ============================================================================

def test_run_code_runner_rejects_unverified_source(tmp_path):
    """source_analysis not verified → ValueError."""
    ws = _make_mock_workspace(tmp_path)

    # Create an unverified artifact
    art = _make_mock_source_analysis_artifact(ws)
    art["verification_status"] = "pending"

    with pytest.raises(ValueError, match="unverified|must be 'pass'"):
        run_code_runner(ws, art, provider=None)


def test_run_code_runner_static_scan_fail_saves_artifact(tmp_path):
    """LLM generates dangerous code → static scan fails → artifact saved with violations."""
    ws = _make_mock_workspace(tmp_path)
    art = _make_mock_source_analysis_artifact(ws)

    dangerous_code = "import os\nos.system('rm -rf /')\n"

    with patch("hermes.agents.code_runner.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.call.return_value = dangerous_code
        mock_get_llm.return_value = mock_llm

        result = run_code_runner(ws, art)

    assert result["type"] == "generated_data"
    metadata = result.get("metadata", {})
    assert metadata.get("static_scan_passed") is False

    # Read artifact content
    content_file = ws.root / result["content_ref"]
    content = json.loads(content_file.read_text())
    assert content["static_scan_result"]["passed"] is False
    assert len(content["static_scan_result"]["violations"]) > 0
    assert content["execution_log"]["exit_code"] == -2
    assert "not executed" in content["execution_log"]["stderr"]


# ============================================================================
# Tests: run_code_runner — happy path (integration with real sandbox)
# ============================================================================

def test_run_code_runner_happy_path_reproducible(tmp_path):
    """Full lifecycle: LLM generates safe code → double-run → reproducible=True."""
    ws = _make_mock_workspace(tmp_path)
    art = _make_mock_source_analysis_artifact(ws)

    safe_code = (
        "import json\n"
        "with open('input.json') as f:\n"
        "    data = json.load(f)\n"
        "vals = [float(v) for v in data['key_statistics']"
        " if v.replace('.','').replace('-','').isdigit()]\n"
        "if not vals:\n"
        "    vals = [1.0, 2.0, 3.0]\n"
        "mean_val = sum(vals) / len(vals)\n"
        "sorted_vals = sorted(vals)\n"
        "n = len(vals)\n"
        "if n % 2 == 0:\n"
        "    median_val = (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2\n"
        "else:\n"
        "    median_val = sorted_vals[n//2]\n"
        "print(f'mean = {mean_val}')\n"
        "print(f'median = {median_val}')\n"
        "print(f'sample_size = {n}')\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump({'mean': mean_val, 'median': median_val, 'n': n}, f)\n"
    )

    with patch("hermes.agents.code_runner.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.call.return_value = safe_code
        mock_get_llm.return_value = mock_llm

        result = run_code_runner(ws, art)

    assert result["type"] == "generated_data"
    metadata = result.get("metadata", {})
    assert metadata.get("static_scan_passed") is True
    assert metadata.get("reproducible") is True

    # Read artifact content
    content_file = ws.root / result["content_ref"]
    content = json.loads(content_file.read_text())

    assert content["static_scan_result"]["passed"] is True
    assert content["verification"]["reproducible"] is True
    assert content["execution_log"]["exit_code"] == 0
    assert len(content["extracted_values"]) > 0

    # Verify extraction
    extracts = content["extracted_values"]
    assert "mean" in extracts, (
        f"Expected 'mean' in extracted_values, got: {list(extracts.keys())}"
    )
    assert "sample_size" in extracts


def test_run_code_runner_reads_input_detection(tmp_path):
    """Code that reads input.json → static_scan_result.reads_input = True."""
    ws = _make_mock_workspace(tmp_path)
    art = _make_mock_source_analysis_artifact(ws)

    code = (
        "import json\n"
        "with open('input.json') as f:\n"
        "    data = json.load(f)\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump({'ok': True}, f)\n"
        "print('sample_size = 42')\n"
    )

    with patch("hermes.agents.code_runner.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.call.return_value = code
        mock_get_llm.return_value = mock_llm

        result = run_code_runner(ws, art)

    content_file = ws.root / result["content_ref"]
    content = json.loads(content_file.read_text())
    assert content["static_scan_result"]["reads_input"] is True


def test_run_code_runner_llm_failure_raises(tmp_path):
    """LLM call fails → RuntimeError raised."""
    ws = _make_mock_workspace(tmp_path)
    art = _make_mock_source_analysis_artifact(ws)

    with patch("hermes.agents.code_runner.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.call.side_effect = ConnectionError("API unreachable")
        mock_get_llm.return_value = mock_llm

        with pytest.raises(RuntimeError, match="LLM code generation failed"):
            run_code_runner(ws, art)


# ============================================================================
# Tests: ID uniqueness
# ============================================================================

def test_run_code_runner_generates_unique_artifact_id(tmp_path):
    """Two runs → different artifact IDs."""
    ws = _make_mock_workspace(tmp_path)
    art = _make_mock_source_analysis_artifact(ws)

    code = (
        "import json\n"
        "with open('input.json') as f:\n"
        "    data = json.load(f)\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump({'x': 1}, f)\n"
        "print('mean = 1.0')\n"
    )

    with patch("hermes.agents.code_runner.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.call.return_value = code
        mock_get_llm.return_value = mock_llm

        r1 = run_code_runner(ws, art)
        r2 = run_code_runner(ws, art)

    assert r1["artifact_id"] != r2["artifact_id"]


# ============================================================================
# Tests: prompt content
# ============================================================================

def test_prompt_warns_against_eval_exec():
    prompt = _build_code_generation_prompt("data", "analyze")
    assert "eval()" in prompt
    assert "exec()" in prompt


def test_prompt_mentions_output_json():
    prompt = _build_code_generation_prompt("data", "analyze")
    assert "output.json" in prompt


def test_prompt_lists_print_formats():
    prompt = _build_code_generation_prompt("data", "analyze")
    assert "mean = " in prompt
    assert "p_value = " in prompt
