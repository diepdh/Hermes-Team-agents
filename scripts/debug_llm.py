"""Debug: simple LLM call with full stderr capture."""
import json, sys, tempfile
from pathlib import Path

sys.path.insert(0, r"C:\Users\dohuy\Downloads\03. Source code\Hermes Engineerig OS\hermes")

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
raw = llm.call(prompt, max_tokens=1200)
code = _clean_code(raw)
safe, violations = validate_code_safety(code)
reads = detect_input_reading(code)

print("Static scan:", "PASS" if safe else f"FAIL ({len(violations)} violations)")
print("Reads input:", reads)
print("--- CODE (first 600 chars) ---")
print(code[:600])

if safe:
    tmp = tempfile.mkdtemp(prefix="hermes-debug-")
    result = run_double_sandbox(code, input_json, timeout=60, base_workspace_dir=tmp)
    log = result["execution_log"]
    print("\n--- STDOUT ---")
    print(repr(log["stdout"]))
    print("\n--- STDERR (FULL) ---")
    print(log["stderr"])
    print("\nexit_code:", log["exit_code"])
    print("timeout:", log.get("timeout"))
    print("extracted:", result["extracted_values"])
    print("reproducible:", result["verification"]["reproducible"])
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
