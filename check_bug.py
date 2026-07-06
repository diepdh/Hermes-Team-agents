"""Mục 3 bug investigation: debate_verdict with no_consensus through checker."""
import json, os, tempfile
from pathlib import Path

os.chdir(Path(__file__).parent)
from dotenv import load_dotenv; load_dotenv()

from hermes.core.verifier import verify_artifact, finalize_verification
from hermes.core.workspace import Workspace
from hermes.core.storage import save_artifact
from hermes.rubrics import load_rubric
from hermes.core.risk import get_risk_level, get_effective_threshold, should_trigger_debate

real_debate_verdict = {
    "artifact_type": "debate_verdict",
    "target_artifact_id": "A-debate-real",
    "target_artifact_version": 1,
    "target_artifact_type": "lecture_draft",
    "rounds": [{"round": 1, "proponent_argument": "Lập luận bảo vệ...", "opponent_argument": "Phản biện chỉ ra 5 lỗi..."}],
    "final_decision": "no_consensus",
    "unresolved_issues": ["Debate ended without consensus after 1 round(s). Human review required."],
}

rubric = load_rubric("debate_verdict")
print(f"Rubric threshold: {rubric['pass_threshold']}")
print(f"Risk level: {get_risk_level('debate_verdict')}")
print(f"Effective threshold: {get_effective_threshold('debate_verdict', rubric['pass_threshold'])}")
print(f"should_trigger_debate: {should_trigger_debate('debate_verdict')}")

result = verify_artifact("debate_verdict", json.dumps(real_debate_verdict), rubric)
print(f"\nverify_artifact: passed={result['passed']}, score={result['score']}")
print(f"detail: {json.dumps(result['detail'])}")

ws = Workspace(str(Path(tempfile.mkdtemp())))
ws.ensure_initialized()
save_artifact(ws, "A-debate-real", "x", "debate_verdict", "T-20260706-001")
artifact = save_artifact(ws, "A-debate-real", json.dumps(real_debate_verdict), "debate_verdict", "T-20260706-001")

status = finalize_verification(
    ws, artifact["artifact_id"], artifact["version"], "debate_verdict",
    result, notes="bug investigation",
    rubric_pass_threshold=rubric["pass_threshold"],
)

print(f"\n>>> finalize_verification status: '{status}' <<<")
if status == "fail":
    print("BUG: no_consensus → fail (should be escalated)")
elif status == "escalated":
    print("OK: no_consensus → escalated")
