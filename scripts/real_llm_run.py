"""Multi-run LLM exercise — 3 runs with simple analysis (fixed prompt)."""
import json, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.agents.code_runner import _build_code_generation_prompt, _serialize_input_data, _clean_code
from hermes.core.sandbox import validate_code_safety, run_double_sandbox, detect_input_reading
from hermes.core.llm_config import get_llm

source_content = {
    "paragraphs_summary": "Survey data: 10 scores from 0-100.",
    "tables": [],
    "images": [],
    "key_statistics": ["45", "67", "89", "23", "56", "78", "91", "34", "62", "50"],
}
input_json, desc = _serialize_input_data(source_content)
prompt = _build_code_generation_prompt(
    desc,
    "Compute descriptive statistics ONLY: mean, median, std, sample_size. "
    "Use ONLY key_statistics from input.json. Keep it simple."
)

llm = get_llm("local_cx")
results = []

for n in range(1, 4):
    print(f"\n--- RUN {n}/3 ---")
    tmp = tempfile.mkdtemp(prefix=f"llm-run{n}-")
    r = {"run": n}
    try:
        raw = llm.call(prompt, max_tokens=1200)
        code = _clean_code(raw)
        safe, _ = validate_code_safety(code)
        r["scan"] = safe
        if not safe:
            r["error"] = "scan fail"
            results.append(r); import shutil; shutil.rmtree(tmp, ignore_errors=True); continue

        s = run_double_sandbox(code, input_json, timeout=60, base_workspace_dir=tmp)
        log = s["execution_log"]
        r["exit_code"] = log["exit_code"]
        r["reproducible"] = s["verification"]["reproducible"]
        r["stdout"] = log["stdout"]
        r["stderr"] = log["stderr"]
        r["extracted"] = s["extracted_values"]
        r["code"] = code if log["exit_code"] == 0 and s["verification"]["reproducible"] else None
        print(f"  scan={'PASS' if safe else 'FAIL'} exit={log['exit_code']} repr={s['verification']['reproducible']} stdout={log['stdout'][:80]}")
    except Exception as e:
        r["error"] = str(e)
        print(f"  ERROR: {e}")
    results.append(r)
    import shutil; shutil.rmtree(tmp, ignore_errors=True)

print(f"\n=== SUMMARY ===")
print(f"Static scan pass: {sum(1 for r in results if r.get('scan'))}/3")
print(f"exit_code==0: {sum(1 for r in results if r.get('exit_code') == 0)}/3")
print(f"reproducible: {sum(1 for r in results if r.get('reproducible'))}/3")
success = [r for r in results if r.get('scan') and r.get('exit_code') == 0 and r.get('reproducible')]
print(f"Complete success: {len(success)}/3")

if success:
    r = success[0]
    print(f"\n--- SUCCESS RUN #{r['run']} ---")
    print("\n[CODE]")
    print(r.get("code", "(n/a)")[:800])
    print("\n[STDOUT]")
    print(r["stdout"])
    print("\n[EXTRACTED]")
    print(json.dumps(r["extracted"], indent=2))
