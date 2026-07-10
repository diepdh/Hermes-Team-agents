"""Sandbox for safe code execution in Hermes Phase 5.7b.

Defense-in-depth strategy (three layers):

  Layer 1 — AST static scan:              SandboxValidator (ast.NodeVisitor)
  Layer 2 — Runtime isolation:            subprocess.run(timeout, cwd=tempdir)
  Layer 3 — Reproducibility gate:         double-run hash comparison (A.2)

LIMITATION (stated explicitly as required):
  This is static analysis + subprocess isolation, NOT a complete sandbox.
  It blocks the cheapest bypass classes (string-concat import, importlib,
  dunder-chain jailbreaks, builtin aliasing, pathlib I/O).  It does NOT
  block: ctypes memory manipulation, pybind11 native code, or advanced
  escape techniques.  Defense-in-depth helps but cannot guarantee safety
  against a determined adversary.  For P5.7b scope (statistical computation
  code from LLM), this is adequate.

Round 2 patches applied (per reviewer instructions):
  A.1 — Block pathlib .open()/.read_text()/.write_text() etc. via method-name ban
  A.2 — Block builtin aliasing (x = eval; x(...)) via visit_Name
  A.3 — Block dunder-chain jailbreak (__class__, __bases__, __subclasses__, etc.)
  A.4 — Detect 'with open("input.json") as f: json.load(f)' idiom in ReadsInputDetector
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# ============================================================================
# Module-level allow/block lists
# ============================================================================

# Modules allowed for import (whitelist).
# pathlib has been REMOVED (A.1 recommendation) because every I/O method
# on Path objects (open, read_text, write_text, etc.) can bypass the
# builtin-open check, and statistical code does not need pathlib.
ALLOWED_MODULES: frozenset[str] = frozenset({
    # Computation — numpy + scipy available in sandbox venv
    "numpy",
    "scipy", "scipy.stats", "scipy.optimize",

    # Standard library — computation & data
    "json", "math", "statistics", "csv",
    "collections", "itertools", "functools", "operator",
    "re", "datetime",
    "typing", "dataclasses", "enum",
    "copy", "pprint",
    "random",
})

# Banned modules (rejected at Import/ImportFrom level).
BANNED_MODULES: frozenset[str] = frozenset({
    "os", "subprocess", "shutil", "glob",
    "socket", "http", "urllib", "requests",
    "ftplib", "smtplib", "poplib", "imaplib",
    "importlib", "_importlib", "ctypes", "_ctypes",
    "builtins", "_builtins", "__builtins__",
    "pickle", "_pickle", "marshal",
    "sys", "gc", "inspect", "traceback",
    "pathlib",  # A.1 — removed from ALLOWED, banned explicitly
    "tempfile", "signal",
    "multiprocessing", "threading", "concurrent",
    "code", "codeop", "codecs",
    "asyncio", "trio",
    "webbrowser", "antigravity",
    "pdb", "bdb", "profile", "cProfile", "trace",
})

# Builtin names that must NEVER be referenced (even in variable assignment).
# A.2 — visit_Name catches any reference to these.
BANNED_BUILTINS: frozenset[str] = frozenset({
    "eval", "exec", "compile", "__import__",
    "globals", "locals", "vars",
})

# Magic / dunder attributes that allow sandbox escape.
# A.3 — visit_Attribute catches any .attr access to these.
DANGEROUS_DUNDER_ATTRS: frozenset[str] = frozenset({
    "__builtins__", "__class__", "__bases__", "__subclasses__",
    "__globals__", "__code__", "__closure__", "__mro__", "__base__",
    "__import__", "__loader__", "__spec__", "__dict__",
    "__init__", "__new__", "__del__", "__reduce__", "__reduce_ex__",
    "__getstate__", "__setstate__", "__getattr__", "__setattr__",
})

# File I/O method names — rejected on ANY object (A.1, revised round 3).
#
# DESIGN DECISION (round 3): pathlib is already banned at the Import level
# (in BANNED_MODULES), so no Path object can be created.  Layer 2 here
# is defense-in-depth only — catching the scenario where a different
# module exposes a file-object with these methods.  Since layer 1 already
# closes the main route, we keep ONLY names that have zero collision
# with dict / list / pandas.DataFrame / numpy.ndarray methods:
#   - copy   → REMOVED — dict.copy(), list.copy(), pd.DataFrame.copy(), np.ndarray.copy()
#   - rename → REMOVED — pd.DataFrame.rename(columns=...)
#   - remove → REMOVED — list.remove(x)
#   - move   → KEPT — no common non-file method uses this name
#   - stat   → KEPT — no common non-file method uses this name
BANNED_FILE_METHODS: frozenset[str] = frozenset({
    "open", "read_text", "write_text", "read_bytes", "write_bytes",
    "unlink", "touch", "mkdir", "rmdir", "chmod", "chown",
    "symlink_to", "iterdir", "rglob", "glob", "resolve",
    "copytree", "rmtree", "move", "stat",
})

# Pandas call-level blocklist: functions rejected even if pandas import is allowed.
PANDAS_CALL_BLOCKED: frozenset[str] = frozenset({
    "read_csv", "read_excel", "read_pickle", "read_sql", "read_sql_query",
    "read_sql_table", "read_table", "read_fwf", "read_clipboard",
    "read_html", "read_xml", "read_parquet", "read_feather",
    "read_hdf", "read_stata", "read_sas", "read_spss",
    "read_orc", "read_gbq",
    "to_pickle",
})

# ============================================================================
# Layer 1 — AST validator
# ============================================================================


class SandboxValidator(ast.NodeVisitor):
    """AST-based security validator.

    Traverses the AST of generated code and enforces:
      - Module whitelist (ALLOWED_MODULES)
      - Banned module detection (BANNED_MODULES)
      - Banned builtin references (A.2)
      - Dangerous dunder attribute access (A.3)
      - File I/O method calls on any object (A.1)
      - Builtin open() restricted to allowed paths
      - Pandas I/O function restrictions (read_csv etc.)
      - Numpy load() pickle-payload restrictions
    """

    def __init__(self) -> None:
        self.violations: list[str] = []

    # ── Import checks ──────────────────────────────────────────────────

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_module(alias.name, node.lineno, f"import {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if module:
            self._check_module(module, node.lineno, f"from {module} import ...")
        self.generic_visit(node)

    def _check_module(self, name: str, lineno: int, source: str) -> None:
        # Check banned first (superset includes modules we want to block)
        if name in BANNED_MODULES:
            self.violations.append(
                f"Line {lineno}: module '{name}' is banned in sandbox ({source})"
            )
            return
        # Check against whitelist (allow submodules of whitelisted top-level)
        top_level = name.split(".")[0]
        if top_level not in ALLOWED_MODULES and name not in ALLOWED_MODULES:
            self.violations.append(
                f"Line {lineno}: module '{name}' is not in the sandbox "
                f"allowlist ({source})"
            )

    # ── Name reference check (A.2) ─────────────────────────────────────

    def visit_Name(self, node: ast.Name) -> None:
        """Block any reference (Load context) to banned builtins.

        A.2: x = eval; x(...) would bypass visit_Call because func.id == 'x'.
        By rejecting ANY reference to 'eval' in Load context, we catch both
        direct calls and aliasing before the call happens.
        """
        if isinstance(node.ctx, ast.Load) and node.id in BANNED_BUILTINS:
            self.violations.append(
                f"Line {node.lineno}: reference to '{node.id}' is banned "
                f"in sandbox (even in variable assignment)"
            )
        self.generic_visit(node)

    # ── Attribute check (A.3) ──────────────────────────────────────────

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Reject dangerous dunder attributes and banned file-method calls.

        A.3: ().__class__.__bases__[0].__subclasses__() jailbreak.
        A.1: pathlib.Path(...).read_text() I/O bypass.
        """
        # Dunder attrs (A.3)
        if node.attr in DANGEROUS_DUNDER_ATTRS:
            self.violations.append(
                f"Line {node.lineno}: access to '."
                f"{node.attr}' is banned (dunder chain escape vector)"
            )
            # Still visit children — we want ALL violations, not just the first
            self.generic_visit(node)
            return

        # File I/O method names on any object (A.1)
        if node.attr in BANNED_FILE_METHODS:
            self.violations.append(
                f"Line {node.lineno}: calling '."
                f"{node.attr}()' is banned (file I/O method, sandbox escape vector)"
            )
            # Still visit deeper to catch more
            self.generic_visit(node)
            return

        self.generic_visit(node)

    # ── Call checks ────────────────────────────────────────────────────

    def visit_Call(self, node: ast.Call) -> None:
        self._check_direct_banned_builtins(node)
        self._check_getattr_builtins(node)
        self._check_open_path(node)
        self._check_pandas_call(node)
        self._check_numpy_load(node)
        self.generic_visit(node)

    def _check_direct_banned_builtins(self, node: ast.Call) -> None:
        """Block eval(...), exec(...), compile(...), __import__(...).

        Note: A.2 catches aliasing (x = eval) at visit_Name, so we don't
        need to worry about indirect calls here.
        """
        if isinstance(node.func, ast.Name) and node.func.id in BANNED_BUILTINS:
            self.violations.append(
                f"Line {node.lineno}: calling '{node.func.id}()' is banned"
            )

    def _check_getattr_builtins(self, node: ast.Call) -> None:
        """Block getattr(__builtins__, ...) pattern."""
        if not isinstance(node.func, ast.Name):
            return
        if node.func.id != "getattr":
            return
        if len(node.args) < 1:
            return
        arg0 = node.args[0]
        if isinstance(arg0, ast.Name) and arg0.id in ("__builtins__", "builtins"):
            self.violations.append(
                f"Line {node.lineno}: getattr(__builtins__, ...) is banned"
            )

    def _check_open_path(self, node: ast.Call) -> None:
        """Only allow open() with literal sandbox-safe paths.

        Allowed: open("input.json"), open("output.json"), open("execution.log")
        Rejected: open("../..."), open("C:\\..."), open(variable), open(expr)
        """
        if not isinstance(node.func, ast.Name):
            return
        if node.func.id != "open":
            return
        if len(node.args) < 1:
            self.violations.append(
                f"Line {node.lineno}: open() requires a path argument"
            )
            return

        path_arg = node.args[0]
        if not isinstance(path_arg, ast.Constant) or not isinstance(path_arg.value, str):
            self.violations.append(
                f"Line {node.lineno}: open() path must be a string literal, "
                f"not a variable or expression"
            )
            return

        path_str: str = path_arg.value
        # Block absolute paths and parent traversal
        if path_str.startswith("/") or path_str.startswith("\\"):
            self.violations.append(
                f"Line {node.lineno}: open() with absolute path '{path_str}' "
                f"is banned"
            )
            return
        if ".." in path_str:
            self.violations.append(
                f"Line {node.lineno}: open() with path traversal '{path_str}' "
                f"is banned"
            )
            return
        # Check for Windows drive letters
        if len(path_str) >= 2 and path_str[1] == ":":
            self.violations.append(
                f"Line {node.lineno}: open() with absolute Windows path "
                f"'{path_str}' is banned"
            )
            return

        # Allow only sandbox-safe filenames
        safe_names = {"input.json", "output.json", "execution.log"}
        if path_str not in safe_names:
            self.violations.append(
                f"Line {node.lineno}: open() path '{path_str}' not in "
                f"allowed set: {sorted(safe_names)}"
            )

    def _check_pandas_call(self, node: ast.Call) -> None:
        """Block dangerous pandas I/O functions (B.3)."""
        if not isinstance(node.func, ast.Attribute):
            return
        # Only check when called via pd.* or pandas.*
        if not isinstance(node.func.value, ast.Name):
            return
        if node.func.value.id not in ("pd", "pandas"):
            return

        func_name = node.func.attr
        if func_name in PANDAS_CALL_BLOCKED:
            self.violations.append(
                f"Line {node.lineno}: pandas.{func_name}() is blocked in sandbox"
            )
            return

        # read_json: only allowed with literal "input.json"
        if func_name == "read_json":
            if not self._is_literal_arg(node, 0, "input.json"):
                self.violations.append(
                    f"Line {node.lineno}: pd.read_json() only allowed with "
                    f"path='input.json'"
                )

    def _check_numpy_load(self, node: ast.Call) -> None:
        """Block np.load() with allow_pickle=True or unspecified."""
        if not isinstance(node.func, ast.Attribute):
            return
        if not isinstance(node.func.value, ast.Name):
            return
        if node.func.value.id not in ("np", "numpy"):
            return
        if node.func.attr != "load":
            return

        # Check keyword arguments for allow_pickle
        allow_pickle_explicit_false = False
        for kw in node.keywords:
            if kw.arg == "allow_pickle":
                if isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    allow_pickle_explicit_false = True
                break

        if not allow_pickle_explicit_false:
            self.violations.append(
                f"Line {node.lineno}: np.load() requires explicit "
                f"'allow_pickle=False' in sandbox"
            )

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _is_literal_arg(node: ast.Call, index: int, expected: str) -> bool:
        """Check if positional argument at index is a string literal matching expected."""
        if len(node.args) <= index:
            return False
        arg = node.args[index]
        return (
            isinstance(arg, ast.Constant)
            and isinstance(arg.value, str)
            and arg.value == expected
        )


def validate_code_safety(code: str) -> tuple[bool, list[str]]:
    """Validate code safety via AST scan.

    Returns:
        (is_safe, list_of_violations).  is_safe = (len(violations) == 0).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error in generated code: {e}"]
    validator = SandboxValidator()
    validator.visit(tree)
    return len(validator.violations) == 0, validator.violations


# ============================================================================
# ReadsInputDetector — A.4 patched for 'with open() as f:' idiom
# ============================================================================


class ReadsInputDetector(ast.NodeVisitor):
    """Detect whether code reads data from input.json.

    Recognizes three patterns:
      1. json.load(open("input.json"))           — direct
      2. with open("input.json") as f:            — A.4 with-statement idiom
           json.load(f)
      3. pd.read_json("input.json")               — pandas
    """

    def __init__(self) -> None:
        self.found: bool = False
        # Variables assigned from open("input.json") in with statements:
        #   with open("input.json") as f:   →  _vars_from_input_open.add("f")
        self._vars_from_input_open: set[str] = set()

    def visit_With(self, node: ast.With) -> None:
        """Track variables bound to open('input.json') in with statements.

        A.4: This runs BEFORE visit_Call traverses the with body because
        NodeVisitor visits the With node first, then generic_visit recurses
        into the body.  Test confirms this ordering.
        """
        for item in node.items:
            if (
                isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Name)
                and item.context_expr.func.id == "open"
                and item.context_expr.args
                and isinstance(item.context_expr.args[0], ast.Constant)
                and isinstance(item.context_expr.args[0].value, str)
                and item.context_expr.args[0].value == "input.json"
                and item.optional_vars is not None
                and isinstance(item.optional_vars, ast.Name)
            ):
                self._vars_from_input_open.add(item.optional_vars.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Pattern 1 & 2: json.load(...) — check for direct open() or
        # variable from with statement.
        if self._is_json_load(node):
            if node.args:
                arg = node.args[0]
                # Pattern 1: json.load(open("input.json"))
                if self._is_open_call_with_path(arg, "input.json"):
                    self.found = True
                # Pattern 2: json.load(f) where f was from
                # 'with open("input.json") as f'
                elif (
                    isinstance(arg, ast.Name)
                    and arg.id in self._vars_from_input_open
                ):
                    self.found = True

        # Pattern 3: pd.read_json("input.json") or pandas.read_json("input.json")
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "read_json"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ("pd", "pandas")
        ):
            if (
                node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value == "input.json"
            ):
                self.found = True

        self.generic_visit(node)

    @staticmethod
    def _is_json_load(node: ast.Call) -> bool:
        """Check if call is json.load(...) or json.loads(...)."""
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in ("load", "loads")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "json"
        )

    @staticmethod
    def _is_open_call_with_path(arg_node: ast.AST, expected_path: str) -> bool:
        """Check if arg is open('<expected_path>') call."""
        if not isinstance(arg_node, ast.Call):
            return False
        if not isinstance(arg_node.func, ast.Name):
            return False
        if arg_node.func.id != "open":
            return False
        if not arg_node.args:
            return False
        path_arg = arg_node.args[0]
        return (
            isinstance(path_arg, ast.Constant)
            and isinstance(path_arg.value, str)
            and path_arg.value == expected_path
        )


def detect_input_reading(code: str) -> bool:
    """Return True if code reads from input.json (AST-based detection)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    detector = ReadsInputDetector()
    detector.visit(tree)
    return detector.found


# ============================================================================
# Layer 2+3 — Runtime execution + reproducibility
# ============================================================================

# Default regex patterns for extracting values from execution log.
# These are RULE-BASED — no LLM interpretation.
#
# ROUND 2: Fixed sample_size regex to use (?:^|\\n) anchor so `n =` inside
#          "mean = 30" is not falsely matched as sample_size.
# ROUND 4: Added \\b word-boundary anchors to ALL patterns to prevent
#          cross-pattern collisions (e.g. "median" matching inside a
#          longer word, "std" inside "standardized").
DEFAULT_EXTRACTION_PATTERNS: dict[str, str] = {
    "mean":    r"\bmean\s*[=:]\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)",
    "median":  r"\bmedian\s*[=:]\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)",
    "std":     r"\bstd\s*[=:]\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)",
    "p_value": r"\bp[_ ]value\s*[=:]\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)",
    "correlation": r"\bcorrelation\s*[=:]\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)",
    "r_squared": r"\br[²2][_ ]squared\s*[=:]\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)",
    "sample_size": r"(?:^|\n)\s*(?:sample[_ ]size|n)\s*=\s*(\d+)",
    "accuracy": r"\baccuracy\s*[=:]\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)",
}


def _run_once(
    code: str,
    input_json_content: str,
    timeout: int,
    workspace_dir: str,
) -> dict[str, Any]:
    """Execute code once in an isolated subprocess workspace.

    Args:
        code: Python source code to execute.
        input_json_content: JSON string to write as input.json in the workspace.
        timeout: Hard timeout in seconds.
        workspace_dir: Path to the sandbox workspace directory.

    Returns:
        Dict with stdout, stderr, exit_code, elapsed_seconds, output_json_content.
    """
    ws = Path(workspace_dir)
    ws.mkdir(parents=True, exist_ok=True)

    # Write input.json into the workspace
    input_path = ws / "input.json"
    input_path.write_text(input_json_content, encoding="utf-8")

    # Write the code to a file (safer than -c for long code)
    code_path = ws / "_generated_code.py"
    code_path.write_text(code, encoding="utf-8")

    try:
        # Minimal sandbox env — does NOT inherit parent os.environ.
        # Security: the parent process may hold API keys, credentials,
        # and other secrets.  The sandbox must NEVER see those.
        #
        # Why site-packages still work: sys.executable points to the venv's
        # Python binary, whose sys.path automatically includes the venv's
        # site-packages.  No PATH / PYTHONHOME / VIRTUAL_ENV needed.
        result = subprocess.run(
            [sys.executable, str(code_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ws),
            env={
                "PYTHONPATH": str(ws),
                "PATH": str(Path(sys.executable).parent),
            },
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Execution timed out after {timeout}s",
            "exit_code": -1,
            "elapsed_seconds": timeout,
            "output_json_content": "",
            "timeout": True,
        }

    # Read output.json if it exists
    output_json_content = ""
    output_path = ws / "output.json"
    if output_path.exists():
        try:
            output_json_content = output_path.read_text(encoding="utf-8")
        except Exception:
            output_json_content = ""

    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "elapsed_seconds": timeout if exit_code != 0 else 0,  # approximate
        "output_json_content": output_json_content,
        "timeout": False,
    }


def _compute_sha256(content: str) -> str:
    """Return hex digest of SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def run_double_sandbox(
    code: str,
    input_json_content: str,
    timeout: int = 60,
    base_workspace_dir: str | None = None,
) -> dict[str, Any]:
    """Run code twice in independent sandboxes for reproducibility check (A.2).

    This is the primary entry point for code execution.  It:
      1. Creates two isolated temp workspaces A and B.
      2. Runs code in each.
      3. Computes reproducibility = (sha256(output_A) == sha256(output_B)).
      4. Extracts values from execution log via regex (rule-based, no LLM).

    Workspace retention (point C): workspaces are kept under
    base_workspace_dir/.hermes/sandbox-runs/<task_id>-{A,B}/
    for later audit by Debate Review / Human Gate.  Cleanup is the
    responsibility of a future janitor job (TODO — not in P5.7b scope).

    Args:
        code: Python source to execute.
        input_json_content: JSON string for input.json.
        timeout: Max seconds per run (default 60).
        base_workspace_dir: Parent directory for sandbox workspaces.

    Returns:
        Dict with all execution data for generated_data artifact.
    """
    if base_workspace_dir is None:
        base_workspace_dir = str(Path(tempfile.gettempdir()) / "hermes-sandbox")

    base = Path(base_workspace_dir) / "sandbox-runs"
    base.mkdir(parents=True, exist_ok=True)

    # Use a unique prefix so different tasks don't collide.
    # uuid4 hex instead of timestamp ms — guaranteed unique across parallel runs
    # (reviewer note round 3: time-based prefix risks collision at sub-ms parallelism).
    import uuid
    task_prefix = f"task-{uuid.uuid4().hex[:12]}"

    # ── RUN 1 ─────────────────────────────────────────────────────────
    ws_a = str(base / f"{task_prefix}-A")
    run_a = _run_once(code, input_json_content, timeout, ws_a)

    # ── RUN 2 ─────────────────────────────────────────────────────────
    ws_b = str(base / f"{task_prefix}-B")
    run_b = _run_once(code, input_json_content, timeout, ws_b)

    # ── Compute reproducibility ────────────────────────────────────────
    if run_a["exit_code"] == 0 and run_b["exit_code"] == 0:
        hash_a = _compute_sha256(run_a["output_json_content"])
        hash_b = _compute_sha256(run_b["output_json_content"])
        reproducible = hash_a == hash_b
    else:
        # If either run failed, can't determine reproducibility
        hash_a = ""
        hash_b = ""
        reproducible = False

    input_hash = _compute_sha256(input_json_content)

    # ── Extract values from log (rule-based, no LLM) ───────────────────
    extracted = _extract_values(run_a["stdout"], DEFAULT_EXTRACTION_PATTERNS)

    execution_log = {
        "stdout": run_a["stdout"],
        "stderr": run_a["stderr"],
        "exit_code": run_a["exit_code"],
        "elapsed_seconds": run_a["elapsed_seconds"],
        "timeout": run_a["timeout"],
    }

    return {
        "code": code,
        "execution_log": execution_log,
        "extracted_values": extracted,
        "extraction_method": "regex — rule-based, no LLM interpretation",
        "verification": {
            "input_hash": input_hash,
            "output_hash_1": hash_a,
            "output_hash_2": hash_b,
            "reproducible": reproducible,
            "sandbox_workspace_A": ws_a,
            "sandbox_workspace_B": ws_b,
        },
    }


def _extract_values(
    stdout: str,
    patterns: dict[str, str],
) -> dict[str, str]:
    """Extract numeric values from execution log using regex patterns.

    Rule-based — NO LLM interpretation.  If no pattern matches,
    returns empty dict (principle 9: don't force data when none exists).
    """
    result: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, stdout, re.IGNORECASE)
        if match:
            result[key] = match.group(1)
    return result
