import json
from datetime import datetime, timezone
from pathlib import Path
from config import get_manifest_root
from registry import utc_now_iso


class HistoryManager:
    """Manages execution history and script addition history in history.json"""

    def __init__(self, manifest_root: str | Path | None = None):
        self.manifest_root = Path(manifest_root) if manifest_root else get_manifest_root()
        self.history_file = self.manifest_root / "history.json"

    def _ensure_history_file(self) -> None:
        """Ensure history.json exists with proper structure."""
        if not self.history_file.exists():
            initial_data = {"action_count": 0, "actions": []}
            self._write_history(initial_data)

    def _read_history(self) -> dict:
        """Read current history from file."""
        self._ensure_history_file()
        try:
            return json.loads(self.history_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"action_count": 0, "actions": []}

    def _write_history(self, data: dict) -> None:
        """Write history to file atomically."""
        temporary_path = self.history_file.with_suffix(".json.tmp")
        temporary_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary_path.replace(self.history_file)

    def log_script_added(self, script_data: dict) -> dict:
        """
        Log when a script is added to the system.
        
        Args:
            script_data: Dictionary containing script metadata (name, uuid, description, etc.)
            
        Returns:
            The logged action data with action number
        """
        history = self._read_history()
        action_num = history["action_count"] + 1

        action = {
            "action_number": action_num,
            "action_type": "script_added",
            "timestamp": utc_now_iso(),
            "script_name": script_data.get("name", ""),
            "script_uuid": script_data.get("uuid", ""),
            "script_description": script_data.get("description", ""),
            "details": {
                "input_variables": script_data.get("input_variables", []),
                "config_variables": script_data.get("config_variable", []),
                "output_variables": script_data.get("output_variable", []),
                "dependencies": script_data.get("dependencies", []),
                "help_file_path": script_data.get("help_file_path", ""),
            },
        }

        history["action_count"] = action_num
        history["actions"].append(action)
        self._write_history(history)

        return action

    def log_script_trashed(self, script_data: dict, reason: str | None = None) -> dict:
        """Log when a script is trashed (soft-deleted)."""
        history = self._read_history()
        action_num = history["action_count"] + 1

        action = {
            "action_number": action_num,
            "action_type": "script_trashed",
            "timestamp": utc_now_iso(),
            "script_name": script_data.get("name", ""),
            "script_uuid": script_data.get("uuid", ""),
            "details": {"reason": reason},
        }

        history["action_count"] = action_num
        history["actions"].append(action)
        self._write_history(history)

        return action

    def log_script_restored(self, script_data: dict, reason: str | None = None) -> dict:
        """Log when a script is restored from trash."""
        history = self._read_history()
        action_num = history["action_count"] + 1

        action = {
            "action_number": action_num,
            "action_type": "script_restored",
            "timestamp": utc_now_iso(),
            "script_name": script_data.get("name", ""),
            "script_uuid": script_data.get("uuid", ""),
            "details": {"reason": reason},
        }

        history["action_count"] = action_num
        history["actions"].append(action)
        self._write_history(history)

        return action

    def log_script_run(
        self,
        script_data: dict,
        runtime_values: dict,
        execution_log: str,
        success: bool,
        exit_code: int = 0,
    ) -> dict:
        """
        Log when a script is executed.
        
        Args:
            script_data: Dictionary containing script metadata
            runtime_values: Dict of variable names to their runtime values
            execution_log: Full execution output/log from the script run
            success: Whether the script completed successfully
            exit_code: Exit code from the script
            
        Returns:
            The logged action data with action number
        """
        history = self._read_history()
        action_num = history["action_count"] + 1

        # Parse runtime values to separate by category
        inputs = {}
        configs = {}
        outputs = {}

        for var_name, var_spec in runtime_values.items():
            var_data = {"value": var_spec.get("value"), "type": var_spec.get("type")}
            category = var_spec.get("category", "").lower()

            if category == "input":
                inputs[var_name] = var_data
            elif category == "config":
                configs[var_name] = var_data
            elif category == "output":
                outputs[var_name] = var_data

        action = {
            "action_number": action_num,
            "action_type": "script_run",
            "timestamp": utc_now_iso(),
            "script_name": script_data.get("name", ""),
            "script_uuid": script_data.get("uuid", ""),
            "success": success,
            "exit_code": exit_code,
            "execution_log": execution_log,
            "runtime_values": {
                "input_variables": inputs,
                "config_variables": configs,
                "output_variables": outputs,
            },
            "script_metadata": {
                "description": script_data.get("description", ""),
                "dependencies": script_data.get("dependencies", []),
            },
        }

        history["action_count"] = action_num
        history["actions"].append(action)
        self._write_history(history)

        return action

    def get_all_actions(self) -> list[dict]:
        """Get all actions sorted from newest to oldest."""
        history = self._read_history()
        # Sort by action_number descending (newest first)
        return sorted(history.get("actions", []), key=lambda x: x.get("action_number", 0), reverse=True)

    def get_actions_for_script(self, script_uuid: str) -> list[dict]:
        """Get all actions for a specific script, sorted newest to oldest."""
        history = self._read_history()
        actions = [
            a for a in history.get("actions", [])
            if a.get("script_uuid") == script_uuid
        ]
        return sorted(actions, key=lambda x: x.get("action_number", 0), reverse=True)

    def get_action_by_number(self, action_number: int) -> dict | None:
        """Get a specific action by its number."""
        history = self._read_history()
        for action in history.get("actions", []):
            if action.get("action_number") == action_number:
                return action
        return None

    def get_statistics(self) -> dict:
        """Get overall statistics about all actions."""
        history = self._read_history()
        actions = history.get("actions", [])

        total_actions = len(actions)
        total_added = len([a for a in actions if a.get("action_type") == "script_added"])
        total_runs = len([a for a in actions if a.get("action_type") == "script_run"])
        successful_runs = len([a for a in actions if a.get("action_type") == "script_run" and a.get("success")])

        return {
            "total_actions": total_actions,
            "total_scripts_added": total_added,
            "total_script_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": total_runs - successful_runs,
        }
