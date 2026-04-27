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


def script_file_path(manifest_root: Path, script_uuid: str) -> Path:
    scripts_dir, _ = ensure_manifest_layout(manifest_root)
    return scripts_dir / f"{script_uuid}.py"


def registry_file_path(manifest_root: Path, script_uuid: str) -> Path:
    _, registry_dir = ensure_manifest_layout(manifest_root)
    return registry_dir / f"{script_uuid}.json"


def write_registry_entry(manifest_root: Path, entry: dict) -> Path:
    registry_path = registry_file_path(manifest_root, entry["uuid"])
    temporary_path = registry_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary_path.replace(registry_path)
    return registry_path


def delete_registry_entry(manifest_root: Path, script_uuid: str) -> None:
    script_path = script_file_path(manifest_root, script_uuid)
    registry_path = registry_file_path(manifest_root, script_uuid)
    if script_path.exists():
        script_path.unlink()
    if registry_path.exists():
        registry_path.unlink()


def load_registry_entries(manifest_root: Path) -> list[dict]:
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
        entry["script_path"] = str(script_file_path(manifest_root, script_uuid))
        entry["registry_path"] = str(registry_file)
        entries.append(entry)

    return entries
