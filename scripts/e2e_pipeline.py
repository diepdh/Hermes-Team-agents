"""End-to-end P5.7b: real LLM → code_runner → verify → Debate → timestamp check."""
import json, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.pipeline.existing_paper_pipeline import run_option1_code_runner, assess_existing_paper
from hermes.core.risk import should_trigger_debate, get_risk_level

# ── Setup workspace ──
tmp = tempfile.mkdtemp(prefix="hermes-e2e-")
root = Path(tmp) / "ws"
root.mkdir(); (root/"artifacts").mkdir(); (root/"logs").mkdir()
idx = root / "artifact_index.json"
idx.write_text("{}")

class WS:
    pass
ws = WS()
ws.root = root; ws.artifact_dir = root/"artifacts"
ws.artifact_index_path = idx; ws.log_dir = root/"logs"
ws.ensure_initialized = lambda: None
ws.relative = lambda p: p.relative_to(root)

# ── Source data (simple — key_statistics only, keep it easy for LLM) ──
source = {
    "paragraphs_summary": "50 test scores from an exam, range 0-100.",
    "tables": [],
    "images": [],
    "key_statistics": [str(s) for s in
        [45,67,89,23,56,78,91,34,62,50,73,88,41,59,95,28,66,82,47,71,
         53,86,39,64,98,31,58,76,44,69,92,36,61,84,49,72,55,80,42,65,
         96,33,57,79,46,70,93,38,63,85]],
}

# Save source_analysis
import uuid
art_id = f"A-SRC-{uuid.uuid4().hex[:4]}"
path = ws.artifact_dir / f"{art_id}_v1.md"
path.write_text(json.dumps(source))
idx_data = {
    f"{art_id}_v1": {
        "artifact_id":art_id,"type":"source_analysis","version":1,
        "content_ref":ws.relative(path).as_posix(),
        "verification_status":"pass","verification_notes":"",
        "produced_by_task":"T-e2e","metadata":{},
        "parent_artifact_id":None,"created_at":"2026-07-09T00:00:00Z",
    }
}
idx.write_text(json.dumps(idx_data))
src_artifact = idx_data[f"{art_id}_v1"]

# ── Assessment ──
assessment = assess_existing_paper("Test paper about exam scores.", has_accompanying_data=True)

print("=" * 60)
print("P5.7b END-TO-END — REAL LLM + DEBATE TIMESTAMP CHECK")
print("=" * 60)
print(f"source_analysis: {art_id}")
print(f"risk_level(generated_data): {get_risk_level('generated_data')}")
print(f"should_trigger_debate(generated_data): {should_trigger_debate('generated_data')}")

# ── Run option1 ──
t0 = time.time()
result = run_option1_code_runner(
    ws, src_artifact, assessment,
    artifact_id="e2e-gen-data", provider="local_cx", max_retries=1,
)
t1 = time.time()

print(f"\n--- RESULT ---")
print(f"verification_status: {result['verification_status']}")
print(f"attempts: {result['attempts']}")
print(f"elapsed: {t1-t0:.2f}s")

if result["artifact"]:
    art = result["artifact"]
    print(f"artifact_id: {art['artifact_id']}")
    print(f"artifact_version: {art['version']}")
    content = json.loads((ws.root / art["content_ref"]).read_text())
    print(f"reproducible: {content['verification']['reproducible']}")
    print(f"exit_code: {content['execution_log']['exit_code']}")
    print(f"stdout: {content['execution_log']['stdout'][:200]}")
    print(f"extracted: {content['extracted_values']}")

if result["debate_verdict"]:
    dv = result["debate_verdict"]
    print(f"\n--- DEBATE VERDICT ---")
    print(f"final_decision: {dv.get('final_decision')}")
    print(f"rounds: {len(dv.get('rounds',[]))}")
    # TIMESTAMP CHECK — must have real time gap
    art_created = art.get("created_at","")
    print(f"artifact created_at: {art_created}")
    print(f"debate completed at (approx): now")
    print(f"TIMESTAMP CHECK: elapsed={t1-t0:.2f}s "
          f"{'✅ REAL DEBATE RAN' if t1-t0 > 5 else '⚠ CHECK TIMESTAMP'}")
else:
    print("\n--- NO DEBATE (may be unexpected for risk=critical) ---")

# ── Verify event log ──
log_path = ws.log_dir / "events.jsonl"
if log_path.exists():
    events = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    print(f"\n--- EVENT LOG ({len(events)} events) ---")
    for e in events:
        print(f"  {e['event_type']}: {e.get('artifact_id','')} {e.get('status','')}")

print(f"\nWorkspace: {root}")

import shutil
shutil.rmtree(tmp, ignore_errors=True)
