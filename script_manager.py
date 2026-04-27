import shutil
import uuid
from pathlib import Path

from config import get_manifest_root
from registry import (
    delete_registry_entry,
    ensure_manifest_layout,
    script_file_path,
    utc_now_iso,
    write_registry_entry,
)


class ScriptManager:
    def __init__(self, manifest_root: str | Path | None = None):
        self.manifest_root = Path(manifest_root) if manifest_root else get_manifest_root()

    def set_manifest_root(self, manifest_root: str | Path) -> None:
        self.manifest_root = Path(manifest_root)

    def save_script(self, payload: dict) -> dict:
        source_path = Path(payload["script_path"])
        if source_path.suffix.lower() != ".py":
            raise ValueError("Only .py files can be registered.")

        ensure_manifest_layout(self.manifest_root)

        script_uuid = uuid.uuid4().hex
        copied_script_path = script_file_path(self.manifest_root, script_uuid)
        copied_script_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(source_path, copied_script_path)

        timestamp = utc_now_iso()
        entry = {
            "name": payload.get("name", "").strip(),
            "uuid": script_uuid,
            "description": payload.get("description", "").strip(),
            "input_variables": payload.get("input_variables", []),
            "config_variable": payload.get("config_variable", []),
            "output_variable": payload.get("output_variable", []),
            "dependencies": payload.get("dependencies", []),
            "created_at": timestamp,
            "lastrun_time": "",
            "lastupdated_datetime_stamp": timestamp,
            "success_rate": "",
            "help_file_path": payload.get("help_file_path", "").strip(),
            "current_version": 1,
            "previous_versions": {"1": script_uuid},
        }

        try:
            write_registry_entry(self.manifest_root, entry)
        except Exception:
            if copied_script_path.exists():
                copied_script_path.unlink()
            raise

        entry["script_path"] = str(copied_script_path)
        return entry

    def delete_script(self, script_uuid: str) -> None:
        delete_registry_entry(self.manifest_root, script_uuid)
