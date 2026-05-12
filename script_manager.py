import shutil
import uuid
import json
from pathlib import Path

from config import get_manifest_root
from directory_manager import DirectoryManager
from registry import (
    delete_registry_entry,
    ensure_manifest_layout,
    inject_current_version_fields,
    permanently_delete_registry_entry,
    permanently_delete_version_file,
    registry_file_path,
    script_file_path,
    utc_now_iso,
    write_registry_entry,
)
from history_manager import HistoryManager


class ScriptManager:
    def __init__(self, manifest_root: str | Path | None = None):
        self.manifest_root = Path(manifest_root) if manifest_root else get_manifest_root()
        self.history_manager = HistoryManager(self.manifest_root)

    def set_manifest_root(self, manifest_root: str | Path) -> None:
        self.manifest_root = Path(manifest_root)

    # ── Save (new script) ─────────────────────────────────────────────────────

    def save_script(self, payload: dict) -> dict:
        source_path = Path(payload["script_path"])
        if source_path.suffix.lower() != ".py":
            raise ValueError("Only .py files can be registered.")

        ensure_manifest_layout(self.manifest_root)

        script_uuid = uuid.uuid4().hex
        file_uuid_v1 = uuid.uuid4().hex

        dest_path = script_file_path(self.manifest_root, file_uuid_v1)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)

        timestamp = utc_now_iso()
        entry = {
            "name": payload.get("name", "").strip(),
            "uuid": script_uuid,
            "created_at": timestamp,
            "lastrun_time": "",
            "lastupdated_datetime_stamp": timestamp,
            "success_rate": "",
            "total_runs": 0,
            "successful_runs": 0,
            "current_version": 1,
            "environment_refs": payload.get("environment_refs", []),
            "versions": {
                "1": {
                    "file_uuid": file_uuid_v1,
                    "description": payload.get("description", "").strip(),
                    "input_variables": payload.get("input_variables", []),
                    "config_variable": payload.get("config_variable", []),
                    "output_variable": payload.get("output_variable", []),
                    "dependencies": payload.get("dependencies", []),
                    "help_file_path": payload.get("help_file_path", "").strip(),
                    "version_created_at": timestamp,
                    "trashed": False,
                }
            },
        }

        try:
            write_registry_entry(self.manifest_root, entry)
        except Exception:
            if dest_path.exists():
                dest_path.unlink()
            raise

        inject_current_version_fields(self.manifest_root, entry)

        folder_id = payload.get("folder_id") or None
        DirectoryManager(self.manifest_root).add_script(script_uuid, folder_id)

        self.history_manager.log_script_added(entry)
        return entry

    # ── Version control ───────────────────────────────────────────────────────

    def add_version(self, script_uuid: str, payload: dict) -> dict:
        """Add a new version to an existing script and make it the active version."""
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry entry not found for script {script_uuid}")

        entry = json.loads(registry_path.read_text(encoding="utf-8"))

        source_path = Path(payload["script_path"])
        if source_path.suffix.lower() != ".py":
            raise ValueError("Only .py files can be registered.")

        versions = entry.get("versions", {})
        max_ver = max((int(k) for k in versions.keys()), default=0)
        new_ver = max_ver + 1

        file_uuid = uuid.uuid4().hex
        dest_path = script_file_path(self.manifest_root, file_uuid)
        shutil.copy2(source_path, dest_path)

        timestamp = utc_now_iso()
        versions[str(new_ver)] = {
            "file_uuid": file_uuid,
            "description": payload.get("description", "").strip(),
            "input_variables": payload.get("input_variables", []),
            "config_variable": payload.get("config_variable", []),
            "output_variable": payload.get("output_variable", []),
            "dependencies": payload.get("dependencies", []),
            "help_file_path": payload.get("help_file_path", "").strip(),
            "version_created_at": timestamp,
            "trashed": False,
        }

        entry["versions"] = versions
        entry["current_version"] = new_ver
        entry["lastupdated_datetime_stamp"] = timestamp
        new_name = payload.get("name", "").strip()
        if new_name:
            entry["name"] = new_name

        if "environment_refs" in payload:
            entry["environment_refs"] = payload.get("environment_refs", [])
        entry.setdefault("environment_refs", [])

        write_registry_entry(self.manifest_root, entry)
        inject_current_version_fields(self.manifest_root, entry)
        return entry

    def set_active_version(self, script_uuid: str, version_num: int) -> dict:
        """Switch the active (current) version — used for rollback."""
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry entry not found for script {script_uuid}")

        entry = json.loads(registry_path.read_text(encoding="utf-8"))
        ver_str = str(version_num)
        versions = entry.get("versions", {})

        if ver_str not in versions:
            raise ValueError(f"Version {version_num} does not exist")
        if versions[ver_str].get("trashed"):
            raise ValueError(f"Version {version_num} is trashed — restore it first")

        entry["current_version"] = version_num
        entry["lastupdated_datetime_stamp"] = utc_now_iso()

        write_registry_entry(self.manifest_root, entry)
        inject_current_version_fields(self.manifest_root, entry)
        return entry

    def delete_version(self, script_uuid: str, version_num: int) -> dict:
        """Trash a specific version. Switches current_version to the latest remaining one."""
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry entry not found for script {script_uuid}")

        entry = json.loads(registry_path.read_text(encoding="utf-8"))
        versions = entry.get("versions", {})
        active = [int(k) for k, v in versions.items() if not v.get("trashed")]

        if len(active) <= 1:
            # Last active version — trash the whole script instead
            self.delete_script(script_uuid)
            return entry

        ver_str = str(version_num)
        if ver_str in versions:
            versions[ver_str]["trashed"] = True
            versions[ver_str]["trashed_at"] = utc_now_iso()

        # Switch to latest remaining active version
        remaining = sorted([v for v in active if v != version_num], reverse=True)
        entry["current_version"] = remaining[0] if remaining else active[0]
        entry["lastupdated_datetime_stamp"] = utc_now_iso()

        write_registry_entry(self.manifest_root, entry)
        inject_current_version_fields(self.manifest_root, entry)
        return entry

    def restore_version(self, script_uuid: str, version_num: int) -> dict:
        """Restore a trashed version and make it the active version."""
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry entry not found for script {script_uuid}")

        entry = json.loads(registry_path.read_text(encoding="utf-8"))
        ver_str = str(version_num)
        versions = entry.get("versions", {})

        if ver_str not in versions:
            raise ValueError(f"Version {version_num} does not exist")

        versions[ver_str]["trashed"] = False
        versions[ver_str].pop("trashed_at", None)
        entry["current_version"] = version_num
        entry["lastupdated_datetime_stamp"] = utc_now_iso()

        write_registry_entry(self.manifest_root, entry)
        inject_current_version_fields(self.manifest_root, entry)
        return entry

    def permanently_delete_version(self, script_uuid: str, version_num: int) -> None:
        """Permanently remove a specific trashed version's file and registry entry."""
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        if not registry_path.exists():
            return

        entry = json.loads(registry_path.read_text(encoding="utf-8"))
        versions = entry.get("versions", {})
        ver_str = str(version_num)

        if ver_str not in versions:
            return

        file_uuid = versions[ver_str].get("file_uuid")
        if file_uuid:
            permanently_delete_version_file(self.manifest_root, file_uuid)

        del versions[ver_str]
        entry["versions"] = versions

        if versions:
            write_registry_entry(self.manifest_root, entry)
        else:
            registry_path.unlink()
            DirectoryManager(self.manifest_root).remove_script(script_uuid)

    # ── Script lifecycle ──────────────────────────────────────────────────────

    def delete_script(self, script_uuid: str) -> None:
        """Soft-delete: record folder, remove from directory tree, mark trashed."""
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        try:
            entry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"uuid": script_uuid}
        except Exception:
            entry = {"uuid": script_uuid}

        try:
            folder_id = DirectoryManager(self.manifest_root).find_folder_of_script(script_uuid)
        except Exception:
            folder_id = None
        entry["trashed_from_folder"] = folder_id

        try:
            write_registry_entry(self.manifest_root, entry)
        except Exception:
            pass

        try:
            DirectoryManager(self.manifest_root).remove_script(script_uuid)
        except Exception:
            pass

        delete_registry_entry(self.manifest_root, script_uuid)

        try:
            self.history_manager.log_script_trashed(entry)
        except Exception:
            pass

    def record_run_result(self, script_uuid: str, success: bool) -> dict:
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry entry not found for script {script_uuid}")

        try:
            entry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid registry entry for script {script_uuid}") from exc

        total_runs = int(entry.get("total_runs", 0)) + 1
        successful_runs = int(entry.get("successful_runs", 0)) + (1 if success else 0)

        entry["lastrun_time"] = utc_now_iso()
        entry["successful_runs"] = successful_runs
        entry["total_runs"] = total_runs
        entry["success_rate"] = f"{(successful_runs / total_runs) * 100:.1f}%"
        entry["lastupdated_datetime_stamp"] = utc_now_iso()

        write_registry_entry(self.manifest_root, entry)
        inject_current_version_fields(self.manifest_root, entry)
        entry["registry_path"] = str(registry_path)
        return entry

    def log_script_run(
        self,
        script_uuid: str,
        script_data: dict,
        runtime_values: dict,
        execution_log: str,
        success: bool,
        exit_code: int = 0,
    ) -> dict:
        return self.history_manager.log_script_run(
            script_data, runtime_values, execution_log, success, exit_code
        )

    def restore_script(self, script_uuid: str) -> dict:
        """Restore a soft-deleted script (clear `trashed`)."""
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry entry not found for script {script_uuid}")

        try:
            entry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid registry entry for script {script_uuid}") from exc

        if not entry.get("trashed"):
            return entry

        original_folder_id = entry.pop("trashed_from_folder", None)
        entry.pop("trashed", None)
        entry.pop("trashed_at", None)
        entry["lastupdated_datetime_stamp"] = utc_now_iso()

        write_registry_entry(self.manifest_root, entry)

        dm = DirectoryManager(self.manifest_root)
        if original_folder_id and dm.get_folder_name(original_folder_id) is None:
            original_folder_id = None
        dm.add_script(script_uuid, original_folder_id)

        try:
            self.history_manager.log_script_restored(entry)
        except Exception:
            pass

        inject_current_version_fields(self.manifest_root, entry)
        return entry

    def get_script_environment_refs(self, script_uuid: str) -> list[str]:
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        if not registry_path.exists():
            return []

        try:
            entry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        refs = entry.get("environment_refs", [])
        return [str(ref).strip() for ref in refs if str(ref).strip()]

    def set_script_environment_refs(self, script_uuid: str, environment_refs: list[str]) -> dict:
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry entry not found for script {script_uuid}")

        try:
            entry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid registry entry for script {script_uuid}") from exc

        entry["environment_refs"] = [str(ref).strip() for ref in environment_refs if str(ref).strip()]
        entry["lastupdated_datetime_stamp"] = utc_now_iso()
        write_registry_entry(self.manifest_root, entry)
        inject_current_version_fields(self.manifest_root, entry)
        return entry

    def permanently_delete_script(self, script_uuid: str) -> None:
        """Permanently remove all script version files, registry entry, and directory listing."""
        permanently_delete_registry_entry(self.manifest_root, script_uuid)
        DirectoryManager(self.manifest_root).remove_script(script_uuid)
