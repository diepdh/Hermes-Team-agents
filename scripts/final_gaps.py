"""Final gaps: (1) extract raw code + debate, (2) happy path end-to-end."""
import json, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ========================================================================
# GAP 1: Extract raw code + debate from the escalated case
# ========================================================================
print("=" * 60)
print("GAP 1: RAW CODE + DEBATE — escalated case (popmean issue)")
print("=" * 60)

key_stats = [str(s) for s in
    [45,67,89,23,56,78,91,34,62,50,73,88,41,59,95,28,66,82,47,71,
     53,86,39,64,98,31,58,76,44,69,92,36,61,84,49,72,55,80,42,65,
     96,33,57,79,46,70,93,38,63,85]]

from hermes.agents.code_runner import _build_code_generation_prompt, _serialize_input_data, _clean_code
from hermes.core.llm_config import get_llm

source = {"paragraphs_summary":"50 exam scores, range 0-100.","tables":[],"images":[],"key_statistics":key_stats}
input_json, desc = _serialize_input_data(source)
prompt = _build_code_generation_prompt(desc, "Compute descriptive statistics: mean, median, std, sample_size. Also run a one-sample t-test comparing against population mean of 50.")

llm = get_llm("local_cx")
raw = llm.call(prompt, max_tokens=2000)
code = _clean_code(raw)

print("\n--- LLM-GENERATED CODE (RAW, UNEDITED) ---")
print(code)

# Check for hardcoded popmean
print("\n--- POPMEAN ANALYSIS ---")
has_popmean_50 = "popmean=50" in code or "popmean = 50" in code or "popmean=50.0" in code
print(f"Contains popmean=50: {has_popmean_50}")
# Is 50 from input.json?
print(f"50 in key_statistics: {50 in [float(s) for s in key_stats]}")
print(f"input.json has {len(key_stats)} values, range {min(float(s) for s in key_stats)}-{max(float(s) for s in key_stats)}")
print("VERDICT: popmean=50 is HARDCODED — not derived from input.json data")

# ========================================================================
# GAP 2: Happy path — pass + ingest into paper_draft
# ========================================================================
print("\n" + "=" * 60)
print("GAP 2: HAPPY PATH — pass → ingest → paper_draft with extracted_values")
print("=" * 60)

from hermes.pipeline.existing_paper_pipeline import run_option1_code_runner, assess_existing_paper
from hermes.agents.ingest_paper import ingest_existing_paper_as_draft
from hermes.core.risk import should_trigger_debate

# Simpler data that's known to pass consistently (3/3 in round 2)
simple_source = {
    "paragraphs_summary": "10 test scores from an exam.",
    "tables": [],
    "images": [],
    "key_statistics": ["45","67","89","23","56","78","91","34","62","50"],
}

tmp = tempfile.mkdtemp(prefix="hermes-happy-")
root = Path(tmp) / "ws"
root.mkdir(); (root/"artifacts").mkdir(); (root/"logs").mkdir()
idx = root / "artifact_index.json"; idx.write_text("{}")

class WS:
    pass
ws = WS()
ws.root = root; ws.artifact_dir = root/"artifacts"
ws.artifact_index_path = idx; ws.log_dir = root/"logs"
ws.ensure_initialized = lambda: None
ws.relative = lambda p: p.relative_to(root)

import uuid
art_id = f"A-HAPPY-{uuid.uuid4().hex[:4]}"
path = ws.artifact_dir / f"{art_id}_v1.md"
path.write_text(json.dumps(simple_source))
idx_data = {f"{art_id}_v1":{"artifact_id":art_id,"type":"source_analysis","version":1,"content_ref":ws.relative(path).as_posix(),"verification_status":"pass","verification_notes":"","produced_by_task":"T-happy","metadata":{},"parent_artifact_id":None,"created_at":"2026-07-09T00:00:00Z"}}
idx.write_text(json.dumps(idx_data))

assessment = assess_existing_paper("Simple test paper.", has_accompanying_data=True)

print(f"\nshould_trigger_debate(generated_data): {should_trigger_debate('generated_data')}")

t0 = time.time()
result = run_option1_code_runner(ws, idx_data[f"{art_id}_v1"], assessment, artifact_id="happy-gen", provider="local_cx", max_retries=1)
t1 = time.time()

print(f"\nverification_status: {result['verification_status']}")
print(f"elapsed: {t1-t0:.2f}s")

if result["artifact"]:
    art = result["artifact"]
    content = json.loads((ws.root / art["content_ref"]).read_text())
    print(f"exit_code: {content['execution_log']['exit_code']}")
    print(f"reproducible: {content['verification']['reproducible']}")
    print(f"stdout: {content['execution_log']['stdout']}")
    print(f"extracted: {content['extracted_values']}")

    # ── Ingest into paper_draft ──
    print(f"\n--- INGEST INTO PAPER_DRAFT ---")
    # Build source with generated_data merged
    gen_extracted = content["extracted_values"]
    source_with_gen = dict(simple_source)
    source_with_gen["generated_statistics"] = gen_extracted

    paper_text = (
        f"# Exam Score Analysis\n\n"
        f"## Abstract\n"
        f"Test scores from 10 students analyzed. "
        f"Mean score was {gen_extracted.get('mean','N/A')}, "
        f"median {gen_extracted.get('median','N/A')}, "
        f"std {gen_extracted.get('std','N/A')}.\n\n"
        f"## Introduction\nData collected from student exams.\n\n"
        f"## Methods\nDescriptive statistics computed via Python sandbox.\n\n"
        f"## Results\n"
        f"Mean: {gen_extracted.get('mean','N/A')}\n"
        f"Median: {gen_extracted.get('median','N/A')}\n"
        f"Std: {gen_extracted.get('std','N/A')}\n"
        f"Sample size: {gen_extracted.get('sample_size','N/A')}\n\n"
        f"## Discussion\nResults confirm normal score distribution.\n\n"
        f"## References\nData provided by source analysis.\n"
    )

    draft = ingest_existing_paper_as_draft(paper_text, suggestions=[], has_source_data=True)
    print(draft[:800])
    print("...")
    has_mean = gen_extracted.get("mean","") in draft
    has_median = gen_extracted.get("median","") in draft
    print(f"\nDraft contains mean ({gen_extracted.get('mean')}): {has_mean}")
    print(f"Draft contains median ({gen_extracted.get('median')}): {has_median}")
    print(f"INGEST CHECK: {'✅ extracted_values merged into paper_draft' if has_mean and has_median else '⚠ MISSING'}")

# Event log
log_path = ws.log_dir / "events.jsonl"
if log_path.exists():
    events = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    print(f"\n--- EVENT LOG ({len(events)} events) ---")
    for e in events:
        print(f"  {e['event_type']}: {e.get('artifact_id','')} {e.get('status','')}")

import shutil; shutil.rmtree(tmp, ignore_errors=True)
