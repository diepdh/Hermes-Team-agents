"""
Workspace management cho Hermes Phase 0.5.

Mỗi workspace là một thư mục độc lập chứa dữ liệu dự án (artifacts, tasks,
logs, rubrics). Code lõi của Hermes cài đặt ở một nơi, dữ liệu workspace ở
nơi khác do ngườidùng chỉ định.

Thứ tự ưu tiên xác định workspace root:
    1. Tham số `root` truyền vào Workspace(...)
    2. Biến môi trường HERMES_WORKSPACE
    3. Thư mục hiện hành os.getcwd()
"""

import json
import os
import pathlib
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Workspace:
    """Đại diện cho một workspace Hermes."""

    root: pathlib.Path

    def __init__(self, root: str | pathlib.Path | None = None):
        resolved = (
            root
            or os.environ.get("HERMES_WORKSPACE")
            or os.getcwd()
        )
        self.root = pathlib.Path(resolved).resolve()
        self.hermes_dir = self.root / ".hermes"
        self.artifact_dir = self.hermes_dir / "artifacts"
        self.task_dir = self.hermes_dir / "tasks"
        self.rubric_dir = self.hermes_dir / "rubrics"
        self.log_dir = self.hermes_dir / "logs"

    def ensure_initialized(self) -> None:
        """Tạo cấu trúc thư mục và file index nếu chưa tồn tại."""
        for d in (self.artifact_dir, self.task_dir, self.rubric_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)

        for index_file in (self.artifact_dir / "index.json", self.task_dir / "index.json"):
            if not index_file.exists():
                index_file.write_text("{}", encoding="utf-8")

        config_path = self.hermes_dir / "config.json"
        if not config_path.exists():
            config = {
                "workspace_name": self.root.name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "hermes_version": "1.0",
            }
            config_path.write_text(
                json.dumps(config, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    @property
    def artifact_index_path(self) -> pathlib.Path:
        return self.artifact_dir / "index.json"

    @property
    def task_index_path(self) -> pathlib.Path:
        return self.task_dir / "index.json"

    @property
    def config_path(self) -> pathlib.Path:
        return self.hermes_dir / "config.json"

    def relative(self, path: pathlib.Path) -> pathlib.Path:
        """Trả về path tương đối so với workspace root."""
        return pathlib.Path(path).resolve().relative_to(self.root)
