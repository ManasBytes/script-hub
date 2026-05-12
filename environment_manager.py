from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from config import get_environment_master_key
from registry import ensure_manifest_layout, utc_now_iso

_TEMPLATE_PATTERN = re.compile(r"{{\s*([A-Za-z0-9_.-]+)\s*}}")


@dataclass(frozen=True)
class EnvironmentValue:
    name: str
    value: object
    is_secret: bool = False


class EnvironmentManager:
    def __init__(self, manifest_root: str | Path):
        self.manifest_root = Path(manifest_root)

    @property
    def environments_dir(self) -> Path:
        ensure_manifest_layout(self.manifest_root)
        path = self.manifest_root / "environments"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def index_path(self) -> Path:
        return self.manifest_root / "env_index.json"

    def _env_path(self, environment_uuid: str) -> Path:
        return self.environments_dir / f"{environment_uuid}.json"

    def _load_index(self) -> dict:
        if not self.index_path.exists():
            return {"version": 1, "environments": []}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("version", 1)
                data.setdefault("environments", [])
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {"version": 1, "environments": []}

    def _save_index(self, index: dict) -> None:
        self.manifest_root.mkdir(parents=True, exist_ok=True)
        tmp = self.index_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.index_path)

    def _load_record(self, environment_uuid: str) -> dict:
        path = self._env_path(environment_uuid)
        if not path.exists():
            raise FileNotFoundError(f"Environment {environment_uuid!r} not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid environment file: {path}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Invalid environment file: {path}")
        data.setdefault("uuid", environment_uuid)
        data.setdefault("variables", {})
        data.setdefault("parent_environment_refs", [])
        data.setdefault("trashed", False)
        return data

    def _save_record(self, record: dict) -> dict:
        record = dict(record)
        record["updated_at"] = utc_now_iso()
        if "uuid" not in record or not str(record["uuid"]).strip():
            record["uuid"] = uuid.uuid4().hex
        record.setdefault("variables", {})
        record.setdefault("parent_environment_refs", [])
        record.setdefault("trashed", False)
        record.setdefault("scope", "global")

        path = self._env_path(str(record["uuid"]))
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

        index = self._load_index()
        environments = [str(env_id) for env_id in index.get("environments", []) if str(env_id).strip()]
        if str(record["uuid"]) not in environments:
            environments.append(str(record["uuid"]))
        index["environments"] = environments
        self._save_index(index)
        return record

    def list_environments(self, include_trashed: bool = False) -> list[dict]:
        index = self._load_index()
        results: list[dict] = []
        for environment_uuid in index.get("environments", []):
            try:
                record = self._load_record(str(environment_uuid))
            except (FileNotFoundError, ValueError):
                continue
            if record.get("trashed") and not include_trashed:
                continue
            results.append(self._public_record(record))
        return results

    def get_environment(self, environment_uuid: str, include_secret_values: bool = False) -> dict:
        record = self._load_record(environment_uuid)
        return self._public_record(record, include_secret_values=include_secret_values)

    def create_environment(
        self,
        name: str,
        variables: dict[str, dict[str, object]] | None = None,
        scope: str = "global",
        scope_id: str | None = None,
        parent_environment_refs: list[str] | None = None,
        description: str = "",
    ) -> dict:
        record = {
            "uuid": uuid.uuid4().hex,
            "name": name.strip(),
            "description": description.strip(),
            "scope": scope,
            "scope_id": scope_id,
            "parent_environment_refs": [str(ref).strip() for ref in (parent_environment_refs or []) if str(ref).strip()],
            "variables": variables or {},
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "trashed": False,
        }
        return self._public_record(self._save_record(record))

    def update_environment(self, environment_uuid: str, **changes) -> dict:
        record = self._load_record(environment_uuid)
        for key, value in changes.items():
            if value is None:
                continue
            if key == "variables":
                record[key] = value
            elif key == "parent_environment_refs":
                record[key] = [str(ref).strip() for ref in value if str(ref).strip()]
            else:
                record[key] = value
        return self._public_record(self._save_record(record))

    def delete_environment(self, environment_uuid: str, permanent: bool = False) -> None:
        path = self._env_path(environment_uuid)
        if not path.exists():
            return

        if permanent:
            path.unlink()
            index = self._load_index()
            index["environments"] = [env_id for env_id in index.get("environments", []) if str(env_id) != environment_uuid]
            self._save_index(index)
            return

        record = self._load_record(environment_uuid)
        record["trashed"] = True
        self._save_record(record)

    def _public_record(self, record: dict, include_secret_values: bool = False) -> dict:
        public = dict(record)
        variables = public.get("variables", {})
        sanitized: dict[str, dict[str, object]] = {}
        for variable_name, payload in variables.items():
            payload = dict(payload or {})
            if payload.get("is_secret") and not include_secret_values:
                payload["value"] = "***"
            sanitized[str(variable_name)] = payload
        public["variables"] = sanitized
        return public

    def merge_environments(self, environment_refs: list[str]) -> dict[str, object]:
        merged: dict[str, object] = {}
        visited: set[str] = set()

        def walk(environment_uuid: str) -> None:
            if not environment_uuid or environment_uuid in visited:
                return
            visited.add(environment_uuid)
            record = self._load_record(environment_uuid)
            for parent_uuid in record.get("parent_environment_refs", []):
                walk(str(parent_uuid))
            for variable_name, payload in record.get("variables", {}).items():
                if not isinstance(payload, dict):
                    merged[str(variable_name)] = payload
                    continue
                merged[str(variable_name)] = payload.get("value")

        for environment_uuid in environment_refs:
            walk(str(environment_uuid).strip())
        return self.resolve_templates(merged)

    def resolve_templates(self, values: dict[str, object]) -> dict[str, object]:
        resolved = dict(values)

        def resolve_value(value: object, depth: int = 0) -> object:
            if depth > 10:
                return value
            if not isinstance(value, str):
                return value

            def replace(match: re.Match[str]) -> str:
                key = match.group(1)
                replacement = resolved.get(key, os.environ.get(key, ""))
                if replacement is None:
                    return ""
                if isinstance(replacement, str) and replacement != value:
                    return str(resolve_value(replacement, depth + 1))
                return str(replacement)

            return _TEMPLATE_PATTERN.sub(replace, value)

        for key in list(resolved.keys()):
            resolved[key] = resolve_value(resolved[key])
        return resolved

    def resolve_for_script(self, script_data: dict) -> dict[str, object]:
        environment_refs = [str(ref).strip() for ref in script_data.get("environment_refs", []) if str(ref).strip()]
        merged = self.merge_environments(environment_refs)
        merged.update({str(key): value for key, value in os.environ.items()})
        return merged

    def master_key_is_configured(self) -> bool:
        return bool(get_environment_master_key().strip())

    def list_template_variable_names(self, environment_refs: list[str]) -> list[str]:
        names = sorted(self.merge_environments(environment_refs).keys(), key=str.casefold)
        return names

    def get_environment_label(self, environment_uuid: str) -> str:
        try:
            record = self._load_record(environment_uuid)
        except Exception:
            return environment_uuid
        name = str(record.get("name", "")).strip() or environment_uuid
        scope = str(record.get("scope", "global")).strip()
        return f"{name} ({scope})"
