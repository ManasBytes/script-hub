from PyQt6.QtCore import QMimeData, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QDrag
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import get_manifest_root
from directory_manager import DirectoryManager
from registry import load_registry_entries
from script_manager import ScriptManager


# ── Move-to dialog ────────────────────────────────────────────────────────────

class MoveToDialog(QDialog):
    """Folder picker used for 'Move to…' operations on scripts and folders."""

    def __init__(self, parent, manifest_root, exclude_folder_id: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Move To")
        self.setMinimumSize(300, 380)
        self._exclude_id = exclude_folder_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Select destination folder:"))

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(14)
        self._tree.setAnimated(True)
        layout.addWidget(self._tree, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self._move_btn = QPushButton("Move Here")
        self._move_btn.setObjectName("primaryButton")
        self._move_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._move_btn)
        layout.addLayout(btn_row)

        data = DirectoryManager(manifest_root).get_full_tree()
        root_item = QTreeWidgetItem(["All Scripts  (root)"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, None)
        self._tree.addTopLevelItem(root_item)
        self._populate(root_item, data.get("folders", []))
        root_item.setExpanded(True)
        self._tree.setCurrentItem(root_item)

    def _populate(self, parent_item: QTreeWidgetItem, folders: list) -> None:
        for f in folders:
            if f["id"] == self._exclude_id:
                continue
            item = QTreeWidgetItem([f["name"]])
            item.setData(0, Qt.ItemDataRole.UserRole, f["id"])
            parent_item.addChild(item)
            self._populate(item, f.get("folders", []))
            item.setExpanded(True)

    def selected_folder_id(self) -> str | None:
        item = self._tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None


# ── Card geometry ─────────────────────────────────────────────────────────────
CARD_W = 126
CARD_H = 118
CARD_SPACING = 12
GRID_MARGIN = 10


# ── Folder mini card ──────────────────────────────────────────────────────────

class FolderMiniCard(QFrame):
    double_clicked = pyqtSignal(str)
    rename_requested = pyqtSignal(str)   # folder_id
    delete_requested = pyqtSignal(str)   # folder_id
    move_requested = pyqtSignal(str)     # folder_id
    script_dropped = pyqtSignal(str, str)  # script_uuid, folder_id

    def __init__(self, folder_data: dict):
        super().__init__()
        self.folder_id = folder_data["id"]
        self.folder_name = folder_data["name"]
        self.setObjectName("folderMiniCard")
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{self.folder_name}\nDouble-click to open")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 10)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        icon = QLabel("📁")
        icon.setObjectName("miniCardIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name = QLabel(self.folder_name)
        name.setObjectName("miniCardName")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setWordWrap(True)
        name.setMaximumHeight(32)

        layout.addStretch()
        layout.addWidget(icon)
        layout.addSpacing(2)
        layout.addWidget(name)
        layout.addStretch()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-script-uuid"):
            self._set_drag_over(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drag_over(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        uuid = event.mimeData().data("application/x-script-uuid").data().decode()
        self._set_drag_over(False)
        self.script_dropped.emit(uuid, self.folder_id)
        event.acceptProposedAction()

    def _set_drag_over(self, active: bool):
        self.setProperty("dragOver", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        act_rename = menu.addAction("Rename")
        act_move = menu.addAction("Move to…")
        menu.addSeparator()
        act_delete = menu.addAction("Delete Folder")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == act_rename:
            self.rename_requested.emit(self.folder_id)
        elif chosen == act_move:
            self.move_requested.emit(self.folder_id)
        elif chosen == act_delete:
            self.delete_requested.emit(self.folder_id)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.folder_id)
        super().mouseDoubleClickEvent(event)


# ── Script mini card ──────────────────────────────────────────────────────────

class ScriptMiniCard(QFrame):
    selection_changed = pyqtSignal()
    move_requested = pyqtSignal(str)  # script_uuid

    def __init__(self, script_data: dict, run_cb, view_cb):
        super().__init__()
        self.script_data = script_data
        self.script_uuid = script_data.get("uuid", "")
        self._run_cb = run_cb
        self._view_cb = view_cb

        self.setObjectName("scriptMiniCard")
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drag_start_pos = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        name = script_data.get("name", "Unnamed")
        desc = script_data.get("description", "")
        self.setToolTip(f"{name}\n{desc}" if desc else name)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        content = QWidget()
        content.setObjectName("miniCardContent")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(8, 0, 8, 6)
        c_layout.setSpacing(6)

        badge = QLabel("PY")
        badge.setObjectName("scriptPyBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(38, 26)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("miniCardName")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setWordWrap(True)
        name_lbl.setMaximumHeight(32)

        c_layout.addStretch()
        c_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
        c_layout.addSpacing(2)
        c_layout.addWidget(name_lbl)
        c_layout.addStretch()

        self.action_bar = QWidget()
        self.action_bar.setObjectName("miniCardActionBar")
        self.action_bar.setFixedHeight(0)
        a_layout = QHBoxLayout(self.action_bar)
        a_layout.setContentsMargins(5, 2, 5, 3)
        a_layout.setSpacing(4)

        run_btn = QPushButton("Run")
        run_btn.setObjectName("miniCardRunBtn")
        run_btn.clicked.connect(lambda: self._run_cb(self.script_data))

        view_btn = QPushButton("View")
        view_btn.setObjectName("miniCardViewBtn")
        view_btn.clicked.connect(lambda: self._view_cb(self.script_data))

        a_layout.addWidget(run_btn)
        a_layout.addWidget(view_btn)

        main.addWidget(content, 1)
        main.addWidget(self.action_bar)

        self.checkbox = QCheckBox(self)
        self.checkbox.setObjectName("scriptSelectCheckbox")
        self.checkbox.setGeometry(5, 5, 16, 16)
        self.checkbox.stateChanged.connect(lambda: self.selection_changed.emit())
        self.checkbox.hide()

    def is_selected(self) -> bool:
        return self.checkbox.isChecked()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        act_move = menu.addAction("Move to…")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == act_move:
            self.move_requested.emit(self.script_uuid)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_start_pos is not None
            and (event.buttons() & Qt.MouseButton.LeftButton)
            and (event.pos() - self._drag_start_pos).manhattanLength()
                >= QApplication.startDragDistance()
        ):
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData("application/x-script-uuid", self.script_uuid.encode())
            drag.setMimeData(mime)
            drag.setPixmap(self.grab())
            drag.setHotSpot(event.pos())
            self._drag_start_pos = None
            drag.exec(Qt.DropAction.MoveAction)
            return
        super().mouseMoveEvent(event)

    def enterEvent(self, event):
        self.action_bar.setFixedHeight(30)
        self.checkbox.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self.action_bar.setFixedHeight(0)
            if not self.checkbox.isChecked():
                self.checkbox.hide()
        super().leaveEvent(event)


# ── Breadcrumb bar ────────────────────────────────────────────────────────────

class BreadcrumbBar(QWidget):
    crumb_clicked = pyqtSignal(object)  # str | None

    def __init__(self):
        super().__init__()
        self.setObjectName("breadcrumbBar")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self.setFixedHeight(28)

    def set_path(self, path: list):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, (fid, name) in enumerate(path):
            is_last = (i == len(path) - 1)
            if i > 0:
                sep = QLabel("›")
                sep.setObjectName("breadcrumbSep")
                self._layout.addWidget(sep)

            btn = QPushButton(name)
            btn.setFlat(True)
            btn.setObjectName("breadcrumbBtnActive" if is_last else "breadcrumbBtn")
            btn.setCursor(
                Qt.CursorShape.ArrowCursor if is_last else Qt.CursorShape.PointingHandCursor
            )
            btn.clicked.connect(lambda _=False, f=fid: self.crumb_clicked.emit(f))
            self._layout.addWidget(btn)

        self._layout.addStretch()


# ── Script grid view ──────────────────────────────────────────────────────────

class ScriptGridView(QScrollArea):
    folder_opened = pyqtSignal(str)
    selection_changed = pyqtSignal()
    new_folder_requested = pyqtSignal()
    add_script_requested = pyqtSignal()
    folder_rename_requested = pyqtSignal(str)   # folder_id
    folder_delete_requested = pyqtSignal(str)   # folder_id
    folder_move_requested = pyqtSignal(str)     # folder_id
    script_moved = pyqtSignal(str, str)         # script_uuid, target_folder_id
    script_move_requested = pyqtSignal(str)     # script_uuid

    def __init__(self, run_cb, view_cb):
        super().__init__()
        self._run_cb = run_cb
        self._view_cb = view_cb
        self._all_cards: list[QFrame] = []
        self._script_cards: list[ScriptMiniCard] = []
        self._cols = 4

        self.setObjectName("scriptGridView")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container.setObjectName("scriptGridContainer")
        self._container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._container.customContextMenuRequested.connect(self._show_grid_context_menu)
        self.setWidget(self._container)

        self._empty_label = QLabel("This folder is empty.\nCreate sub-folders or add scripts to get started.")
        self._empty_label.setObjectName("gridEmptyLabel")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setParent(self._container)
        self._empty_label.hide()

    def load(self, folders: list[dict], scripts: list[dict]):
        for card in self._all_cards:
            card.setParent(None)
            card.deleteLater()
        self._all_cards.clear()
        self._script_cards.clear()

        for folder in folders:
            card = FolderMiniCard(folder)
            card.double_clicked.connect(self.folder_opened)
            card.rename_requested.connect(self.folder_rename_requested)
            card.delete_requested.connect(self.folder_delete_requested)
            card.move_requested.connect(self.folder_move_requested)
            card.script_dropped.connect(self.script_moved)
            card.setParent(self._container)
            self._all_cards.append(card)

        for script in scripts:
            card = ScriptMiniCard(script, self._run_cb, self._view_cb)
            card.selection_changed.connect(self.selection_changed)
            card.move_requested.connect(self.script_move_requested)
            card.setParent(self._container)
            self._script_cards.append(card)
            self._all_cards.append(card)

        self._cols = self._calc_cols()
        self._reposition()

        for card in self._all_cards:
            card.show()

    def _show_grid_context_menu(self, pos):
        for card in self._all_cards:
            if card.geometry().contains(pos):
                return
        menu = QMenu(self._container)
        act_new_folder = menu.addAction("New Subfolder")
        act_add_script = menu.addAction("Add Script Here")
        chosen = menu.exec(self._container.mapToGlobal(pos))
        if chosen == act_new_folder:
            self.new_folder_requested.emit()
        elif chosen == act_add_script:
            self.add_script_requested.emit()

    def get_selected_cards(self) -> list[ScriptMiniCard]:
        return [c for c in self._script_cards if c.is_selected()]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_cols = self._calc_cols()
        if new_cols != self._cols:
            self._cols = new_cols
            self._reposition()

    def _calc_cols(self) -> int:
        vw = self.viewport().width() - GRID_MARGIN * 2
        return max(1, (vw + CARD_SPACING) // (CARD_W + CARD_SPACING))

    def _reposition(self):
        if not self._all_cards:
            self._empty_label.setGeometry(0, 40, max(200, self.viewport().width()), 60)
            self._empty_label.show()
            self._container.setMinimumHeight(120)
            return

        self._empty_label.hide()
        cols = max(1, self._cols)

        for i, card in enumerate(self._all_cards):
            col = i % cols
            row = i // cols
            x = GRID_MARGIN + col * (CARD_W + CARD_SPACING)
            y = GRID_MARGIN + row * (CARD_H + CARD_SPACING)
            card.move(x, y)

        rows = (len(self._all_cards) + cols - 1) // cols
        total_h = GRID_MARGIN + rows * (CARD_H + CARD_SPACING) + GRID_MARGIN
        self._container.setMinimumHeight(total_h)


# ── Scripts page ──────────────────────────────────────────────────────────────

class ScriptsPage(QWidget):
    add_requested = pyqtSignal(object)         # folder_id: str | None
    scripts_changed = pyqtSignal()
    view_script_requested = pyqtSignal(dict)
    run_script_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setObjectName("ScriptsPage")
        self._script_manager = ScriptManager()
        self._current_folder_id: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 16)
        outer.setSpacing(10)

        # ── Header ─────────────────────────────────────────────────────────
        title = QLabel("Scripts")
        title.setObjectName("pageTitle")

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._delete_selected)

        add_btn = QPushButton("+ Add Script")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._on_add_clicked)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.delete_button)
        header.addWidget(add_btn)
        outer.addLayout(header)

        # ── Breadcrumb ──────────────────────────────────────────────────────
        self.breadcrumb = BreadcrumbBar()
        self.breadcrumb.crumb_clicked.connect(self._on_crumb_clicked)
        outer.addWidget(self.breadcrumb)

        # ── Search ──────────────────────────────────────────────────────────
        self.search_input = QLineEdit()
        self.search_input.setObjectName("scriptsSearch")
        self.search_input.setPlaceholderText("Search scripts by name or description…")
        self.search_input.textChanged.connect(self._load_grid)
        outer.addWidget(self.search_input)

        # ── Meta ────────────────────────────────────────────────────────────
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("scriptsMeta")
        outer.addWidget(self.meta_label)

        # ── Grid ────────────────────────────────────────────────────────────
        self.grid_view = ScriptGridView(self.run_script, self.view_script)
        self.grid_view.folder_opened.connect(self._navigate_to)
        self.grid_view.selection_changed.connect(self._update_delete_button)
        self.grid_view.new_folder_requested.connect(self._new_subfolder)
        self.grid_view.add_script_requested.connect(self._on_add_clicked)
        self.grid_view.folder_rename_requested.connect(self._rename_folder)
        self.grid_view.folder_delete_requested.connect(self._delete_folder)
        self.grid_view.folder_move_requested.connect(self._open_move_folder_dialog)
        self.grid_view.script_moved.connect(self._move_script)
        self.grid_view.script_move_requested.connect(self._open_move_script_dialog)
        outer.addWidget(self.grid_view, 1)

        self.reload_scripts()

    # ── Public API ────────────────────────────────────────────────────────

    def navigate_to(self, folder_id: str | None) -> None:
        """Navigate to a specific folder (called from the global sidebar)."""
        self._navigate_to(folder_id)

    # ── Data / navigation ─────────────────────────────────────────────────

    def reload_scripts(self):
        manifest_root = get_manifest_root()
        all_entries = load_registry_entries(manifest_root)
        DirectoryManager(manifest_root).migrate_orphans([e["uuid"] for e in all_entries])
        self._navigate_to(self._current_folder_id)

    def _navigate_to(self, folder_id):
        if folder_id is not None:
            if DirectoryManager(get_manifest_root()).get_folder_name(folder_id) is None:
                folder_id = None

        self._current_folder_id = folder_id
        path = DirectoryManager(get_manifest_root()).get_folder_path(folder_id)
        self.breadcrumb.set_path(path)
        self._load_grid()

    def _load_grid(self):
        query = self.search_input.text().strip().lower()
        manifest_root = get_manifest_root()
        all_entries = load_registry_entries(manifest_root)
        entry_map = {e["uuid"]: e for e in all_entries}
        dm = DirectoryManager(manifest_root)

        if query:
            if self._current_folder_id is None:
                scripts = [s for s in all_entries
                           if query in s.get("name", "").lower()
                           or query in s.get("description", "").lower()]
            else:
                _, uuids = dm.get_folder_contents(self._current_folder_id)
                pool = [entry_map[u] for u in uuids if u in entry_map]
                scripts = [s for s in pool
                           if query in s.get("name", "").lower()
                           or query in s.get("description", "").lower()]
            folders = []
        else:
            folders, uuids = dm.get_folder_contents(self._current_folder_id)
            scripts = [entry_map[u] for u in uuids if u in entry_map]

        self.grid_view.load(folders, scripts)

        if query:
            n = len(scripts)
            self.meta_label.setText(f"{n} script{'s' if n != 1 else ''} found")
        else:
            parts = []
            if folders:
                parts.append(f"{len(folders)} folder{'s' if len(folders) != 1 else ''}")
            if scripts:
                parts.append(f"{len(scripts)} script{'s' if len(scripts) != 1 else ''}")
            self.meta_label.setText("  ·  ".join(parts) if parts else "Empty")

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_crumb_clicked(self, folder_id) -> None:
        self._navigate_to(folder_id)

    def _on_add_clicked(self) -> None:
        self.add_requested.emit(self._current_folder_id)

    def _update_delete_button(self):
        count = len(self.grid_view.get_selected_cards())
        self.delete_button.setEnabled(count > 0)
        self.delete_button.setText(f"Delete Selected ({count})" if count else "Delete Selected")

    def _delete_selected(self):
        selected = self.grid_view.get_selected_cards()
        if not selected:
            return
        names = "\n".join(f"• {c.script_uuid}" for c in selected)
        confirm = QMessageBox.question(
            self,
            "Move to Trash",
            f"Move {len(selected)} script(s) to Trash?\n\n{names}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        errors = []
        for card in selected:
            try:
                self._script_manager.delete_script(card.script_uuid)
            except Exception as exc:
                errors.append(f"{card.script_uuid}: {exc}")

        if errors:
            QMessageBox.warning(self, "Partial Deletion", "\n".join(errors))

        self.reload_scripts()
        self.scripts_changed.emit()

    def _move_script(self, script_uuid: str, folder_id: str):
        DirectoryManager(get_manifest_root()).move_script(script_uuid, folder_id)
        self.reload_scripts()
        self.scripts_changed.emit()

    def _open_move_script_dialog(self, script_uuid: str):
        dlg = MoveToDialog(self, get_manifest_root(), exclude_folder_id=None)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        target = dlg.selected_folder_id()
        DirectoryManager(get_manifest_root()).move_script(script_uuid, target)
        self.reload_scripts()
        self.scripts_changed.emit()

    def _open_move_folder_dialog(self, folder_id: str):
        dlg = MoveToDialog(self, get_manifest_root(), exclude_folder_id=folder_id)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        target = dlg.selected_folder_id()
        try:
            DirectoryManager(get_manifest_root()).move_folder(folder_id, target)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot Move", str(exc))
            return
        if self._current_folder_id == folder_id:
            self._current_folder_id = target
        self._navigate_to(self._current_folder_id)
        self.scripts_changed.emit()

    def _new_subfolder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        DirectoryManager(get_manifest_root()).add_folder(self._current_folder_id, name.strip())
        self._navigate_to(self._current_folder_id)
        self.scripts_changed.emit()

    def _rename_folder(self, folder_id: str):
        dm = DirectoryManager(get_manifest_root())
        old_name = dm.get_folder_name(folder_id) or ""
        name, ok = QInputDialog.getText(self, "Rename Folder", "New name:", text=old_name)
        if not ok or not name.strip() or name.strip() == old_name:
            return
        dm.rename_folder(folder_id, name.strip())
        self._navigate_to(self._current_folder_id)
        self.scripts_changed.emit()

    def _delete_folder(self, folder_id: str):
        reply = QMessageBox.question(
            self,
            "Delete Folder",
            "Delete this folder?\nScripts inside will be moved to root.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self._current_folder_id == folder_id:
            self._current_folder_id = None
        DirectoryManager(get_manifest_root()).delete_folder(folder_id)
        self._navigate_to(self._current_folder_id)
        self.scripts_changed.emit()

    def run_script(self, script_data: dict) -> None:
        self.run_script_requested.emit(script_data)

    def view_script(self, script_data: dict) -> None:
        self.view_script_requested.emit(script_data)
