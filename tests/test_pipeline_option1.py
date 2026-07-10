"""Integration tests for P5.7b pipeline (OPTION=1 code_runner path)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from hermes.pipeline.existing_paper_pipeline import run_option1_code_runner


def _make_workspace(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "artifacts").mkdir()
    (root / "logs").mkdir()
    idx = root / "artifact_index.json"
    idx.write_text("{}")
    class WS:
        pass
    ws = WS()
    ws.root = root; ws.artifact_dir = root / "artifacts"
    ws.artifact_index_path = idx; ws.log_dir = root / "logs"
    ws.ensure_initialized = lambda: None
    ws.relative = lambda p: p.relative_to(root)
    return ws


def _make_source_artifact(ws, content=None):
    import uuid
    if content is None:
        content = {"paragraphs_summary":"t","key_statistics":["1","2","3"],"tables":[],"images":[]}
    art_id = f"A-{uuid.uuid4().hex[:4]}"
    path = ws.artifact_dir / f"{art_id}_v1.md"
    path.write_text(json.dumps(content))
    idx = json.loads(ws.artifact_index_path.read_text())
    idx[f"{art_id}_v1"] = {
        "artifact_id":art_id,"type":"source_analysis","version":1,
        "content_ref":ws.relative(path).as_posix(),
        "verification_status":"pass","verification_notes":"",
        "produced_by_task":"T-001","metadata":{},
        "parent_artifact_id":None,"created_at":"2026-07-09T00:00:00Z",
    }
    ws.artifact_index_path.write_text(json.dumps(idx))
    return idx[f"{art_id}_v1"]


def _save_gen_artifact(ws, art_id, version, content_str, metadata):
    path = ws.artifact_dir / f"{art_id}_v{version}.md"
    path.write_text(content_str, encoding="utf-8")
    idx = json.loads(ws.artifact_index_path.read_text())
    idx[f"{art_id}_v{version}"] = {
        "artifact_id":art_id,"type":"generated_data","version":version,
        "content_ref":ws.relative(path).as_posix(),
        "metadata":metadata,
        "verification_status":"pending","verification_notes":"",
        "produced_by_task":"T-code","parent_artifact_id":None,
        "created_at":"2026-07-09T00:00:00Z",
    }
    ws.artifact_index_path.write_text(json.dumps(idx))


# ============================================================================

VALID_CONTENT = json.dumps({
    "code":"import json\nwith open('input.json') as f:\n    data=json.load(f)\nprint('mean = 3.5')\nwith open('output.json','w') as f:\n    json.dump({'m':3.5},f)\n",
    "execution_log":{"stdout":"mean = 3.5\n","stderr":"","exit_code":0,"elapsed_seconds":0.1,"timeout":False},
    "extracted_values":{"mean":"3.5"},"extraction_method":"regex",
    "static_scan_result":{"passed":True,"violations":[],"reads_input":True},
    "verification":{"input_hash":"a"*64,"output_hash_1":"b"*64,"output_hash_2":"b"*64,"reproducible":True,"sandbox_workspace_A":"/tmp/a","sandbox_workspace_B":"/tmp/b"},
    "_timeout":False,
})

FAIL_CONTENT = json.dumps({
    "code":"import os\n","static_scan_result":{"passed":False,"violations":["import os"],"reads_input":False},
    "execution_log":{"stdout":"","stderr":"not executed","exit_code":-2,"elapsed_seconds":0,"timeout":False},
    "extracted_values":{},"extraction_method":"regex",
    "verification":{"input_hash":"","output_hash_1":"","output_hash_2":"","reproducible":False,"sandbox_workspace_A":"","sandbox_workspace_B":""},
    "_timeout":False,
})


def test_option1_success_first_attempt(tmp_path):
    ws = _make_workspace(tmp_path)
    src = _make_source_artifact(ws)

    art = {"artifact_id":"gen-test","type":"generated_data","version":1,
           "content_ref":"artifacts/gen-test_v1.md",
           "metadata":{"static_scan_passed":True,"reproducible":True,"timeout":False}}
    _save_gen_artifact(ws,"gen-test",1,VALID_CONTENT,art["metadata"])

    with patch("hermes.agents.code_runner.run_code_runner", return_value=art):
        with patch("hermes.core.risk.should_trigger_debate", return_value=True):
            with patch("hermes.pipeline.debate_review_task.run_debate_review", return_value={"final_decision":"consensus_pass","rounds":[{}]}):
                r = run_option1_code_runner(ws, src, {}, max_retries=1)

    assert r["verification_status"] == "pass"
    assert r["attempts"] == 1


def test_option1_retry_on_static_scan_fail(tmp_path):
    ws = _make_workspace(tmp_path)
    src = _make_source_artifact(ws)

    fail_art = {"artifact_id":"gen-test","type":"generated_data","version":1,
                "content_ref":"artifacts/gen-test_v1.md",
                "metadata":{"static_scan_passed":False}}
    _save_gen_artifact(ws,"gen-test",1,FAIL_CONTENT,fail_art["metadata"])

    success_art = {"artifact_id":"gen-test","type":"generated_data","version":2,
                   "content_ref":"artifacts/gen-test_v2.md",
                   "metadata":{"static_scan_passed":True,"reproducible":True,"timeout":False}}
    _save_gen_artifact(ws,"gen-test",2,VALID_CONTENT,success_art["metadata"])

    calls = [0]
    def side_effect(*args, **kwargs):
        calls[0] += 1
        if calls[0] == 1: return fail_art
        return success_art

    with patch("hermes.agents.code_runner.run_code_runner", side_effect=side_effect):
        with patch("hermes.core.risk.should_trigger_debate", return_value=True):
            with patch("hermes.pipeline.debate_review_task.run_debate_review", return_value={"final_decision":"consensus_pass","rounds":[{}]}):
                r = run_option1_code_runner(ws, src, {}, max_retries=3)

    assert r["attempts"] == 2
    assert calls[0] == 2


def test_option1_all_retries_exhausted(tmp_path):
    ws = _make_workspace(tmp_path)
    src = _make_source_artifact(ws)

    with patch("hermes.agents.code_runner.run_code_runner", side_effect=RuntimeError("LLM down")):
        r = run_option1_code_runner(ws, src, {}, max_retries=2)

    assert r["verification_status"] == "fail"
    assert r["attempts"] == 2
    assert "LLM down" in r["error"]
