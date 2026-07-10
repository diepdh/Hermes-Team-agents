"""Test the previously-failing case: group comparison from tables."""
import json, sys, tempfile
from pathlib import Path

sys.path.insert(0, r"C:\Users\dohuy\Downloads\03. Source code\Hermes Engineerig OS\hermes")

from hermes.agents.code_runner import _build_code_generation_prompt, _serialize_input_data, _clean_code
from hermes.core.sandbox import validate_code_safety, run_double_sandbox, detect_input_reading
from hermes.core.llm_config import get_llm

# SAME DATA that failed in round 1 (group comparison from tables)
source_content = {
    "paragraphs_summary": (
        "Survey of 50 students. Test scores: Group A (n=25): "
        "mean 78.5, std 12.3. Group B (n=25): mean 82.1, std 10.7."
    ),
    "tables": [
        [["Group", "Mean", "SD", "N"],
         ["A", "78.5", "12.3", "25"],
         ["B", "82.1", "10.7", "25"]]
    ],
    "images": [],
    "key_statistics": ["78.5", "82.1", "12.3", "10.7", "25", "25"],
}

input_json, desc = _serialize_input_data(source_content)

for attempt in range(1, 3):
    print(f"\n{'='*50}")
    print(f"ATTEMPT {attempt}/2 — Group comparison")
    print(f"{'='*50}")

    prompt = _build_code_generation_prompt(
        desc,
        "Compare Group A vs Group B. Find the groups from the TABLES by "
        "looking at column headers (first row of each table). Compute means, "
        "stds from the table data. Perform a t-test for the difference. "
        "Print: mean, median, std, p_value, sample_size."
    )

    llm = get_llm("local_cx")
    raw = llm.call(prompt, max_tokens=2000)
    code = _clean_code(raw)
    safe, violations = validate_code_safety(code)
    reads = detect_input_reading(code)

    print(f"Static scan: {'PASS' if safe else 'FAIL'} ({len(violations)} violations)")
    print(f"Reads input.json: {reads}")
    print(f"Code preview: {code[:200]}...")

    if safe:
        tmp = tempfile.mkdtemp(prefix="hermes-group-")
        result = run_double_sandbox(code, input_json, timeout=60, base_workspace_dir=tmp)
        log = result["execution_log"]
        v = result["verification"]

        print(f"exit_code: {log['exit_code']}")
        print(f"reproducible: {v['reproducible']}")
        print(f"--- STDOUT ---")
        print(log["stdout"])
        print(f"--- STDERR (first 300) ---")
        print((log["stderr"] or "(empty)")[:300])
        print(f"--- EXTRACTED ---")
        print(json.dumps(result["extracted_values"], indent=2))
        print(f"--- FULL CODE ---")
        print(code[:1200])

        if log["exit_code"] == 0 and v["reproducible"]:
            print(f"\n✅ SUCCESS on attempt {attempt}!")
            import shutil; shutil.rmtree(tmp, ignore_errors=True)
            break
        else:
            print(f"\n❌ FAIL — trying again with refined prompt...")
            # Refine prompt for retry
            prompt = (
                f"Your previous code failed. RULES: The input.json tables "
                f"field is a list of tables. Each table is a list of lists. "
                f"First row = column headers. Data rows follow. Extract group "
                f"values directly from table rows by row index — DO NOT look "
                f"for dict keys named 'group_a' or 'group_b'. "
                f"Use table[1:] for data rows. "
                f"Example: table = [['Group','Mean','SD','N'],['A','78.5','12.3','25'],['B','82.1','10.7','25']] "
                f"→ group_a_mean = float(table[1][1]), group_b_mean = float(table[2][1]). "
                f"Now regenerated code that does group comparison from the TABLES."
            )
        import shutil; shutil.rmtree(tmp, ignore_errors=True)

print("\nDone.")
