import shutil
import uuid
import json
from pathlib import Path

from config import get_manifest_root
from directory_manager import DirectoryManager
from registry import (
    delete_registry_entry,
    ensure_manifest_layout,
    registry_file_path,
    script_file_path,
    utc_now_iso,
    write_registry_entry,
)
from history_manager import HistoryManager
from registry import permanently_delete_registry_entry


class ScriptManager:
    def __init__(self, manifest_root: str | Path | None = None):
        self.manifest_root = Path(manifest_root) if manifest_root else get_manifest_root()
        self.history_manager = HistoryManager(self.manifest_root)

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
            "total_runs": 0,
            "successful_runs": 0,
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

        # Place in directory hierarchy
        folder_id = payload.get("folder_id") or None
        DirectoryManager(self.manifest_root).add_script(script_uuid, folder_id)

        # Log the script addition to history
        self.history_manager.log_script_added(entry)

        return entry

    def delete_script(self, script_uuid: str) -> None:
        # Soft-delete: record previous folder, remove from directory tree, mark trashed, and log
        registry_path = registry_file_path(self.manifest_root, script_uuid)
        try:
            entry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"uuid": script_uuid}
        except Exception:
            entry = {"uuid": script_uuid}

        # Record where it was deleted from
        try:
            folder_id = DirectoryManager(self.manifest_root).find_folder_of_script(script_uuid)
        except Exception:
            folder_id = None
        entry["trashed_from_folder"] = folder_id

        # Persist the folder info before marking trashed
        try:
            write_registry_entry(self.manifest_root, entry)
        except Exception:
            pass

        # Remove from directory (so it disappears from lists)
        try:
            DirectoryManager(self.manifest_root).remove_script(script_uuid)
        except Exception:
            pass

        # Mark trashed in registry
        delete_registry_entry(self.manifest_root, script_uuid)

        # Record trash event in history
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
        entry["script_path"] = str(script_file_path(self.manifest_root, script_uuid))
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
        """
        Log a script execution to history.
        
        Args:
            script_uuid: UUID of the script that was run
            script_data: Full script metadata
            runtime_values: Dict of runtime variable values
            execution_log: Complete execution output
            success: Whether execution was successful
            exit_code: Exit code from the script
            
        Returns:
            The logged action data
        """
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

        # Read original folder before clearing trash metadata
        original_folder_id = entry.pop("trashed_from_folder", None)
        entry.pop("trashed", None)
        entry.pop("trashed_at", None)
        entry["lastupdated_datetime_stamp"] = utc_now_iso()

        write_registry_entry(self.manifest_root, entry)

        # Re-add to directory at original location; fall back to root if folder gone
        dm = DirectoryManager(self.manifest_root)
        if original_folder_id and dm.get_folder_name(original_folder_id) is None:
            original_folder_id = None
        dm.add_script(script_uuid, original_folder_id)

        try:
            self.history_manager.log_script_restored(entry)
        except Exception:
            pass

        return entry

    def permanently_delete_script(self, script_uuid: str) -> None:
        """Permanently remove script files and registry, and remove from directory."""
        permanently_delete_registry_entry(self.manifest_root, script_uuid)
        DirectoryManager(self.manifest_root).remove_script(script_uuid)
