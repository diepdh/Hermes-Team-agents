"""Run real debate review through OpenCode LLM."""
import os, sys, json, tempfile
from pathlib import Path

os.chdir(Path(__file__).parent)

# Ensure .env loads
from dotenv import load_dotenv
load_dotenv()

print(f"HERMES_LLM_PROVIDER={os.environ.get('HERMES_LLM_PROVIDER', 'NOT SET')}")
print(f"OPENCODE_MODEL={os.environ.get('OPENCODE_MODEL', 'NOT SET')}")
print(f"OPENCODE_BASE_URL={os.environ.get('OPENCODE_BASE_URL', 'NOT SET')}")

from hermes.core.llm_config import get_llm_config
cfg = get_llm_config("opencode_go")
print(f"LLM model: {cfg['model']}")

from hermes.pipeline.debate_review_task import run_debate_review

artifact_content = """# Lecture: Introduction to Machine Learning

Machine Learning (ML) is a subset of artificial intelligence that enables systems
to learn and improve from experience without explicit programming.

## Key Concepts
1. **Supervised Learning**: learns from labeled data (e.g., spam filter).
2. **Unsupervised Learning**: finds patterns in unlabeled data (e.g., clustering).
3. **Reinforcement Learning**: agent learns via rewards/penalties.

## Applications
ML powers recommendation systems, autonomous vehicles, medical diagnosis,
and NLP. McKinsey (2020) estimates AI could add $13 trillion to global GDP by 2030.
"""

workdir = tempfile.mkdtemp(prefix="debate_")
print(f"\nWorkdir: {workdir}")

print("Running 1-round debate with real LLM...")
verdict = run_debate_review(
    artifact_content=artifact_content,
    artifact_id="A-debate-real",
    artifact_version=1,
    artifact_type="lecture_draft",
    max_rounds=1,
    workdir=workdir,
)
print("\n=== DEBATE VERDICT (REAL LLM) ===")
print(json.dumps(verdict, indent=2, ensure_ascii=False))
