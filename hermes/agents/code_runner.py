"""Code Runner subagent for Phase 5.7b.

Generates Python statistical computation code via LLM, validates it with
AST-based sandbox scan, executes it twice for reproducibility verification,
and produces a ``generated_data`` artifact for the pipeline.

Key principles (per reviewer spec B):
  - Artifact has 3 independent sections: code, execution_log, extracted_values.
  - Code is run TWICE in isolated workspaces → reproducibility = hash match.
  - Values are extracted from stdout via regex (rule-based, no LLM).
  - Static scan failures → save artifact with violations (checker fails rubric).
  - Timeout / infrastructure failures → ``escalated`` (per principle 10).
  - This module saves the artifact and returns it; it does NOT self-judge
    pass/fail.  Final status is determined by ``check_generated_data`` in
    ``verifier.py`` + ``finalize_verification()`` + auto-Debate (risk=critical).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from hermes.core.llm_config import get_llm
from hermes.core.sandbox import (
    ALLOWED_MODULES,
    DEFAULT_EXTRACTION_PATTERNS,
    _extract_values,
    detect_input_reading,
    run_double_sandbox,
    validate_code_safety,
)


# ============================================================================
# LLM prompt for code generation (B.2)
# ============================================================================

_CODE_GENERATION_SYSTEM_PROMPT = """\
You are a statistical computation code generator for a scientific computing sandbox.

YOUR JOB: write a SINGLE, self-contained Python script that:
1. Reads input data from `input.json` using:
   with open("input.json") as f: data = json.load(f)

2. Performs statistical analysis on the data (mean, std, correlation, t-test,
   regression, etc. — whatever the task requests).

3. Writes results to `output.json` using:
   with open("output.json", "w") as f: json.dump(result_dict, f)

4. Prints key values to stdout in EXACTLY these formats (one per line):
   mean = <number>
   median = <number>
   std = <number>
   p_value = <number>
   correlation = <number>
   r_squared = <number>
   sample_size = <number>
   accuracy = <number>
   Only print the values you actually computed.  Print the raw number after
   the equals sign, no extra text on the same line.

INPUT.JSON SCHEMA (ROUND 4 — real structure, do NOT invent your own):
  The input.json file has these exact keys:
  {{
    "key_statistics": ["42.5", "7.3", "0.05", ...],   // list of number strings
    "tables": [
      [["Group","Score"],["A","4.2"],["B","2.8"], ...],  // first row = headers
      ...
    ],
    "summary": "Description of the data source...",    // human-readable text
    "image_descriptions": [                           // OPTIONAL, may be absent
      {{"index": 0, "description": "Chart showing..."}}
    ]
  }}
  - "key_statistics" are raw numeric values stored as STRINGS — you MUST
    convert them to float before computation.
  - "tables" is a list of tables; each table is a list of rows; the first
    row is the header.  Use the header to identify which columns contain
    which data.  DO NOT assume there are columns named "group_a"/"group_b"
    unless you actually find those headers in the table data.
  - "summary" provides context but may not contain structured numbers.
  - If you need to compare groups, extract them from the TABLES by looking
    at column headers and row values.  DO NOT search for keys named
    "group_a", "group_b", "a", "b" that don't exist in the schema.
  - Handle missing keys gracefully — use data.get("key_statistics", [])
    and check if tables exist before iterating.
  - For group comparison / hypothesis testing, use scipy.stats:
    scipy.stats.ttest_ind(group_a, group_b, equal_var=False) for independent t-test.
    scipy.stats.f_oneway(...) for one-way ANOVA.
    Prefer scipy's implementations over manual calculation to avoid errors.

RULES (violations will cause your code to be REJECTED):
- ONLY use modules from this whitelist: {allowed_modules}
- NEVER use: os, subprocess, sys, importlib, ctypes, pickle, socket, http, urllib, requests, shutil, pathlib, glob
- NEVER call: eval(), exec(), compile(), __import__(), open() with any path other than "input.json", "output.json", or "execution.log"
- NEVER access dunder attributes like .__class__, .__bases__, .__subclasses__, .__globals__, .__code__
- If you need random numbers, set a FIXED seed: random.seed(42) or np.random.seed(42)
- Do NOT hardcode sample data — read everything from input.json
- Do NOT import anything outside the whitelist above
- Do NOT invent data structures that don't match the schema above
"""


def _build_code_generation_prompt(
    input_data_description: str,
    analysis_request: str,
) -> str:
    """Build the system+user prompt for LLM code generation.

    Args:
        input_data_description: Human-readable description of available data
                                (from source_analysis).
        analysis_request: What analysis to perform (from assessment suggestions).
    """
    allowed = ", ".join(sorted(ALLOWED_MODULES))
    system = _CODE_GENERATION_SYSTEM_PROMPT.format(allowed_modules=allowed)

    user = f"""\
INPUT DATA DESCRIPTION:
{input_data_description}

ANALYSIS REQUEST:
{analysis_request}

Write a complete Python script that reads input.json, performs the requested
analysis, writes results to output.json, and prints key statistics to stdout.

The input.json file is ALREADY present in the current working directory.
Your script will be executed in a sandbox with a 60-second timeout.
Any import outside the whitelist will cause immediate rejection.

Return ONLY the Python code, no explanations, no markdown fences."""
    return system + "\n\n" + user


# ============================================================================
# Data serialization
# ============================================================================


def _serialize_input_data(
    source_analysis: dict[str, Any],
    existing_paper_assessment: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Convert source_analysis into input.json content and a description.

    Args:
        source_analysis: The verified source_analysis artifact content.
        existing_paper_assessment: Optional assessment for context.

    Returns:
        (input_json_string, human_readable_description).
    """
    # Extract numeric data from source_analysis
    key_stats = source_analysis.get("key_statistics", []) or []
    tables = source_analysis.get("tables", []) or []
    summary = source_analysis.get("paragraphs_summary", "") or ""
    images = source_analysis.get("images", []) or []

    # Build structured input
    input_data: dict[str, Any] = {
        "key_statistics": [str(s) for s in key_stats],
        "tables": tables,
        "summary": summary,
    }

    # Include image descriptions if present
    if images:
        input_data["image_descriptions"] = [
            {"index": i, "description": img.get("description", "")}
            for i, img in enumerate(images)
        ]

    input_json = json.dumps(input_data, ensure_ascii=False, indent=2)

    # Build description for the LLM prompt
    desc_parts = [f"Data summary: {summary}"] if summary else []
    if key_stats:
        desc_parts.append(
            f"Key statistics ({len(key_stats)} values): "
            f"{', '.join(str(s) for s in key_stats[:10])}"
        )
    if tables:
        desc_parts.append(f"Tables available: {len(tables)}")
    if images:
        desc_parts.append(f"Image descriptions available: {len(images)}")

    # Add assessment suggestions if available
    if existing_paper_assessment:
        suggestions = existing_paper_assessment.get("option_2_suggestions", [])
        if suggestions:
            desc_parts.append(
                f"Suggested analyses: {'; '.join(suggestions)}"
            )

    description = "\n".join(desc_parts) if desc_parts else summary
    return input_json, description


# ============================================================================
# Main entry point
# ============================================================================


def run_code_runner(
    workspace,
    source_analysis_artifact: dict[str, Any],
    existing_paper_assessment_artifact: dict[str, Any] | None = None,
    artifact_id: str | None = None,
    provider: str = "local_cx",
    sandbox_timeout: int = 60,
    sandbox_base_dir: str | None = None,
) -> dict[str, Any]:
    """Run the full code_runner lifecycle: generate → scan → double-run → save.

    Args:
        workspace: Workspace instance (from hermes.core.workspace).
        source_analysis_artifact: Verified source_analysis artifact record
            (must have verification_status == "pass").
        existing_paper_assessment_artifact: Optional assessment artifact
            for LLM context.
        artifact_id: Unique artifact ID (auto-generated if None).
        provider: LLM provider key.
        sandbox_timeout: Hard timeout per sandbox run (seconds).
        sandbox_base_dir: Parent directory for sandbox workspaces.

    Returns:
        The generated_data artifact record from save_artifact().

    Raises:
        ValueError: If source_analysis is not verified.
        RuntimeError: On LLM call failure.
    """
    from hermes.core.storage import save_artifact, read_artifact_content
    from hermes.core.events import log_event

    workspace.ensure_initialized()

    # ── Step 0: Verify source_analysis is verified ─────────────────────
    verification_status = source_analysis_artifact.get("verification_status", "pending")
    if verification_status != "pass":
        raise ValueError(
            f"source_analysis artifact {source_analysis_artifact.get('artifact_id')} "
            f"has verification_status='{verification_status}', must be 'pass'. "
            f"Refusing to run code on unverified data."
        )

    if artifact_id is None:
        artifact_id = f"generated-data-{uuid.uuid4().hex[:8]}"

    # ── Step 1: Read source_analysis content ───────────────────────────
    source_content_str = read_artifact_content(workspace, source_analysis_artifact)
    try:
        source_analysis = json.loads(source_content_str)
    except json.JSONDecodeError:
        source_analysis = {"paragraphs_summary": source_content_str}

    # Parse assessment if provided
    assessment = None
    if existing_paper_assessment_artifact:
        try:
            assessment_content = read_artifact_content(
                workspace, existing_paper_assessment_artifact
            )
            assessment = json.loads(assessment_content)
        except (json.JSONDecodeError, Exception):
            assessment = None

    # ── Step 2: Serialize input data ───────────────────────────────────
    input_json, data_description = _serialize_input_data(source_analysis, assessment)

    # ── Step 3: Generate code via LLM ──────────────────────────────────
    analysis_request = (
        "Perform statistical analysis on the provided data. "
        "Compute descriptive statistics (mean, median, std, sample size). "
        "If there are multiple groups or variables, compute correlations "
        "and statistical tests where appropriate."
    )
    if assessment and assessment.get("option_2_suggestions"):
        suggestions = assessment["option_2_suggestions"]
        analysis_request = (
            f"Perform the following analyses based on reviewer suggestions: "
            f"{'; '.join(suggestions)}. "
            f"Also compute basic descriptive statistics."
        )

    prompt = _build_code_generation_prompt(data_description, analysis_request)

    llm = get_llm(provider)
    try:
        code = llm.call(prompt, max_tokens=2000)
    except Exception as exc:
        log_event(workspace, "code_runner_error", {
            "artifact_id": artifact_id,
            "error": f"LLM call failed: {exc}",
        })
        raise RuntimeError(f"LLM code generation failed: {exc}") from exc

    # Clean up markdown code fences if LLM wrapped code in them
    code = _clean_code(code)

    # ── Step 4: Static scan ────────────────────────────────────────────
    static_safe, static_violations = validate_code_safety(code)
    reads_input = detect_input_reading(code)

    if not static_safe:
        # Code failed static scan — save artifact with violations,
        # do NOT attempt execution (saves resources, avoids running
        # code we already know is dangerous).
        log_event(workspace, "code_runner_static_scan_failed", {
            "artifact_id": artifact_id,
            "violation_count": len(static_violations),
        })
        payload = {
            "code": code,
            "execution_log": {
                "stdout": "",
                "stderr": f"Static scan failed — code not executed. "
                          f"Violations: {'; '.join(static_violations)}",
                "exit_code": -2,
                "elapsed_seconds": 0,
                "timeout": False,
            },
            "extracted_values": {},
            "extraction_method": "regex — rule-based, no LLM interpretation",
            "static_scan_result": {
                "passed": False,
                "violations": static_violations,
                "reads_input": reads_input,
            },
            "verification": {
                "input_hash": "",
                "output_hash_1": "",
                "output_hash_2": "",
                "reproducible": False,
                "sandbox_workspace_A": "",
                "sandbox_workspace_B": "",
            },
        }
        return save_artifact(
            workspace=workspace,
            artifact_id=artifact_id,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            artifact_type="generated_data",
            produced_by_task=f"code-runner-{artifact_id}",
            metadata={
                "static_scan_passed": False,
                "violation_count": len(static_violations),
            },
        )

    # ── Step 5: Double-run sandbox ─────────────────────────────────────
    if sandbox_base_dir is None:
        sandbox_base_dir = str(Path(workspace.root) / ".hermes" / "sandbox-runs")

    try:
        sandbox_result = run_double_sandbox(
            code=code,
            input_json_content=input_json,
            timeout=sandbox_timeout,
            base_workspace_dir=sandbox_base_dir,
        )
    except Exception as exc:
        # Subprocess infrastructure failure → escalated (principle 10)
        log_event(workspace, "code_runner_infrastructure_error", {
            "artifact_id": artifact_id,
            "error": f"Sandbox infrastructure failed: {exc}",
        })
        raise RuntimeError(
            f"Sandbox infrastructure failure for {artifact_id}: {exc}. "
            f"This is an infrastructure error — pipeline should escalate."
        ) from exc

    # Check for timeout (infrastructure limit)
    timeout_occurred = sandbox_result["execution_log"].get("timeout", False)

    # ── Step 6: Extract values from log (already done by run_double_sandbox,
    #           but we also check if extraction matched anything) ───────
    extracted = sandbox_result["extracted_values"]

    # ── Step 7: Save artifact ──────────────────────────────────────────
    payload = {
        "code": sandbox_result["code"],
        "execution_log": sandbox_result["execution_log"],
        "extracted_values": extracted,
        "extraction_method": sandbox_result.get(
            "extraction_method",
            "regex — rule-based, no LLM interpretation",
        ),
        "static_scan_result": {
            "passed": True,
            "violations": [],
            "reads_input": reads_input,
        },
        "verification": sandbox_result["verification"],
        "_timeout": timeout_occurred,  # signal for checker (infra → escalated)
    }

    log_event(workspace, "code_runner_completed", {
        "artifact_id": artifact_id,
        "reproducible": sandbox_result["verification"].get("reproducible", False),
        "exit_code": sandbox_result["execution_log"].get("exit_code"),
        "timeout": timeout_occurred,
        "extracted_keys": list(extracted.keys()),
    })

    return save_artifact(
        workspace=workspace,
        artifact_id=artifact_id,
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        artifact_type="generated_data",
        produced_by_task=f"code-runner-{artifact_id}",
        metadata={
            "static_scan_passed": True,
            "reproducible": sandbox_result["verification"].get("reproducible", False),
            "timeout": timeout_occurred,
            "extraction_count": len(extracted),
        },
    )


# ============================================================================
# Helpers
# ============================================================================


def _clean_code(raw: str) -> str:
    """Strip markdown code fences if the LLM wrapped code in ```python ... ```."""
    text = raw.strip()
    # Remove leading ```python or ```
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
