from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config import get_manifest_root
from directory_manager import DirectoryManager
from registry import load_registry_entries, load_trashed_version_entries
from script_manager import ScriptManager


# ── Helpers ───────────────────────────────────────────────────────────────────

def _folder_breadcrumb(manifest_root: Path, folder_id: str | None) -> str:
    path = DirectoryManager(manifest_root).get_folder_path(folder_id)
    return " › ".join(name for _, name in path)


def _fmt_ts(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str).astimezone()
        return dt.strftime("%b %d, %Y  %H:%M")
    except Exception:
        return iso_str[:16].replace("T", "  ")


# ── Trash item card ───────────────────────────────────────────────────────────

class TrashItemCard(QFrame):
    restore_clicked = pyqtSignal(dict)
    delete_clicked = pyqtSignal(dict)

    def __init__(self, entry: dict, manifest_root: Path):
        super().__init__()
        self.entry = entry
        self.setObjectName("trashCard")

        is_version = entry.get("_is_version_trash", False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(5)

        # ── Top row: checkbox · badge · name · buttons ────────────────────────
        top = QHBoxLayout()
        top.setSpacing(10)
        top.setContentsMargins(0, 0, 0, 0)

        self.checkbox = QCheckBox()
        top.addWidget(self.checkbox)

        if is_version:
            badge_text = f"V{entry.get('version_num', '?')}"
            name_text = f"{entry.get('name', 'Unnamed')}  —  Version {entry.get('version_num', '?')}"
        else:
            badge_text = "PY"
            name_text = entry.get("name", "Unnamed")

        badge = QLabel(badge_text)
        badge.setObjectName("trashCardBadge")
        badge.setFixedSize(28, 20)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(badge)

        name_lbl = QLabel(name_text)
        name_lbl.setObjectName("trashCardName")
        top.addWidget(name_lbl, 1)

        restore_btn = QPushButton("Restore")
        restore_btn.setObjectName("trashRestoreBtn")
        restore_btn.setFixedHeight(26)
        restore_btn.clicked.connect(lambda: self.restore_clicked.emit(self.entry))
        top.addWidget(restore_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("trashDeleteBtn")
        delete_btn.setFixedHeight(26)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.entry))
        top.addWidget(delete_btn)

        outer.addLayout(top)

        # ── Description ───────────────────────────────────────────────────────
        desc = entry.get("description", "").strip()
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setObjectName("trashCardDesc")
            desc_lbl.setWordWrap(True)
            desc_lbl.setMaximumHeight(34)
            outer.addWidget(desc_lbl)

        # ── Meta: location (for scripts) · trashed date ───────────────────────
        trashed_at = _fmt_ts(entry.get("trashed_at", ""))
        if is_version:
            meta_lbl = QLabel(f"Version trashed: {trashed_at}")
        else:
            folder_id = entry.get("trashed_from_folder")
            location = _folder_breadcrumb(manifest_root, folder_id)
            meta_lbl = QLabel(f"📁  {location}     ·     Trashed: {trashed_at}")
        meta_lbl.setObjectName("trashCardMeta")
        outer.addWidget(meta_lbl)

    def is_selected(self) -> bool:
        return bool(self.checkbox.isChecked())

    def set_checked(self, checked: bool) -> None:
        self.checkbox.setChecked(checked)


# ── Trash page ────────────────────────────────────────────────────────────────

class TrashPage(QWidget):
    request_refresh = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("TrashPage")
        self._script_manager = ScriptManager()
        self._cards: list[TrashItemCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 24)
        layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────────
        title = QLabel("Trash")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel("Deleted scripts — restore them to return to their original folder.")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        # ── Actions bar ────────────────────────────────────────────────────────
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)

        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("trashCountLabel")
        actions.addWidget(self._count_lbl)

        self._select_all_cb = QCheckBox("Select All")
        self._select_all_cb.stateChanged.connect(self._toggle_select_all)
        actions.addWidget(self._select_all_cb)

        actions.addStretch()

        self._restore_btn = QPushButton("Restore Selected")
        self._restore_btn.setObjectName("primaryButton")
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self._restore_selected)
        actions.addWidget(self._restore_btn)

        self._empty_btn = QPushButton("Empty Trash")
        self._empty_btn.setObjectName("dangerButton")
        self._empty_btn.setEnabled(False)
        self._empty_btn.clicked.connect(self._empty_trash)
        actions.addWidget(self._empty_btn)

        layout.addLayout(actions)
        layout.addSpacing(14)

        # ── Scroll area ────────────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setObjectName("trashScrollArea")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(10)
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, 1)

        self.reload()

    # ── Public ────────────────────────────────────────────────────────────────

    def reload(self):
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()
        self._select_all_cb.blockSignals(True)
        self._select_all_cb.setChecked(False)
        self._select_all_cb.blockSignals(False)

        manifest_root = get_manifest_root()
        entries = load_registry_entries(manifest_root, include_trashed=True)
        trashed_scripts = [e for e in entries if e.get("trashed")]
        trashed_versions = load_trashed_version_entries(manifest_root)
        all_trashed = trashed_scripts + trashed_versions

        if not all_trashed:
            empty_lbl = QLabel("Trash is empty.")
            empty_lbl.setObjectName("trashEmptyLabel")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._container_layout.addWidget(empty_lbl)
        else:
            for entry in all_trashed:
                card = TrashItemCard(entry, manifest_root)
                card.restore_clicked.connect(self._restore_one)
                card.delete_clicked.connect(self._delete_one)
                card.checkbox.stateChanged.connect(self._update_buttons)
                self._cards.append(card)
                self._container_layout.addWidget(card)

        self._container_layout.addStretch()
        self._update_count()
        self._update_buttons()

    # ── Private ───────────────────────────────────────────────────────────────

    def _update_count(self):
        n = len(self._cards)
        self._count_lbl.setText(f"{n} item{'s' if n != 1 else ''}" if n else "")
        self._empty_btn.setEnabled(n > 0)
        self._select_all_cb.setVisible(n > 0)

    def _update_buttons(self):
        selected = sum(1 for c in self._cards if c.is_selected())
        self._restore_btn.setEnabled(selected > 0)
        self._restore_btn.setText(
            f"Restore Selected ({selected})" if selected else "Restore Selected"
        )

    def _toggle_select_all(self, state: int):
        checked = state == Qt.CheckState.Checked.value
        for card in self._cards:
            card.set_checked(checked)

    def _restore_one(self, entry: dict):
        try:
            if entry.get("_is_version_trash"):
                self._script_manager.restore_version(entry["uuid"], entry["version_num"])
            else:
                self._script_manager.restore_script(entry.get("uuid"))
        except Exception as exc:
            QMessageBox.warning(self, "Restore Failed", str(exc))
            return
        self.reload()
        self.request_refresh.emit()

    def _delete_one(self, entry: dict):
        if entry.get("_is_version_trash"):
            name = f"Version {entry.get('version_num')} of {entry.get('name', '')}"
        else:
            name = entry.get("name", entry.get("uuid", ""))
        confirm = QMessageBox.question(
            self, "Delete Permanently",
            f"Permanently delete '{name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            if entry.get("_is_version_trash"):
                self._script_manager.permanently_delete_version(entry["uuid"], entry["version_num"])
            else:
                self._script_manager.permanently_delete_script(entry.get("uuid"))
        except Exception as exc:
            QMessageBox.warning(self, "Delete Failed", str(exc))
            return
        self.reload()
        self.request_refresh.emit()

    def _restore_selected(self):
        selected = [c.entry for c in self._cards if c.is_selected()]
        if not selected:
            return
        errors = []
        for entry in selected:
            try:
                if entry.get("_is_version_trash"):
                    self._script_manager.restore_version(entry["uuid"], entry["version_num"])
                else:
                    self._script_manager.restore_script(entry.get("uuid"))
            except Exception as exc:
                errors.append(f"{entry.get('name')}: {exc}")
        if errors:
            QMessageBox.warning(self, "Partial Restore", "\n".join(errors))
        self.reload()
        self.request_refresh.emit()

    def _empty_trash(self):
        n = len(self._cards)
        if not n:
            return
        confirm = QMessageBox.question(
            self, "Empty Trash",
            f"Permanently delete all {n} item{'s' if n != 1 else ''}?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        errors = []
        for card in self._cards:
            entry = card.entry
            try:
                if entry.get("_is_version_trash"):
                    self._script_manager.permanently_delete_version(entry["uuid"], entry["version_num"])
                else:
                    self._script_manager.permanently_delete_script(entry.get("uuid"))
            except Exception as exc:
                errors.append(f"{entry.get('name')}: {exc}")
        if errors:
            QMessageBox.warning(self, "Partial Delete", "\n".join(errors))
        self.reload()
        self.request_refresh.emit()
