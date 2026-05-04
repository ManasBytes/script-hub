import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_manifest_layout(manifest_root: Path) -> tuple[Path, Path]:
    scripts_dir = manifest_root / "scripts"
    registry_dir = manifest_root / "registry"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    registry_dir.mkdir(parents=True, exist_ok=True)
    return scripts_dir, registry_dir


def script_file_path(manifest_root: Path, file_uuid: str) -> Path:
    scripts_dir, _ = ensure_manifest_layout(manifest_root)
    return scripts_dir / f"{file_uuid}.py"


def registry_file_path(manifest_root: Path, script_uuid: str) -> Path:
    _, registry_dir = ensure_manifest_layout(manifest_root)
    return registry_dir / f"{script_uuid}.json"


def write_registry_entry(manifest_root: Path, entry: dict) -> Path:
    registry_path = registry_file_path(manifest_root, entry["uuid"])
    temporary_path = registry_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary_path.replace(registry_path)
    return registry_path


def _migrate_to_versions_format(entry: dict) -> bool:
    """Migrate old registry format (flat fields) to new versions dict format in-place."""
    if "versions" in entry:
        return False

    old_pv = entry.pop("previous_versions", None)
    file_uuid = (old_pv or {}).get("1") or entry.get("uuid", "")

    current_version = entry.get("current_version", 1)
    version_data = {
        "file_uuid": file_uuid,
        "description": entry.pop("description", ""),
        "input_variables": entry.pop("input_variables", []),
        "config_variable": entry.pop("config_variable", []),
        "output_variable": entry.pop("output_variable", []),
        "dependencies": entry.pop("dependencies", []),
        "help_file_path": entry.pop("help_file_path", ""),
        "version_created_at": entry.get("created_at", ""),
        "trashed": False,
    }
    entry["current_version"] = current_version
    entry["versions"] = {str(current_version): version_data}
    return True


def inject_current_version_fields(manifest_root: Path, entry: dict) -> dict:
    """Inject current version's metadata at the top level of entry in-place."""
    script_uuid = entry.get("uuid", "")
    current_ver = str(entry.get("current_version", 1))
    ver_data = entry.get("versions", {}).get(current_ver, {})
    file_uuid = ver_data.get("file_uuid") or script_uuid

    entry["description"] = ver_data.get("description", "")
    entry["input_variables"] = ver_data.get("input_variables", [])
    entry["config_variable"] = ver_data.get("config_variable", [])
    entry["output_variable"] = ver_data.get("output_variable", [])
    entry["dependencies"] = ver_data.get("dependencies", [])
    entry["help_file_path"] = ver_data.get("help_file_path", "")
    entry["script_path"] = str(script_file_path(manifest_root, file_uuid))
    return entry


def delete_registry_entry(manifest_root: Path, script_uuid: str) -> None:
    """Soft-delete: mark top-level trashed=True on the registry entry."""
    registry_path = registry_file_path(manifest_root, script_uuid)
    if not registry_path.exists():
        return
    try:
        entry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        entry = {"uuid": script_uuid}

    entry["trashed"] = True
    entry["trashed_at"] = utc_now_iso()
    write_registry_entry(manifest_root, entry)


def permanently_delete_registry_entry(manifest_root: Path, script_uuid: str) -> None:
    """Permanently remove all version script files and the registry JSON."""
    registry_path = registry_file_path(manifest_root, script_uuid)

    if registry_path.exists():
        try:
            entry = json.loads(registry_path.read_text(encoding="utf-8"))
            versions = entry.get("versions", {})
            if versions:
                for ver_data in versions.values():
                    file_uuid = ver_data.get("file_uuid")
                    if file_uuid:
                        f = script_file_path(manifest_root, file_uuid)
                        if f.exists():
                            f.unlink()
            else:
                f = script_file_path(manifest_root, script_uuid)
                if f.exists():
                    f.unlink()
        except Exception:
            f = script_file_path(manifest_root, script_uuid)
            if f.exists():
                f.unlink()
        registry_path.unlink()
    else:
        f = script_file_path(manifest_root, script_uuid)
        if f.exists():
            f.unlink()


def permanently_delete_version_file(manifest_root: Path, file_uuid: str) -> None:
    """Delete a single version's script file from disk."""
    f = script_file_path(manifest_root, file_uuid)
    if f.exists():
        f.unlink()


def load_registry_entries(manifest_root: Path, include_trashed: bool = False) -> list[dict]:
    """Load registry entries, auto-migrating old format. Trashed entries excluded by default."""
    _, registry_dir = ensure_manifest_layout(manifest_root)
    entries: list[dict] = []

    for registry_file in sorted(registry_dir.glob("*.json"), key=lambda path: path.name.casefold()):
        try:
            entry = json.loads(registry_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(entry, dict):
            continue

        script_uuid = entry.get("uuid") or registry_file.stem
        entry["uuid"] = script_uuid

        migrated = _migrate_to_versions_format(entry)
        if migrated:
            try:
                write_registry_entry(manifest_root, entry)
            except Exception:
                pass

        inject_current_version_fields(manifest_root, entry)
        entry["registry_path"] = str(registry_file)

        if entry.get("trashed") and not include_trashed:
            continue

        entries.append(entry)

    return entries


def load_trashed_version_entries(manifest_root: Path) -> list[dict]:
    """Load entries for trashed versions within non-trashed (active) scripts."""
    _, registry_dir = ensure_manifest_layout(manifest_root)
    results = []

    for registry_file in sorted(registry_dir.glob("*.json"), key=lambda p: p.name.casefold()):
        try:
            entry = json.loads(registry_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(entry, dict):
            continue

        if entry.get("trashed"):
            continue

        script_uuid = entry.get("uuid") or registry_file.stem
        versions = entry.get("versions", {})

        for ver_num_str, ver_data in versions.items():
            if ver_data.get("trashed"):
                results.append({
                    "uuid": script_uuid,
                    "version_num": int(ver_num_str),
                    "name": entry.get("name", "Unnamed"),
                    "description": ver_data.get("description", ""),
                    "trashed_at": ver_data.get("trashed_at", ""),
                    "_is_version_trash": True,
                    "file_uuid": ver_data.get("file_uuid"),
                })

    return results
