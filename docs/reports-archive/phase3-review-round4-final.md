# Hermes Engineering OS — Phase 3 Review Round 4 (Final)

**Date:** 2026-07-06
**Status:** ✅ SẴN SÀNG ĐÓNG
**Commit:** `c553e37`
**Tests:** 87/87 pass

---

## Mục 1a — Grep xác nhận code persist

```
$ grep -n "save_artifact\|store.save" hermes/pipeline/full_lecture_pipeline.py
39:from hermes.core.storage import save_artifact, read_artifact_content
77:    verdict_artifact = save_artifact(
132:    artifact = save_artifact(
197:        artifact = save_artifact(
```

**Line 77** là dòng persist `debate_verdict` vào Artifact Store — đúng vị trí trong `_maybe_run_debate()`, ngay sau khi `run_debate_review()` trả về và trước khi gọi `finalize_verification()`.

---

## Mục 1b — Test xác nhận artifact thật sự nằm trong store

### Tên test: `test_debate_verdict_persisted_to_store_after_debate`

Nằm trong `tests/test_phase3_debate.py`.

### Nội dung test

```python
def test_debate_verdict_persisted_to_store_after_debate(tmp_path):
    """After _maybe_run_debate, the verdict must be retrievable from
    the Artifact Store using the same API the approve command uses."""
    # 1. Tạo workspace + artifact gốc (mô phỏng run_stage)
    # 2. Mock run_debate_review → consensus_pass
    # 3. Gọi _maybe_run_debate() THẬT (không mock hàm này)
    # 4. ĐỌC LẠI TỪ STORE THẬT:
    verdict_from_store = get_artifact(ws, "lecture-debate-test-debate")
    assert verdict_from_store is not None
    assert verdict_from_store["type"] == "debate_verdict"
    assert verdict_from_store["version"] == 1
    assert verdict_from_store["metadata"]["target_artifact_id"] == "lecture-debate-test"
    assert verdict_from_store["metadata"]["target_artifact_version"] == target["version"]

    # 5. Đọc nội dung thật:
    content = read_artifact_content(ws, verdict_from_store)
    parsed = json.loads(content)
    assert parsed["final_decision"] == "consensus_pass"
    assert "No errors" in parsed["rounds"][0]["opponent_argument"]
```

### Kết quả chạy

```
$ pytest tests/test_phase3_debate.py::test_debate_verdict_persisted_to_store_after_debate -v
======================== 1 passed in 7.58s ========================
```

---

## Mục 1c — Xác nhận người duyệt đọc được debate qua CLI

### Chạy thật

```
$ python -c "
from hermes.core.workspace import Workspace
from hermes.core.storage import list_artifacts, get_artifact, read_artifact_content
...

=== Artifact Store ===
demo-lecture_v1: type=lecture_draft, status=pending
demo-lecture-debate_v1: type=debate_verdict, status=pending

Debate verdict: consensus_pass
Rounds: 1
Opponent: Dong y, khong co loi....
Metadata: target=demo-lecture v1

=== Reviewer workflow ===
1. Artifact demo-lecture v1 escalated → needs approval
2. Reviewer runs: get_artifact(ws, "demo-lecture-debate")
3. Reads verdict → sees opponent agreed → approves
"
```

### Đường đi cho người duyệt

```
get_artifact(workspace, "{target_artifact_id}-debate")
→ trả về artifact type=debate_verdict, version=1
→ metadata.target_artifact_id trỏ về artifact gốc
→ read_artifact_content() trả về toàn bộ proponent/opponent arguments
```

Người duyệt có thể đọc toàn bộ lập luận debate trước khi quyết định `approve`.

---

## Tổng kết test

```
$ pytest tests/ -q
87 passed in 7.78s
```

| Phase | Tests |
|---|---|
| Phase 0 | 11 |
| Phase 1 | 10 |
| Phase 2 | 24 |
| Phase 2 human-gate | 6 |
| Phase 3 risk | 16 |
| Phase 3 debate | 20 |
| **Tổng** | **87** |

---

## Commit history

```
c553e37 test(phase3): add debate_verdict persistence test
e5f9774 fix(phase3): persist debate_verdict to Artifact Store + 3 standalone tests
62b979b feat(phase3): risk matrix + debate review agent
7d47254 chore(phase3): snapshot before Phase 3
```

---

## Kết luận

Cả 3 bằng chứng đều xác nhận:

1. **Code:** `save_artifact()` được gọi tại line 77 của `full_lecture_pipeline.py`
2. **Test:** `test_debate_verdict_persisted_to_store_after_debate` đọc lại từ store thật, assert type/version/metadata/nội dung
3. **CLI:** `get_artifact(ws, "{id}-debate")` → `read_artifact_content()` — người duyệt có đường đi cụ thể để xem lập luận debate

**Phase 3 sẵn sàng đóng. Chờ reviewer xác nhận.**
