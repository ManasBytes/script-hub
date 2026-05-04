from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from config import get_manifest_root
from directory_manager import DirectoryManager
from registry import load_registry_entries

ROW_H   = 28
INDENT  = 16   # px per depth level
TOGGLE_W = 18
ICON_W   = 20


# ── Individual row widgets ────────────────────────────────────────────────────

class _FolderRow(QWidget):
    toggled  = pyqtSignal(object)   # folder_id  (str | None)
    navigate = pyqtSignal(object)   # folder_id  (str | None) on double-click

    def __init__(
        self,
        folder_id,
        name: str,
        depth: int,
        expanded: bool,
        has_children: bool,
    ):
        super().__init__()
        self.folder_id = folder_id
        self._has_children = has_children
        self.setObjectName("explorerFolderRow")
        self.setFixedHeight(ROW_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

        row = QHBoxLayout(self)
        row.setContentsMargins(4 + depth * INDENT, 0, 4, 0)
        row.setSpacing(2)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("explorerToggleBtn")
        self.toggle_btn.setFixedSize(TOGGLE_W, TOGGLE_W)
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if has_children:
            self.toggle_btn.setText("▼" if expanded else "▶")
            self.toggle_btn.clicked.connect(lambda: self.toggled.emit(folder_id))
        else:
            self.toggle_btn.setText("")
            self.toggle_btn.setEnabled(False)

        row.addWidget(self.toggle_btn)

        icon = QLabel("📁")
        icon.setObjectName("explorerIcon")
        icon.setFixedWidth(ICON_W)
        row.addWidget(icon)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("explorerItemName")
        row.addWidget(name_lbl, 1)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only navigate when click is outside the toggle button area
            if not (self._has_children and self.toggle_btn.geometry().contains(event.pos())):
                self.navigate.emit(self.folder_id)
        super().mouseDoubleClickEvent(event)


class _ScriptRow(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, script_data: dict, depth: int):
        super().__init__()
        self.script_data = script_data
        self.setObjectName("explorerScriptRow")
        self.setFixedHeight(ROW_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

        row = QHBoxLayout(self)
        row.setContentsMargins(4 + depth * INDENT, 0, 4, 0)
        row.setSpacing(2)

        spacer = QWidget()
        spacer.setFixedWidth(TOGGLE_W)
        row.addWidget(spacer)

        icon = QLabel("📄")
        icon.setObjectName("explorerIcon")
        icon.setFixedWidth(ICON_W)
        row.addWidget(icon)

        name = script_data.get("name") or Path(script_data.get("script_path", "")).stem
        name_lbl = QLabel(name)
        name_lbl.setObjectName("explorerItemName")
        row.addWidget(name_lbl, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.script_data)
        super().mousePressEvent(event)


# ── Main sidebar widget ───────────────────────────────────────────────────────

class Sidebar(QWidget):
    """VSCode Explorer-style global sidebar with ▶/▼ per-folder toggles."""

    script_selected          = pyqtSignal(dict)
    folder_navigate_requested = pyqtSignal(object)   # str | None

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self._expanded: dict = {}   # folder_id → bool; root (None) defaults True
        self._entry_map: dict = {}
        self._tree_data: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setObjectName("sidebarHeader")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 10, 8, 8)
        hl.setSpacing(4)

        title = QLabel("EXPLORER")
        title.setObjectName("sidebarTitle")
        hl.addWidget(title)
        hl.addStretch()

        collapse_btn = QPushButton("⊟")
        collapse_btn.setObjectName("sidebarCollapseAllBtn")
        collapse_btn.setToolTip("Collapse all folders")
        collapse_btn.setFixedSize(22, 22)
        collapse_btn.clicked.connect(self._collapse_all)
        hl.addWidget(collapse_btn)

        layout.addWidget(hdr)

        # ── Scroll area ─────────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setObjectName("explorerScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._container = QWidget()
        self._container.setObjectName("explorerContainer")
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(0, 4, 0, 8)
        self._vbox.setSpacing(0)
        self._vbox.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

        self.reload()

    # ── Public ────────────────────────────────────────────────────────────

    def reload(self) -> None:
        manifest_root = get_manifest_root()
        entries = load_registry_entries(manifest_root)
        self._entry_map = {e["uuid"]: e for e in entries}
        self._tree_data = DirectoryManager(manifest_root).get_full_tree()
        self._build_tree()

    # ── Tree building ─────────────────────────────────────────────────────

    def _build_tree(self):
        # Remove all existing rows (keep only the terminal stretch)
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        root_has_children = (
            bool(self._tree_data.get("folders"))
            or bool(self._tree_data.get("scripts"))
        )
        root_expanded = self._expanded.get(None, True)

        root_row = _FolderRow(None, "All Scripts", 0, root_expanded, root_has_children)
        root_row.toggled.connect(self._toggle)
        root_row.navigate.connect(self.folder_navigate_requested)
        self._insert_row(root_row)

        if root_expanded:
            self._add_children(self._tree_data, depth=1)

    def _add_children(self, node: dict, depth: int):
        for f in node.get("folders", []):
            fid = f["id"]
            is_exp = self._expanded.get(fid, False)
            has_children = bool(f.get("folders")) or bool(f.get("scripts"))

            row = _FolderRow(fid, f["name"], depth, is_exp, has_children)
            row.toggled.connect(self._toggle)
            row.navigate.connect(self.folder_navigate_requested)
            self._insert_row(row)

            if is_exp:
                self._add_children(f, depth + 1)

        for uuid in node.get("scripts", []):
            entry = self._entry_map.get(uuid)
            if not entry:
                continue
            row = _ScriptRow(entry, depth)
            row.clicked.connect(self.script_selected)
            self._insert_row(row)

    def _insert_row(self, widget: QWidget):
        self._vbox.insertWidget(self._vbox.count() - 1, widget)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _toggle(self, folder_id):
        default = (folder_id is None)   # root defaults to True
        self._expanded[folder_id] = not self._expanded.get(folder_id, default)
        self._build_tree()

    def _collapse_all(self):
        for key in list(self._expanded.keys()):
            if key is not None:
                self._expanded[key] = False
        self._expanded[None] = True   # root always stays visible
        self._build_tree()
