import json
import uuid as _uuid_mod
from pathlib import Path


class DirectoryManager:
    """
    Manages Manifest/directory.json — the folder hierarchy for scripts.

    Tree shape stored on disk:
    {
        "version": 1,
        "folders": [
            {"id": "abc123", "name": "ETL", "folders": [...], "scripts": ["uuid1", ...]}
        ],
        "scripts": ["uuid2", ...]   <- root-level (unfiled) scripts
    }
    """

    def __init__(self, manifest_root: Path):
        self.manifest_root = Path(manifest_root)
        self._path = self.manifest_root / "directory.json"

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self) -> dict:
        if not self._path.exists():
            return {"version": 1, "folders": [], "scripts": []}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"version": 1, "folders": [], "scripts": []}
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "folders": [], "scripts": []}

    def save(self, tree: dict) -> None:
        self.manifest_root.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path)

    # ── Folder CRUD ───────────────────────────────────────────────────────────

    def add_folder(self, parent_id: str | None, name: str) -> str:
        """Create a folder under parent (None = root). Returns the new folder id."""
        tree = self.load()
        folder_id = _uuid_mod.uuid4().hex[:12]
        new_node = {"id": folder_id, "name": name, "folders": [], "scripts": []}
        if parent_id is None:
            tree.setdefault("folders", []).append(new_node)
        else:
            parent = self._find_folder(tree, parent_id)
            if parent is None:
                raise ValueError(f"Parent folder {parent_id!r} not found")
            parent.setdefault("folders", []).append(new_node)
        self.save(tree)
        return folder_id

    def rename_folder(self, folder_id: str, new_name: str) -> None:
        tree = self.load()
        node = self._find_folder(tree, folder_id)
        if node is None:
            raise ValueError(f"Folder {folder_id!r} not found")
        node["name"] = new_name
        self.save(tree)

    def delete_folder(self, folder_id: str) -> list[str]:
        """Delete folder recursively. Returns script UUIDs that were inside (moved to root)."""
        tree = self.load()
        node = self._find_folder(tree, folder_id)
        orphans = self._collect_scripts(node or {})
        self._remove_folder_node(tree, folder_id)
        tree.setdefault("scripts", []).extend(orphans)
        self.save(tree)
        return orphans

    # ── Script placement ──────────────────────────────────────────────────────

    def add_script(self, script_uuid: str, folder_id: str | None = None) -> None:
        """Place a script in folder (None = root). Removes from any previous location."""
        tree = self.load()
        self._remove_script_everywhere(tree, script_uuid)
        if folder_id is None:
            tree.setdefault("scripts", []).append(script_uuid)
        else:
            node = self._find_folder(tree, folder_id)
            if node is None:
                tree.setdefault("scripts", []).append(script_uuid)
            else:
                node.setdefault("scripts", []).append(script_uuid)
        self.save(tree)

    def remove_script(self, script_uuid: str) -> None:
        tree = self.load()
        self._remove_script_everywhere(tree, script_uuid)
        self.save(tree)

    def move_script(self, script_uuid: str, target_folder_id: str | None) -> None:
        self.add_script(script_uuid, target_folder_id)

    def move_folder(self, folder_id: str, new_parent_id: str | None) -> None:
        """Re-parent folder_id under new_parent_id (None = root). Raises if target is inside folder."""
        tree = self.load()
        if new_parent_id is not None and self._is_ancestor(tree, folder_id, new_parent_id):
            raise ValueError("Cannot move a folder into itself or one of its descendants")
        node = self._extract_folder_node(tree, folder_id)
        if node is None:
            raise ValueError(f"Folder {folder_id!r} not found")
        if new_parent_id is None:
            tree.setdefault("folders", []).append(node)
        else:
            parent = self._find_folder(tree, new_parent_id)
            if parent is None:
                raise ValueError(f"Target folder {new_parent_id!r} not found")
            parent.setdefault("folders", []).append(node)
        self.save(tree)

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_folder_contents(self, folder_id: str | None) -> tuple[list[dict], list[str]]:
        """Return (sub-folder list, script UUID list) for a folder. None = root."""
        tree = self.load()
        if folder_id is None:
            return tree.get("folders", []), tree.get("scripts", [])
        node = self._find_folder(tree, folder_id)
        if node is None:
            return [], []
        return node.get("folders", []), node.get("scripts", [])

    def get_full_tree(self) -> dict:
        return self.load()

    def get_folder_name(self, folder_id: str) -> str | None:
        tree = self.load()
        node = self._find_folder(tree, folder_id)
        return node["name"] if node else None

    def find_folder_of_script(self, script_uuid: str) -> str | None:
        """Return the folder_id containing the script, or None if root/not found."""
        tree = self.load()
        return self._find_script_folder(tree, script_uuid, current_id=None)

    def get_folder_path(self, folder_id: str | None) -> list[tuple]:
        """Return [(id, name), ...] from root to folder. First entry is always (None, 'All Scripts')."""
        if folder_id is None:
            return [(None, "All Scripts")]
        tree = self.load()
        result: list | None = None

        def dfs(node: dict, path: list) -> bool:
            nonlocal result
            for f in node.get("folders", []):
                extended = path + [(f["id"], f["name"])]
                if f["id"] == folder_id:
                    result = extended
                    return True
                if dfs(f, extended):
                    return True
            return False

        dfs(tree, [])
        if result:
            return [(None, "All Scripts")] + result
        return [(None, "All Scripts")]

    def migrate_orphans(self, all_uuids: list[str]) -> bool:
        """Add any registry UUIDs not yet in the tree to root. Returns True if changed."""
        tree = self.load()
        known = self._collect_all_scripts(tree)
        orphans = [u for u in all_uuids if u not in known]
        if not orphans:
            return False
        tree.setdefault("scripts", []).extend(orphans)
        self.save(tree)
        return True

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_folder(self, node: dict, folder_id: str) -> dict | None:
        for f in node.get("folders", []):
            if f["id"] == folder_id:
                return f
            found = self._find_folder(f, folder_id)
            if found is not None:
                return found
        return None

    def _remove_folder_node(self, node: dict, folder_id: str) -> bool:
        folders = node.get("folders", [])
        for i, f in enumerate(folders):
            if f["id"] == folder_id:
                folders.pop(i)
                return True
            if self._remove_folder_node(f, folder_id):
                return True
        return False

    def _remove_script_everywhere(self, node: dict, uuid: str) -> None:
        scripts = node.get("scripts", [])
        if uuid in scripts:
            scripts.remove(uuid)
        for f in node.get("folders", []):
            self._remove_script_everywhere(f, uuid)

    def _collect_scripts(self, node: dict) -> list[str]:
        result = list(node.get("scripts", []))
        for f in node.get("folders", []):
            result.extend(self._collect_scripts(f))
        return result

    def _collect_all_scripts(self, tree: dict) -> set[str]:
        result = set(tree.get("scripts", []))
        for f in tree.get("folders", []):
            result.update(self._collect_scripts(f))
        return result

    def _find_script_folder(self, node: dict, uuid: str, current_id: str | None) -> str | None:
        if uuid in node.get("scripts", []):
            return current_id
        for f in node.get("folders", []):
            found = self._find_script_folder(f, uuid, f["id"])
            if found is not None or uuid in f.get("scripts", []):
                return f["id"] if uuid in f.get("scripts", []) else found
        return None

    def _extract_folder_node(self, node: dict, folder_id: str) -> dict | None:
        """Remove and return the folder node with folder_id from the tree."""
        folders = node.get("folders", [])
        for i, f in enumerate(folders):
            if f["id"] == folder_id:
                return folders.pop(i)
            result = self._extract_folder_node(f, folder_id)
            if result is not None:
                return result
        return None

    def _is_ancestor(self, tree: dict, ancestor_id: str, node_id: str) -> bool:
        """Return True if node_id is ancestor_id or lives anywhere inside ancestor_id's subtree."""
        if ancestor_id == node_id:
            return True
        ancestor = self._find_folder(tree, ancestor_id)
        if ancestor is None:
            return False
        return self._find_folder(ancestor, node_id) is not None
