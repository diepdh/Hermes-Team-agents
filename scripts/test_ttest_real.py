"""Final LLM exercise: real t-test with raw observation data + scipy.

Group A: [72,68,81,75,70,79,83,76,74,71,69,77,80,73,78,82,75,68,79,85,72,70,76,80,74]
Group B: [85,79,88,82,86,91,84,87,83,90,86,85,89,82,88,84,90,87,85,92,86,83,89,84,88]
"""
import json, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.agents.code_runner import _build_code_generation_prompt, _serialize_input_data, _clean_code
from hermes.core.sandbox import validate_code_safety, run_double_sandbox, detect_input_reading
from hermes.core.llm_config import get_llm

# Raw observation data — 25 scores per group
group_a = [72,68,81,75,70,79,83,76,74,71,69,77,80,73,78,82,75,68,79,85,72,70,76,80,74]
group_b = [85,79,88,82,86,91,84,87,83,90,86,85,89,82,88,84,90,87,85,92,86,83,89,84,88]

source_content = {
    "paragraphs_summary": (
        f"Experiment comparing Group A (control, n=25) vs Group B (treatment, n=25). "
        f"Individual scores provided in tables."
    ),
    "tables": [
        [["Group", "Score"]] + [["A", str(s)] for s in group_a] + [["B", str(s)] for s in group_b]
    ],
    "images": [],
    "key_statistics": [str(s) for s in group_a + group_b],
}

input_json, desc = _serialize_input_data(source_content)

prompt = _build_code_generation_prompt(
    desc,
    "Compare Group A vs Group B using an independent samples t-test. "
    "Extract group scores from the tables using the 'Group' and 'Score' columns. "
    "Use scipy.stats.ttest_ind(group_a_scores, group_b_scores, equal_var=False). "
    "Print: mean, std, sample_size for each group, plus p_value from the t-test. "
    "Also print t_statistic if you compute it."
)

llm = get_llm("local_cx")
results = []

for n in range(1, 3):
    print(f"\n--- RUN {n}/2 ---")
    tmp = tempfile.mkdtemp(prefix=f"hermes-ttest-{n}-")
    r = {"run": n}
    try:
        raw = llm.call(prompt, max_tokens=2000)
        code = _clean_code(raw)
        safe, vs = validate_code_safety(code)
        r["scan"] = safe
        if not safe:
            r["error"] = f"scan fail: {vs[:3]}"
            results.append(r); import shutil; shutil.rmtree(tmp,ignore_errors=True); continue

        s = run_double_sandbox(code, input_json, timeout=60, base_workspace_dir=tmp)
        log = s["execution_log"]
        r["exit_code"] = log["exit_code"]
        r["reproducible"] = s["verification"]["reproducible"]
        r["stdout"] = log["stdout"]
        r["stderr"] = log["stderr"]
        r["extracted"] = s["extracted_values"]
        r["code"] = code if log["exit_code"]==0 and s["verification"]["reproducible"] else None
        print(f"  scan={'PASS' if safe else 'FAIL'} exit={log['exit_code']} repr={s['verification']['reproducible']}")
        print(f"  stdout: {log['stdout'][:200]}")
        print(f"  extracted: {s['extracted_values']}")
    except Exception as e:
        r["error"] = str(e)
        print(f"  ERROR: {e}")
    results.append(r)
    import shutil; shutil.rmtree(tmp,ignore_errors=True)

print(f"\n=== SUMMARY ===")
success = [r for r in results if r.get('scan') and r.get('exit_code')==0 and r.get('reproducible')]
print(f"Complete success: {len(success)}/2")

if success:
    r = success[0]
    print(f"\n--- SUCCESS RUN #{r['run']} ---")
    print("[CODE (first 1000 chars)]")
    print((r.get("code") or "")[:1000])
    print("\n[STDOUT]")
    print(r["stdout"])
    print("\n[EXTRACTED]")
    print(json.dumps(r["extracted"], indent=2))

# Manual verification
import numpy as np
from scipy import stats
a = np.array(group_a, dtype=float)
b = np.array(group_b, dtype=float)
t_stat, p_val = stats.ttest_ind(a, b, equal_var=False)
print("\n=== MANUAL VERIFICATION (outside sandbox) ===")
print(f"Group A: mean={np.mean(a):.4f}, std={np.std(a,ddof=1):.4f}, n={len(a)}")
print(f"Group B: mean={np.mean(b):.4f}, std={np.std(b,ddof=1):.4f}, n={len(b)}")
print(f"t_statistic={t_stat:.6f}, p_value={p_val:.6f}")
