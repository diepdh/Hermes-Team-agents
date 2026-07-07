# Hermes Engineering OS — Phase 3 Final Report

**Date:** 2026-07-06
**Commit:** `62b979b` (hoàn chỉnh Phase 3)
**Snapshot trước Phase 3:** `7d47254`
**Coder Agent:** tự thực hiện theo hướng dẫn reviewer

---

## 1. Kết quả test (76/76 pass)

```
======================= 76 passed, 83 warnings in 6.65s =======================
```

**Phân bố:**
- Phase 0: 11 tests
- Phase 1: 10 tests
- Phase 2: 24 tests
- Phase 2 human-gate: 6 tests
- **Phase 3 risk: 9 tests (MỚI)**
- **Phase 3 debate: 16 tests (MỚI)**
- **Tổng: 76 tests**

Log đầy đủ từ lệnh `pytest -v`:

```
tests/test_phase0.py::test_schema_valid_task PASSED
tests/test_phase0.py::test_schema_invalid_task_missing_field PASSED
tests/test_phase0.py::test_rubric_schema PASSED
tests/test_phase0.py::test_state_machine_valid_transition PASSED
tests/test_phase0.py::test_state_machine_invalid_transition PASSED
tests/test_phase0.py::test_state_machine_verified_terminal PASSED
tests/test_phase0.py::test_artifact_versioning PASSED
tests/test_phase0.py::test_update_verification PASSED
tests/test_phase0.py::test_two_workspaces_isolated PASSED
tests/test_phase0.py::test_workspace_is_portable PASSED
tests/test_phase0.py::test_cli_init PASSED
tests/test_phase1.py::test_verifier_scores_complete_artifact PASSED
tests/test_phase1.py::test_verifier_fails_missing_citations PASSED
tests/test_phase1.py::test_verifier_fails_missing_summary PASSED
tests/test_phase1.py::test_verifier_fails_missing_gaps PASSED
tests/test_phase1.py::test_pipeline_mocked_kickoff_passes_first_attempt PASSED
tests/test_phase1.py::test_pipeline_passes_first_attempt PASSED
tests/test_phase1.py::test_pipeline_retry_then_pass PASSED
tests/test_phase1.py::test_pipeline_escalates_after_max_retries PASSED
tests/test_phase1.py::test_llm_config_registry PASSED
tests/test_phase1.py::test_rubric_criteria_names_match_verifier PASSED
tests/test_phase2.py::test_verify_artifact_dispatches_to_correct_checker PASSED
tests/test_phase2.py::test_verify_artifact_raises_for_unknown_type PASSED
tests/test_phase2.py::test_rubric_criteria_names_match_verifier_all_types PASSED
tests/test_phase2.py::test_lit_review_pass_with_good_artifact PASSED
tests/test_phase2.py::test_lit_review_fail_with_missing_sections PASSED
tests/test_phase2.py::test_course_outline_pass_with_good_artifact PASSED
tests/test_phase2.py::test_course_outline_fail_missing_objectives PASSED
tests/test_phase2.py::test_course_outline_fail_missing_session_breakdown PASSED
tests/test_phase2.py::test_lecture_draft_pass_with_good_artifact PASSED
tests/test_phase2.py::test_lecture_draft_fail_short_content PASSED
tests/test_phase2.py::test_lecture_draft_fail_unsupported_claims PASSED
tests/test_phase2.py::test_quiz_bank_pass_with_good_artifact PASSED
tests/test_phase2.py::test_quiz_bank_fail_too_few_questions PASSED
tests/test_phase2.py::test_quiz_bank_fail_missing_answer_key PASSED
tests/test_phase2.py::test_quiz_bank_fail_no_difficulty_variety PASSED
tests/test_phase2.py::test_all_registry_types_have_checker PASSED
tests/test_phase2.py::test_curriculum_designer_agent_initializes PASSED
tests/test_phase2.py::test_content_writer_agent_initializes PASSED
tests/test_phase2.py::test_assessment_builder_agent_initializes PASSED
tests/test_phase2.py::test_editor_agent_initializes PASSED
tests/test_phase2.py::test_curriculum_designer_task_output_file PASSED
tests/test_phase2.py::test_content_writer_task_output_file PASSED
tests/test_phase2.py::test_assessment_builder_task_output_file PASSED
tests/test_phase2.py::test_editor_task_does_not_add_claims PASSED
tests/test_phase2_human_gate.py::test_human_gate_types_defined PASSED
tests/test_phase2_human_gate.py::test_escalated_to_pass_via_update_verification PASSED
tests/test_phase2_human_gate.py::test_non_human_gate_type_stays_pass PASSED
tests/test_phase2_human_gate.py::test_find_verification_record PASSED
tests/test_phase2_human_gate.py::test_approve_command_updates_to_pass PASSED
tests/test_phase2_human_gate.py::test_approve_warns_on_already_pass PASSED
tests/test_phase3_debate.py::test_judge_consensus_is_pure_function PASSED
tests/test_phase3_debate.py::test_judge_consensus_opponent_concession PASSED
tests/test_phase3_debate.py::test_judge_consensus_opponent_concession_english PASSED
tests/test_phase3_debate.py::test_judge_consensus_proponent_concession PASSED
tests/test_phase3_debate.py::test_judge_consensus_continue PASSED
tests/test_phase3_debate.py::test_debate_only_triggers_for_high_critical_risk PASSED
tests/test_phase3_debate.py::test_debate_stops_at_max_3_rounds PASSED
tests/test_phase3_debate.py::test_debate_stops_at_custom_max_rounds PASSED
tests/test_phase3_debate.py::test_no_consensus_maps_to_escalated_not_fail_not_pass PASSED
tests/test_phase3_debate.py::test_consensus_fail_maps_to_fail PASSED
tests/test_phase3_debate.py::test_consensus_pass_maps_to_escalated_for_human_gate PASSED
tests/test_phase3_debate.py::test_consensus_pass_after_round_1_does_not_run_round_2 PASSED
tests/test_phase3_debate.py::test_rubric_criteria_names_match_verifier_debate_verdict PASSED
tests/test_phase3_debate.py::test_build_verdict_consensus_pass PASSED
tests/test_phase3_debate.py::test_build_verdict_no_consensus PASSED
tests/test_phase3_debate.py::test_run_debate_review_output_valid_schema PASSED
tests/test_phase3_risk.py::test_all_artifact_types_have_risk_level PASSED
tests/test_phase3_risk.py::test_effective_threshold_never_below_rubric_base PASSED
tests/test_phase3_risk.py::test_high_risk_floor_applied_when_rubric_base_lower PASSED
tests/test_phase3_risk.py::test_critical_risk_floor_applied PASSED
tests/test_phase3_risk.py::test_low_and_medium_risk_no_floor PASSED
tests/test_phase3_risk.py::test_unknown_artifact_type_defaults_to_medium_not_low PASSED
tests/test_phase3_risk.py::test_finalize_verification_applies_risk_floor PASSED
tests/test_phase3_risk.py::test_finalize_verification_passes_when_score_above_floor PASSED
tests/test_phase3_risk.py::test_risk_matrix_keys_match_risk_adjusted_floor_keys PASSED
======================= 76 passed, 83 warnings in 6.65s =======================
```

---

## 2. Danh sách file thay đổi

| File | Trạng thái | Mô tả |
|---|---|---|
| `hermes/core/risk.py` | **MỚI** | Ma trận rủi ro + RISK_ADJUSTED_FLOOR + get_risk_level/get_effective_threshold |
| `hermes/core/verifier.py` | SỬA | Tích hợp risk matrix vào finalize_verification(); thêm checker debate_verdict |
| `hermes/agents/debate_proponent.py` | **MỚI** | CrewAI Agent — bảo vệ artifact |
| `hermes/agents/debate_opponent.py` | **MỚI** | CrewAI Agent — phản biện artifact |
| `hermes/pipeline/debate_review_task.py` | **MỚI** | Vòng lặp debate (max 3 rounds) + judge_consensus() pure function |
| `hermes/pipeline/full_lecture_pipeline.py` | SỬA | Truyền rubric_pass_threshold vào finalize_verification |
| `hermes/rubrics/R-debate-verdict-v1.json` | **MỚI** | Rubric cho debate_verdict |
| `hermes/rubrics/__init__.py` | SỬA | Đăng ký debate_verdict rubric |
| `schemas/artifact.schema.json` | SỬA | Thêm "debate_verdict" vào enum type |
| `schemas/task.schema.json` | SỬA | Thêm subagent debate_proponent/opponent + max_rounds |
| `tests/test_phase3_risk.py` | **MỚI** | 9 tests cho ma trận rủi ro |
| `tests/test_phase3_debate.py` | **MỚI** | 16 tests cho debate agent |
| `tests/test_phase2.py` | SỬA | Cập nhật registry check để bao gồm debate_verdict |

**Tổng:** 7 file mới, 6 file sửa

---

## 3. Chi tiết ma trận rủi ro (hermes/core/risk.py)

### RISK_MATRIX (7 artifact types)

| Artifact Type | Risk Level | Ghi chú |
|---|---|---|
| `lit_review_md` | low | Nội bộ, rủi ro thấp |
| `verified_content` | low | Đã verify, rủi ro thấp |
| `course_outline` | medium | Trung bình |
| `final_content` | medium | Output cuối |
| `lecture_draft` | **high** | Dùng giảng dạy thật |
| `quiz_bank` | **high** | Đánh giá chính thức |
| `debate_verdict` | **critical** | Quyết định cuối cùng |

### RISK_ADJUSTED_FLOOR

| Risk Level | Floor | Ý nghĩa |
|---|---|---|
| low | 0.0 | Không nâng ngưỡng |
| medium | 0.0 | Không nâng, dùng rubric base |
| **high** | **0.85** | Nâng từ 0.70/0.80 lên 0.85 |
| **critical** | **0.90** | Nâng lên 0.90 |

### Logic chính

```python
def get_risk_level(artifact_type: str) -> str:
    return RISK_MATRIX.get(artifact_type, "medium")  # unknown → medium, KHÔNG low

def get_effective_threshold(artifact_type: str, rubric_base_threshold: float) -> float:
    floor = RISK_ADJUSTED_FLOOR.get(get_risk_level(artifact_type), 0.0)
    return max(rubric_base_threshold, floor)  # chỉ nâng, không hạ
```

---

## 4. Chi tiết sửa finalize_verification() (verifier.py)

**Tham số mới:**
- `rubric_pass_threshold: float | None = None` — để tính effective threshold
- `debate_verdict: dict | None = None` — kết quả debate nếu có

**Luồng quyết định (Phase 3):**
```
1. Tính risk_level + effective_threshold
2. Nếu có rubric_pass_threshold → rubric_pass = score >= effective_threshold
   Ngược lại → dùng rubric_result["passed"] (backward compat)
3. Nếu không pass → "fail"
4. Nếu có debate_verdict:
   - "no_consensus" → "escalated"
   - "consensus_fail" → "fail"
   - "consensus_pass" + HUMAN_GATE → "escalated"
   - "consensus_pass" + không human gate → "pass"
5. Nếu rubric pass + HUMAN_GATE → "escalated"
6. Còn lại → "pass"
```

Kết quả lưu vào verification_notes kèm `risk={risk_level, effective_threshold, rubric_score, ...}` JSON.

---

## 5. Debate Review Agent

### Cấu trúc code

```
hermes/agents/
├── debate_proponent.py      # CrewAI Agent — bảo vệ artifact
├── debate_opponent.py       # CrewAI Agent — phản biện artifact
hermes/pipeline/
└── debate_review_task.py    # Loop điều phối (max 3 rounds)
```

### judge_consensus() — PURE FUNCTION (không LLM, không network)

Pattern matching trên text argument:

| Pattern (opponent) | Kết quả |
|---|---|
| "không có lỗi", "no errors found", "đồng ý với lập luận", "i agree" | `consensus_pass` |
| Pattern (proponent) | |
| "thừa nhận sai sót", "i concede", "không thể bảo vệ" | `consensus_fail` |
| Cả hai cùng "đồng ý"/"agree" | `consensus_pass` |
| Mặc định | `continue` |

### run_debate_review() flow

```python
for round in 1..max_rounds:
    prop_arg = proponent_agent.review(artifact, previous_rounds)
    opp_arg = opponent_agent.review(artifact, previous_rounds)
    rounds.append({proponent_argument, opponent_argument})
    decision = judge_consensus(prop_arg, opp_arg)  # PURE FUNCTION
    if decision in ("consensus_pass", "consensus_fail"):
        return build_verdict(rounds, decision)      # DỪNG SỚM
return build_verdict(rounds, "no_consensus")         # Hết vòng
```

### Tích hợp state machine
- **Không thêm state riêng** cho debate — là sub-bước trong transition `rubric_check → final`
- Chỉ kích hoạt khi `risk_level ∈ {high, critical}` **VÀ** `rubric_pass = True`

### Kết quả debate_verdict mẫu (từ test)

```json
{
  "artifact_type": "debate_verdict",
  "target_artifact_id": "A-early",
  "target_artifact_version": 1,
  "target_artifact_type": "lecture_draft",
  "rounds": [
    {
      "round": 1,
      "proponent_argument": "Proponent defends the artifact strongly.",
      "opponent_argument": "Không có lỗi nào — opponent agrees."
    }
  ],
  "final_decision": "consensus_pass",
  "unresolved_issues": []
}
```

---

## 6. Xác nhận RISK_MATRIX đăng ký đầy đủ

Test `test_all_artifact_types_have_risk_level` đọc toàn bộ artifact type từ `schemas/artifact.schema.json` và assert tất cả đều có trong `RISK_MATRIX`:

| Artifact Type | Schema? | RISK_MATRIX? | Risk |
|---|---|---|---|
| `lit_review_md` | ✓ | ✓ | low |
| `course_outline` | ✓ | ✓ | medium |
| `lecture_draft` | ✓ | ✓ | high |
| `quiz_bank` | ✓ | ✓ | high |
| `verified_content` | ✓ | ✓ | low |
| `final_content` | ✓ | ✓ | medium |
| `debate_verdict` | ✓ (mới thêm) | ✓ | critical |

---

## 7. Việc KHÔNG làm (đúng mục 4 hướng dẫn)

- [x] Không đổi CrewAI — debate dùng CrewAI local crew
- [x] Không sửa `R-quiz-bank-v1.json` — giữ nguyên threshold 0.8
- [x] Không động `local_cx` provider
- [x] Không đếm token bằng tiktoken

---

## 8. Commit history (không rebase)

```
62b979b feat(phase3): risk matrix + debate review agent   ← HOÀN CHỈNH
7d47254 chore(phase3): snapshot before Phase 3             ← SNAPSHOT
c2637f5 chore(phase2): add baseline measurements
dbb2bb0 fix(phase2): pipeline rubric fallback + lambda parameter fix
137da70 fix(packaging): merge core/agents/pipeline into hermes package
6e762f2 wip(phase2): snapshot hermes package before merge
```

---

## 9. Ghi chú về chạy debate thật

Phiên hiện tại không có `OPENCODE_MODEL` trong environment. Để chạy debate thật qua LLM:

```bash
export OPENCODE_MODEL=deepseek-v4-flash
export OPENCODE_BASE_URL=http://localhost:...
export OPENCODE_API_KEY=...
cd hermes/
python -c "
from hermes.pipeline.debate_review_task import run_debate_review
import json
verdict = run_debate_review(
    artifact_content='## Summary...',
    artifact_id='A-debate-test',
    artifact_version=1,
    artifact_type='lecture_draft',
    workdir='/tmp/debate_output'
)
print(json.dumps(verdict, indent=2, ensure_ascii=False))
"
```

---

**Chờ reviewer hướng dẫn tiếp.**
