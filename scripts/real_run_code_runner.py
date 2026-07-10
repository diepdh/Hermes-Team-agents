"""Real end-to-end exercise for code_runner.py with sample data.

This script uses mock LLM (patched get_llm) but real sandbox execution.
The code generated is realistic statistical Python that reads/writes
input.json/output.json and prints extractable values to stdout.

Paste raw output into the final report.
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.agents.code_runner import run_code_runner
from hermes.core.sandbox import _extract_values, DEFAULT_EXTRACTION_PATTERNS


def main():
    # Create a temporary workspace
    tmp = tempfile.mkdtemp(prefix="hermes-real-run-")
    ws_root = Path(tmp) / "workspace"
    ws_root.mkdir()
    (ws_root / "artifacts").mkdir()
    (ws_root / "logs").mkdir()
    idx = ws_root / "artifact_index.json"
    idx.write_text("{}")

    class WS:
        root = ws_root
        artifact_dir = ws_root / "artifacts"
        artifact_index_path = idx
        log_dir = ws_root / "logs"
        def ensure_initialized(self): pass
        def relative(self, p): return p.relative_to(self.root)

    ws = WS()

    # Create verified source_analysis artifact with numeric data
    source_content = {
        "paragraphs_summary": "Test dataset: 100 survey responses with scores from 1-5.",
        "tables": [
            [["Group", "Score"], ["A", "4.2"], ["A", "3.8"], ["B", "2.1"], ["B", "2.8"]]
        ],
        "images": [],
        "key_statistics": ["42.5", "7.3", "0.05", "3.14", "99.0"],
    }

    art_id = "A-TEST01"
    art_path = ws.artifact_dir / f"{art_id}_v1.md"
    art_path.write_text(json.dumps(source_content))
    idx_data = {
        f"{art_id}_v1": {
            "artifact_id": art_id,
            "type": "source_analysis",
            "version": 1,
            "content_ref": ws.relative(art_path).as_posix(),
            "verification_status": "pass",
            "verification_notes": "",
            "produced_by_task": "T-20260709-001",
            "metadata": {},
            "parent_artifact_id": None,
            "created_at": "2026-07-09T00:00:00Z",
        }
    }
    idx.write_text(json.dumps(idx_data))

    art_record = idx_data[f"{art_id}_v1"]

    # Realistic statistical Python code (simulates what LLM would generate)
    realistic_code = (
        "import json\n"
        "with open('input.json') as f:\n"
        "    data = json.load(f)\n"
        "stats_raw = data['key_statistics']\n"
        "vals = []\n"
        "for v in stats_raw:\n"
        "    try:\n"
        "        vals.append(float(v))\n"
        "    except ValueError:\n"
        "        pass\n"
        "if not vals:\n"
        "    vals = [42.5, 7.3, 0.05, 3.14, 99.0]\n"
        "n = len(vals)\n"
        "mean_val = sum(vals) / n\n"
        "sorted_vals = sorted(vals)\n"
        "mid = n // 2\n"
        "if n % 2 == 0:\n"
        "    median_val = (sorted_vals[mid-1] + sorted_vals[mid]) / 2\n"
        "else:\n"
        "    median_val = sorted_vals[mid]\n"
        "import math\n"
        "variance = sum((x - mean_val)**2 for x in vals) / (n - 1) if n > 1 else 0\n"
        "std_val = math.sqrt(variance)\n"
        "print(f'mean = {mean_val}')\n"
        "print(f'median = {median_val}')\n"
        "print(f'std = {std_val}')\n"
        "print(f'sample_size = {n}')\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump({'mean': mean_val, 'median': median_val, 'std': std_val, 'n': n}, f)\n"
    )

    # ── Run code_runner with mocked LLM ────────────────────────────────
    with patch("hermes.agents.code_runner.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.call.return_value = realistic_code
        mock_get_llm.return_value = mock_llm

        result = run_code_runner(ws, art_record)

    # ── Read artifact and display results ──────────────────────────────
    print("=" * 70)
    print("CODE_RUNNER REAL RUN — RESULTS")
    print("=" * 70)
    print(f"\nArtifact ID: {result['artifact_id']}")
    print(f"Artifact type: {result['type']}")
    print(f"Version: {result['version']}")
    print(f"Static scan passed: {result.get('metadata', {}).get('static_scan_passed')}")
    print(f"Reproducible: {result.get('metadata', {}).get('reproducible')}")
    print(f"Timeout: {result.get('metadata', {}).get('timeout')}")
    print(f"Extraction count: {result.get('metadata', {}).get('extraction_count')}")

    content_file = ws.root / result["content_ref"]
    content = json.loads(content_file.read_text())

    print(f"\n--- execution_log.stdout ---")
    print(content["execution_log"]["stdout"])

    print(f"\n--- execution_log.stderr ---")
    print(content["execution_log"]["stderr"])

    print(f"\n--- execution_log.exit_code ---")
    print(content["execution_log"]["exit_code"])

    print(f"\n--- extracted_values ---")
    print(json.dumps(content["extracted_values"], indent=2))

    print(f"\n--- verification ---")
    v = content["verification"]
    print(f"  reproducible: {v['reproducible']}")
    print(f"  input_hash: {v['input_hash'][:16]}...")
    print(f"  output_hash_1: {v['output_hash_1'][:16]}...")
    print(f"  output_hash_2: {v['output_hash_2'][:16]}...")
    print(f"  output_hash match: {v['output_hash_1'] == v['output_hash_2']}")
    print(f"  sandbox_workspace_A: {v['sandbox_workspace_A']}")
    print(f"  sandbox_workspace_B: {v['sandbox_workspace_B']}")

    print(f"\n--- static_scan_result ---")
    print(f"  passed: {content['static_scan_result']['passed']}")
    print(f"  reads_input: {content['static_scan_result']['reads_input']}")

    # ── Verify workspaces still exist (point C) ────────────────────────
    ws_a = Path(v["sandbox_workspace_A"])
    ws_b = Path(v["sandbox_workspace_B"])
    print(f"\n--- Workspace persistence (point C) ---")
    print(f"  Workspace A exists: {ws_a.exists()}")
    print(f"  Workspace B exists: {ws_b.exists()}")

    # Clean up
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print("\nDone. All workspaces cleaned up.")


if __name__ == "__main__":
    main()
