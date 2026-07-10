"""Unit tests for P5.7b — Sandbox (code execution isolation).

Tests cover:
  - A.1: Pathlib I/O bypass blocked
  - A.2: Builtin aliasing blocked
  - A.3: Dunder-chain jailbreak blocked
  - A.4: 'with open() as f:' idiom detected as reading input.json
  - AST scan (import whitelist/banned, call-level checks)
  - Double-run reproducibility
  - Runtime isolation (timeout, filesystem)
"""

import json
import tempfile
from pathlib import Path

import pytest

from hermes.core.sandbox import (
    ALLOWED_MODULES,
    BANNED_BUILTINS,
    BANNED_MODULES,
    DANGEROUS_DUNDER_ATTRS,
    DEFAULT_EXTRACTION_PATTERNS,
    ReadsInputDetector,
    SandboxValidator,
    _extract_values,
    detect_input_reading,
    run_double_sandbox,
    validate_code_safety,
)


# ============================================================================
# Helpers
# ============================================================================

def _is_safe(code: str) -> tuple[bool, list[str]]:
    return validate_code_safety(code)


def _assert_violation_contains(code: str, substring: str):
    safe, violations = _is_safe(code)
    assert not safe, f"Expected violations for code:\n{code}"
    combined = " | ".join(violations).lower()
    assert substring.lower() in combined, (
        f"Expected violation containing '{substring}', "
        f"got: {violations}"
    )


def _assert_safe(code: str):
    safe, violations = _is_safe(code)
    assert safe, f"Expected safe, got violations: {violations}"


# ============================================================================
# A.1 — Pathlib I/O bypass (Round 2 patch)
# ============================================================================

def test_blocks_pathlib_open_bypass():
    """pathlib.Path(...).open() / .read_text() / .write_text() → REJECT.

    A.1: BANNED_FILE_METHODS catches these regardless of the object type.
    """
    # Path().read_text() bypass
    _assert_violation_contains(
        "from pathlib import Path\nPath('/etc/passwd').read_text()",
        "banned"
    )
    # Path().write_text() bypass
    _assert_violation_contains(
        "from pathlib import Path\nPath('../../secret').write_text('x')",
        "banned"
    )
    # Path().open() bypass
    _assert_violation_contains(
        "from pathlib import Path\nf = Path('input.json').open('r')",
        "banned"
    )
    # import pathlib itself should now be banned
    _assert_violation_contains("import pathlib", "banned")


# ============================================================================
# A.2 — Builtin aliasing (Round 2 patch)
# ============================================================================

def test_blocks_builtin_alias_eval():
    """x = eval; x(...) → REJECT at Name reference (Load context)."""
    _assert_violation_contains("x = eval", "eval")
    _assert_violation_contains("x = exec; x()", "exec")
    _assert_violation_contains("f = compile; f()", "compile")


def test_blocks_builtin_alias_via_assignment():
    """Multiple alias patterns all rejected."""
    _assert_violation_contains("y = eval", "eval")
    _assert_violation_contains("_dangerous = __import__", "__import__")
    _assert_violation_contains("g = globals", "globals")
    _assert_violation_contains("l = locals", "locals")
    _assert_violation_contains("v = vars", "vars")


# ============================================================================
# A.3 — Dunder-chain jailbreak (Round 2 patch)
# ============================================================================

def test_blocks_dunder_subclasses_chain():
    """().__class__.__bases__[0].__subclasses__() → REJECT."""
    _assert_violation_contains(
        "x = ()\ny = x.__class__",
        "__class__"
    )
    _assert_violation_contains(
        "().__bases__",
        "__bases__"
    )
    _assert_violation_contains(
        "''.__class__.__bases__[0].__subclasses__()",
        "__class__"
    )


def test_blocks_dunder_globals_access():
    """func.__globals__ → REJECT."""
    _assert_violation_contains(
        "import json\njson.dumps.__globals__",
        "__globals__"
    )


def test_blocks_dunder_code_closure():
    """func.__code__ / func.__closure__ → REJECT."""
    _assert_violation_contains(
        "def f(): pass\nf.__code__",
        "__code__"
    )
    _assert_violation_contains(
        "def g(): pass\ng.__closure__",
        "__closure__"
    )


# ============================================================================
# A.4 — ReadsInputDetector 'with open()' idiom (Round 2 patch)
# ============================================================================

def test_reads_input_detector_with_statement_idiom():
    """'with open("input.json") as f: json.load(f)' → detected as reading input."""
    code = (
        "import json\n"
        "with open('input.json') as f:\n"
        "    data = json.load(f)\n"
        "    print(data)\n"
    )
    assert detect_input_reading(code), (
        "Should detect 'with open() as f: json.load(f)' pattern"
    )


def test_reads_input_detector_with_statement_multiple_vars():
    """Multiple with statements, var from open should be tracked."""
    code = (
        "import json\n"
        "with open('input.json') as mydata:\n"
        "    content = json.load(mydata)\n"
        "    print(content['key'])\n"
    )
    assert detect_input_reading(code)


def test_reads_input_detector_pandas_read_json():
    """pd.read_json('input.json') is still DETECTED by AST, but import is blocked.

    detect_input_reading runs on the AST independently of import validation.
    Even though pandas is now banned from ALLOWED_MODULES, the AST pattern
    detector still sees the read_json('input.json') call and returns True.
    The actual execution would still fail at static scan (import pandas → reject).
    """
    code = (
        "import pandas as pd\n"
        "df = pd.read_json('input.json')\n"
    )
    assert detect_input_reading(code)  # AST pattern detected
    # But static scan rejects the pandas import:
    safe, violations = validate_code_safety(code)
    assert not safe


def test_reads_input_detector_direct_open():
    """json.load(open('input.json')) → detected (original pattern)."""
    code = "import json\ndata = json.load(open('input.json'))\nprint(data)\n"
    assert detect_input_reading(code)


def test_reads_input_detector_does_not_flag_open_other_file():
    """Code that opens a different file → NOT flagged as reading input."""
    code = "with open('output.json', 'w') as f:\n    f.write('test')\n"
    assert not detect_input_reading(code)


def test_reads_input_detector_without_input_json():
    """Code with with-statement but not input.json → NOT flagged."""
    code = (
        "import json\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump({}, f)\n"
    )
    # This should be safe but open('output.json') is whitelisted
    # ReadsInputDetector only looks for 'input.json' patterns
    assert not detect_input_reading(code)


# ============================================================================
# AST scan — Import checks
# ============================================================================

def test_blocks_import_via_importlib():
    """importlib is in BANNED_MODULES → REJECT at Import level."""
    _assert_violation_contains("import importlib", "banned")
    _assert_violation_contains("from importlib import import_module", "banned")


def test_blocks_ast_bypass_string_concat():
    """__import__('o'+'s') → REJECT at Name reference (A.2) AND module level.

    Even if the string-concat bypasses Import-level checks, A.2 catches
    '__import__' in BANNED_BUILTINS at visit_Name.
    """
    # __import__ is banned at Name reference level
    _assert_violation_contains("x = __import__('os')", "__import__")


def test_blocks_bare_eval_exec_compile():
    """Direct eval/exec/compile → REJECT."""
    _assert_violation_contains("eval('1+1')", "eval")
    _assert_violation_contains("exec('x=1')", "exec")
    _assert_violation_contains("compile('x', '', 'exec')", "compile")


def test_blocks_getattr_builtins():
    """getattr(__builtins__, ...) → REJECT."""
    _assert_violation_contains(
        "getattr(__builtins__, 'eval')('1+1')",
        "getattr"
    )


def test_blocks_open_variable_path():
    """open(variable_path) → REJECT (path must be literal)."""
    _assert_violation_contains("p = 'input.json'\nopen(p)", "must be a string literal")
    _assert_violation_contains("import sys\nopen(sys.argv[1])", "must be a string literal")


# ============================================================================
# AST scan — Module whitelist
# ============================================================================

def test_whitelist_allows_numpy_import():
    """import numpy → ALLOWED."""
    _assert_safe("import numpy\n")


def test_whitelist_allows_scipy_stats():
    """from scipy import stats → ALLOWED (scipy restored round 5)."""
    _assert_safe("from scipy import stats\n")


def test_whitelist_allows_pandas_import():
    """pandas removed from ALLOWED_MODULES — import pandas → REJECT."""
    _assert_violation_contains("import pandas", "allowlist")


def test_blocks_unknown_import():
    """beautifulsoup4 → REJECT (not in ALLOWED, not in BANNED — caught by allowlist)."""
    _assert_violation_contains("import beautifulsoup4", "allowlist")


# ============================================================================
# AST scan — Pandas call-level checks
# ============================================================================

def test_whitelist_call_pandas_read_csv_rejected():
    """pandas not in ALLOWED → REJECT at import level (not call level)."""
    code = "import pandas as pd\npd.read_csv('data.csv')\n"
    _assert_violation_contains(code, "allowlist")


def test_whitelist_call_pandas_read_pickle_rejected():
    """pandas not in ALLOWED → REJECT at import level."""
    code = "import pandas as pd\npd.read_pickle('data.pkl')\n"
    _assert_violation_contains(code, "allowlist")


def test_whitelist_call_pandas_read_json_allowed_for_input_only():
    """pandas not in ALLOWED — even read_json('input.json') is blocked at import."""
    _assert_violation_contains(
        "import pandas as pd\ndf = pd.read_json('input.json')\n",
        "allowlist"
    )


def test_whitelist_call_pandas_DataFrame_allowed():
    """pandas not in ALLOWED → REJECT at import level."""
    _assert_violation_contains(
        "import pandas as pd\ndf = pd.DataFrame({'a': [1,2,3]})\n",
        "allowlist"
    )


# ============================================================================
# AST scan — Numpy call-level checks
# ============================================================================

def test_whitelist_call_numpy_load_nopickle_allowed():
    """np.load(..., allow_pickle=False) → ALLOWED."""
    _assert_safe("import numpy as np\narr = np.load('data.npy', allow_pickle=False)\n")


def test_whitelist_call_numpy_load_with_pickle_rejected():
    """np.load(..., allow_pickle=True) → REJECT."""
    _assert_violation_contains(
        "import numpy as np\narr = np.load('data.npy', allow_pickle=True)\n",
        "allow_pickle"
    )


def test_whitelist_call_numpy_load_pickle_default_rejected():
    """np.load('data.npy') with no allow_pickle → REJECT (default=True)."""
    _assert_violation_contains(
        "import numpy as np\narr = np.load('data.npy')\n",
        "allow_pickle"
    )


def test_whitelist_call_numpy_array_allowed():
    """np.array(...) → ALLOWED."""
    _assert_safe("import numpy as np\narr = np.array([1, 2, 3])\n")


def test_whitelist_call_numpy_mean_std_allowed():
    """np.mean, np.std → ALLOWED."""
    _assert_safe(
        "import numpy as np\n"
        "arr = np.array([1,2,3])\n"
        "m = np.mean(arr)\n"
        "s = np.std(arr)\n"
    )


def test_whitelist_call_scipy_stats_ttest_allowed():
    """scipy.stats.ttest_ind → ALLOWED (scipy restored)."""
    _assert_safe(
        "from scipy import stats\n"
        "import numpy as np\n"
        "a = np.array([1,2,3])\n"
        "b = np.array([4,5,6])\n"
        "r = stats.ttest_ind(a, b)\n"
    )


# ============================================================================
# AST scan — open() path checks
# ============================================================================

def test_sandbox_blocks_absolute_file_write():
    """open('/etc/passwd', 'w') → REJECT."""
    _assert_violation_contains("open('/etc/passwd', 'w')", "absolute")
    _assert_violation_contains("open('C:\\\\temp\\\\test.txt', 'w')", "absolute")


def test_sandbox_blocks_path_traversal():
    """open('../../../file', 'w') → REJECT."""
    _assert_violation_contains("open('../../../secret.txt', 'w')", "path traversal")


def test_sandbox_allows_safe_open():
    """open('input.json'), open('output.json'), open('execution.log') → ALLOWED."""
    _assert_safe("open('input.json')\n")
    _assert_safe("open('output.json', 'w')\n")
    _assert_safe("open('execution.log', 'w')\n")


# ============================================================================
# AST scan — Syntax error handling
# ============================================================================

def test_validate_code_safety_handles_syntax_error():
    """Broken code → not safe, reports syntax error."""
    safe, violations = validate_code_safety("import numpy\nfor x in\n")
    assert not safe
    assert any("Syntax error" in v or "syntax" in v.lower() for v in violations)


# ============================================================================
# ReadsInputDetector — edge cases
# ============================================================================

def test_reads_input_detector_empty_code():
    """Empty code → not reading input."""
    assert not detect_input_reading("")
    assert not detect_input_reading("   \n")


def test_reads_input_detector_no_input_json():
    """Code that reads other files → not flagged."""
    code = "import json\nf = open('config.json')\ndata = json.load(f)\n"
    assert not detect_input_reading(code)


# ============================================================================
# Double-run reproducibility (A.2 — integration tests)
# ============================================================================

def test_double_run_reproducibility_hash_match():
    """Deterministic code → reproducible=True."""
    code = (
        "import json\n"
        "with open('input.json') as f:\n"
        "    data = json.load(f)\n"
        "nums = data['values']\n"
        "mean_val = sum(nums) / len(nums)\n"
        "print(f'mean = {mean_val}')\n"
        "result = {'mean': mean_val}\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump(result, f)\n"
    )
    input_data = json.dumps({"values": [1.0, 2.0, 3.0, 4.0, 5.0]})

    with tempfile.TemporaryDirectory() as tmp:
        result = run_double_sandbox(code, input_data, timeout=30, base_workspace_dir=tmp)

    assert result["verification"]["reproducible"] is True
    assert result["execution_log"]["exit_code"] == 0
    assert "mean" in result["extracted_values"]


def test_double_run_reproducibility_hash_mismatch():
    """Non-deterministic code (random without seed) → reproducible=False."""
    code = (
        "import json\n"
        "import random\n"
        "with open('input.json') as f:\n"
        "    data = json.load(f)\n"
        "result = {'rand': random.random()}\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump(result, f)\n"
    )
    input_data = json.dumps({"values": [1.0, 2.0]})

    with tempfile.TemporaryDirectory() as tmp:
        result = run_double_sandbox(code, input_data, timeout=30, base_workspace_dir=tmp)

    # random.random() without seed → different output each run
    assert result["verification"]["reproducible"] is False


def test_double_run_uses_separate_workspaces():
    """Run A and B must use distinct workspace directories."""
    code = (
        "import json\n"
        "with open('input.json') as f:\n"
        "    d = json.load(f)\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump({'x': d['values'][0]}, f)\n"
    )
    input_data = json.dumps({"values": [42]})

    # Use a persistent temp dir (not TemporaryDirectory context manager)
    # so workspaces survive long enough for path checks (point C — workspaces retained).
    import tempfile as _tmp
    tmp_dir = _tmp.mkdtemp(prefix="hermes-test-sandbox-")
    try:
        result = run_double_sandbox(code, input_data, timeout=30, base_workspace_dir=tmp_dir)

        ws_a = result["verification"]["sandbox_workspace_A"]
        ws_b = result["verification"]["sandbox_workspace_B"]
        assert ws_a != ws_b, f"Workspaces must differ: {ws_a} == {ws_b}"
        assert Path(ws_a).exists(), f"Workspace A should still exist: {ws_a}"
        assert Path(ws_b).exists(), f"Workspace B should still exist: {ws_b}"
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_double_run_timeout_handling():
    """Code with infinite loop → timeout, reproducible=False."""
    code = (
        "import time\n"
        "import json\n"
        "with open('input.json') as f:\n"
        "    d = json.load(f)\n"
        "time.sleep(999)\n"  # will timeout
        "with open('output.json', 'w') as f:\n"
        "    json.dump({}, f)\n"
    )
    input_data = json.dumps({"values": [1]})

    with tempfile.TemporaryDirectory() as tmp:
        result = run_double_sandbox(code, input_data, timeout=2, base_workspace_dir=tmp)

    assert result["verification"]["reproducible"] is False
    assert result["execution_log"].get("timeout") is True or result["execution_log"]["exit_code"] != 0


# ============================================================================
# Sandbox workspace retention (point C)
# ============================================================================

def test_sandbox_workspaces_not_deleted_after_run():
    """Workspaces A and B must persist after run_double_sandbox for audit."""
    code = (
        "import json\n"
        "with open('input.json') as f:\n"
        "    d = json.load(f)\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump({'ok': True}, f)\n"
    )
    input_data = json.dumps({"x": 1})

    with tempfile.TemporaryDirectory() as tmp:
        result = run_double_sandbox(code, input_data, timeout=30, base_workspace_dir=tmp)
        ws_a = result["verification"]["sandbox_workspace_A"]
        ws_b = result["verification"]["sandbox_workspace_B"]

        assert Path(ws_a).is_dir(), f"Workspace A must exist: {ws_a}"
        assert Path(ws_b).is_dir(), f"Workspace B must exist: {ws_b}"

        # input.json should be present in both
        assert (Path(ws_a) / "input.json").exists(), "input.json missing from A"
        assert (Path(ws_b) / "input.json").exists(), "input.json missing from B"


# ============================================================================
# Security: sandbox must NOT see parent env secrets (regression test)
# ============================================================================

def test_sandbox_subprocess_cannot_read_parent_env_secret(tmp_path, monkeypatch):
    """A secret env var in the parent process must NOT be visible inside sandbox.

    Regression guard: round 4 unintentionally changed _run_once() to inherit
    os.environ, exposing API keys/credentials to untrusted sandbox code.
    This test confirms the fix — sandbox runs with a minimal env.
    """
    monkeypatch.setenv("HERMES_TEST_SECRET_DO_NOT_LEAK", "super-secret-value-12345")

    code = (
        "import os\n"
        "secret = os.environ.get('HERMES_TEST_SECRET_DO_NOT_LEAK', 'NOT-FOUND')\n"
        "print(f'secret = {secret}')\n"
        "import json\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump({'secret': secret}, f)\n"
    )

    input_json = '{"values": [1, 2, 3]}'
    import tempfile
    tmp = tempfile.mkdtemp(prefix="hermes-sec-test-")
    try:
        result = run_double_sandbox(code, input_json, timeout=30, base_workspace_dir=tmp)
        stdout = result["execution_log"]["stdout"]
        assert "super-secret-value" not in stdout, (
            f"SECRET LEAKED into sandbox! stdout: {stdout}"
        )
        assert "NOT-FOUND" in stdout or result["execution_log"]["exit_code"] != 0, (
            f"Expected secret to be inaccessible. stdout: {stdout}"
        )
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_sandbox_numpy_works_with_minimal_env(tmp_path):
    """numpy import works in sandbox despite minimal env (stdlib + numpy only).

    Confirms sys.executable's own sys.path includes venv site-packages.
    """
    code = (
        "import json\n"
        "import numpy as np\n"
        "with open('input.json') as f:\n"
        "    data = json.load(f)\n"
        "arr = np.array(data['values'])\n"
        "m = float(np.mean(arr))\n"
        "print(f'mean = {m}')\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump({'mean': m}, f)\n"
    )
    input_json = '{"values": [1.0, 2.0, 3.0, 4.0, 5.0]}'
    import tempfile
    tmp = tempfile.mkdtemp(prefix="hermes-np-test-")
    try:
        result = run_double_sandbox(code, input_json, timeout=30, base_workspace_dir=tmp)
        assert result["execution_log"]["exit_code"] == 0, (
            f"numpy import failed in minimal env: {result['execution_log']['stderr']}"
        )
        assert result["extracted_values"].get("mean") == "3.0"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================================
# Runtime: input.json integrity
# ============================================================================

def test_sandbox_input_json_unchanged_after_execution():
    """input.json content must be identical before and after execution."""
    code = (
        "import json\n"
        "with open('input.json') as f:\n"
        "    d = json.load(f)\n"
        "with open('output.json', 'w') as f:\n"
        "    json.dump({'double': d['value'] * 2}, f)\n"
    )
    input_data = json.dumps({"value": 21})

    with tempfile.TemporaryDirectory() as tmp:
        result = run_double_sandbox(code, input_data, timeout=30, base_workspace_dir=tmp)

        # Read input.json from workspace A and verify
        ws_a = result["verification"]["sandbox_workspace_A"]
        actual_input = (Path(ws_a) / "input.json").read_text()
        assert json.loads(actual_input) == json.loads(input_data), (
            "input.json must not be modified by code"
        )


# ============================================================================
# Extraction patterns
# ============================================================================

def test_extract_values_mean_from_log():
    stdout = "Computing...\nmean = 3.5\nDone."
    extracted = _extract_values(stdout, DEFAULT_EXTRACTION_PATTERNS)
    assert extracted.get("mean") == "3.5"


def test_extract_values_p_value_from_log():
    stdout = "t-test result: p_value = 0.0032"
    extracted = _extract_values(stdout, DEFAULT_EXTRACTION_PATTERNS)
    assert extracted.get("p_value") == "0.0032"


def test_extract_values_empty_when_no_match():
    stdout = "No recognizable patterns here."
    extracted = _extract_values(stdout, DEFAULT_EXTRACTION_PATTERNS)
    assert extracted == {}  # principle 9: don't force data when none exists


def test_extract_values_multiple_patterns():
    stdout = "mean=4.2 median=4.0 std=1.3"
    extracted = _extract_values(stdout, DEFAULT_EXTRACTION_PATTERNS)
    assert extracted.get("mean") == "4.2"
    assert extracted.get("median") == "4.0"
    assert extracted.get("std") == "1.3"


def test_extract_values_no_cross_pattern_collision():
    """Log with similar numbers → each key matches its OWN line, no cross-match.

    Bug regression: sample_size regex `n =` used to match "n =" inside
    "mean = 30", causing sample_size to extract "30" instead of "5".
    The `(?:^|\\n)` anchor + `\\b` word boundary fix prevents this.
    """
    stdout = (
        "mean = 30.5\n"
        "median = 28.0\n"
        "std = 12.3\n"
        "sample_size = 5\n"
    )
    extracted = _extract_values(stdout, DEFAULT_EXTRACTION_PATTERNS)
    assert extracted.get("mean") == "30.5", f"mean should be 30.5, got {extracted.get('mean')}"
    assert extracted.get("median") == "28.0"
    assert extracted.get("std") == "12.3"
    assert extracted.get("sample_size") == "5", (
        f"sample_size should be 5, got {extracted.get('sample_size')}. "
        f"Likely 'n =' regex matched inside 'mean = 30.5'"
    )


# ============================================================================
# Module constant integrity
# ============================================================================

def test_banned_modules_not_in_allowed():
    overlap = BANNED_MODULES & ALLOWED_MODULES
    assert not overlap, f"Modules both banned and allowed: {overlap}"


def test_pathlib_not_in_allowed_modules():
    """A.1: pathlib removed from ALLOWED_MODULES."""
    assert "pathlib" not in ALLOWED_MODULES, (
        "pathlib must not be in ALLOWED_MODULES (A.1)"
    )


def test_banned_builtins_well_defined():
    required = {"eval", "exec", "compile", "__import__", "globals", "locals", "vars"}
    missing = required - BANNED_BUILTINS
    assert not missing, f"BANNED_BUILTINS missing: {missing}"


def test_dangerous_dunder_attrs_covers_sandbox_escape():
    required = {"__class__", "__bases__", "__subclasses__", "__globals__", "__code__"}
    missing = required - DANGEROUS_DUNDER_ATTRS
    assert not missing, f"DANGEROUS_DUNDER_ATTRS missing: {missing}"


# ============================================================================
# False-positive prevention — valid code MUST NOT be blocked (Round 3)
# ============================================================================

def test_allows_dataframe_rename():
    """pd.DataFrame.rename → pandas import blocked, so method call is irrelevant."""
    code = (
        "import pandas as pd\n"
        "df = pd.DataFrame({'a': [1, 2, 3]})\n"
        "df2 = df.rename(columns={'a': 'b'})\n"
    )
    # pandas import is now blocked → code fails at import, not at rename
    safe, violations = validate_code_safety(code)
    assert not safe  # blocked at pandas import
    assert any("allowlist" in v or "pandas" in v.lower() for v in violations)


def test_allows_dataframe_copy():
    """pd.DataFrame.copy → pandas import blocked."""
    code = (
        "import pandas as pd\n"
        "df = pd.DataFrame({'a': [1, 2, 3]})\n"
        "df2 = df.copy()\n"
    )
    safe, violations = validate_code_safety(code)
    assert not safe  # blocked at pandas import


def test_allows_list_remove():
    """list.remove(x) → NOT blocked."""
    code = "x = [1, 2, 3]; x.remove(2)\n"
    _assert_safe(code)


def test_allows_dict_copy():
    """dict.copy() → NOT blocked."""
    code = "d = {'a': 1, 'b': 2}; d2 = d.copy()\n"
    _assert_safe(code)


def test_allows_numpy_array_copy():
    """numpy.ndarray.copy() → NOT blocked."""
    code = (
        "import numpy as np\n"
        "arr = np.array([1, 2, 3])\n"
        "arr2 = arr.copy()\n"
    )
    _assert_safe(code)
