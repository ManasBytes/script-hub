from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from directory_manager import DirectoryManager


class FolderTreeWidget(QWidget):
    """Left-panel folder tree shown inside the Scripts page."""

    folder_selected = pyqtSignal(object)   # emits str | None  (None = "All Scripts" / root)
    tree_changed = pyqtSignal()            # folder added / renamed / deleted

    def __init__(self, manifest_root: Path):
        super().__init__()
        self.setObjectName("folderTreePanel")
        self._manifest_root = Path(manifest_root)
        self._selected_folder_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header strip ─────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("folderTreeHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 10, 10, 8)
        hl.setSpacing(6)

        title_lbl = QLabel("Folders")
        title_lbl.setObjectName("folderTreeTitle")
        hl.addWidget(title_lbl)
        hl.addStretch()

        new_btn = QPushButton("+ New")
        new_btn.setObjectName("smallPrimaryButton")
        new_btn.setToolTip("New sub-folder inside the selected folder")
        new_btn.clicked.connect(self._new_at_selected)
        hl.addWidget(new_btn)
        layout.addWidget(header)

        # ── Tree ─────────────────────────────────────────────────────────────
        self.tree = QTreeWidget()
        self.tree.setObjectName("folderTree")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemClicked.connect(self._item_clicked)
        layout.addWidget(self.tree)

        self.reload()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_manifest_root(self, root: Path) -> None:
        self._manifest_root = Path(root)

    def get_selected_folder_id(self) -> str | None:
        return self._selected_folder_id

    def select_folder(self, folder_id: str | None) -> None:
        """Programmatically set selected folder without emitting folder_selected."""
        self._selected_folder_id = folder_id
        root_item = self.tree.topLevelItem(0)
        if root_item:
            self.tree.blockSignals(True)
            self._restore_selection(root_item)
            self.tree.blockSignals(False)

    def reload(self) -> None:
        self.tree.clear()
        data = self._dm.get_full_tree()

        root_item = QTreeWidgetItem(["All Scripts"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, None)
        self.tree.addTopLevelItem(root_item)
        self._populate(root_item, data.get("folders", []))
        root_item.setExpanded(True)
        self._restore_selection(root_item)

    # ── Private: helpers ──────────────────────────────────────────────────────

    @property
    def _dm(self) -> DirectoryManager:
        return DirectoryManager(self._manifest_root)

    def _populate(self, parent: QTreeWidgetItem, folders: list) -> None:
        for f in folders:
            item = QTreeWidgetItem([f["name"]])
            item.setData(0, Qt.ItemDataRole.UserRole, f["id"])
            parent.addChild(item)
            self._populate(item, f.get("folders", []))

    def _restore_selection(self, root_item: QTreeWidgetItem) -> None:
        if self._selected_folder_id is None:
            self.tree.setCurrentItem(root_item)
            return
        found = self._find_item(root_item, self._selected_folder_id)
        if found:
            self.tree.setCurrentItem(found)
            found.setExpanded(True)
        else:
            self._selected_folder_id = None
            self.tree.setCurrentItem(root_item)

    def _find_item(self, parent: QTreeWidgetItem, folder_id: str) -> QTreeWidgetItem | None:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == folder_id:
                return child
            found = self._find_item(child, folder_id)
            if found:
                return found
        return None

    # ── Private: interactions ─────────────────────────────────────────────────

    def _item_clicked(self, item: QTreeWidgetItem) -> None:
        fid = item.data(0, Qt.ItemDataRole.UserRole)
        self._selected_folder_id = fid
        self.folder_selected.emit(fid)

    def _context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        folder_id = item.data(0, Qt.ItemDataRole.UserRole)
        is_root = folder_id is None

        menu = QMenu(self)
        act_new = menu.addAction("New Subfolder")
        menu.addSeparator()
        act_rename = menu.addAction("Rename")
        act_delete = menu.addAction("Delete Folder")
        act_rename.setEnabled(not is_root)
        act_delete.setEnabled(not is_root)

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == act_new:
            self._create_subfolder(folder_id)
        elif chosen == act_rename:
            self._rename_folder(folder_id, item)
        elif chosen == act_delete:
            self._delete_folder(folder_id)

    def _new_at_selected(self) -> None:
        self._create_subfolder(self._selected_folder_id)

    def _create_subfolder(self, parent_id: str | None) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        self._dm.add_folder(parent_id, name.strip())
        self.reload()
        self.tree_changed.emit()

    def _rename_folder(self, folder_id: str, item: QTreeWidgetItem) -> None:
        old = item.text(0)
        name, ok = QInputDialog.getText(self, "Rename Folder", "New name:", text=old)
        if not ok or not name.strip() or name.strip() == old:
            return
        self._dm.rename_folder(folder_id, name.strip())
        self.reload()
        self.tree_changed.emit()

    def _delete_folder(self, folder_id: str) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Folder",
            "Delete this folder?\nScripts inside will be moved to root.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self._selected_folder_id == folder_id:
            self._selected_folder_id = None
        self._dm.delete_folder(folder_id)
        self.reload()
        self.folder_selected.emit(self._selected_folder_id)
        self.tree_changed.emit()
