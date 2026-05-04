from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from script_manager import ScriptManager


def _fmt_ts(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str).astimezone()
        return dt.strftime("%b %d, %Y  %H:%M")
    except Exception:
        return iso_str[:16].replace("T", "  ")


class RollbackDialog(QDialog):
    """Shows all active (non-trashed) versions; lets user switch the active version."""

    version_changed = pyqtSignal(dict)

    def __init__(self, script_data: dict, script_manager: ScriptManager, parent=None):
        super().__init__(parent)
        self._script_data = script_data
        self._script_manager = script_manager

        self.setWindowTitle(f"Version History — {script_data.get('name', '')}")
        self.setMinimumSize(520, 420)
        self.setObjectName("RollbackDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel(f"Version History: {script_data.get('name', '')}")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Select a version to make it the active (current) version. "
            "The script will run using the chosen version's file and metadata."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 4, 0, 4)
        container_layout.setSpacing(8)

        versions = script_data.get("versions", {})
        current_ver = script_data.get("current_version", 1)

        sorted_versions = sorted(
            [(int(k), v) for k, v in versions.items() if not v.get("trashed")],
            reverse=True,
        )

        if not sorted_versions:
            empty = QLabel("No active versions found.")
            empty.setObjectName("hintText")
            container_layout.addWidget(empty)
        else:
            for ver_num, ver_data in sorted_versions:
                card = self._build_version_card(ver_num, ver_data, ver_num == current_ver)
                container_layout.addWidget(card)

        container_layout.addStretch()
        scroll.setWidget(container)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("ghostButton")
        close_btn.clicked.connect(self.reject)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(scroll, 1)
        root.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _build_version_card(self, ver_num: int, ver_data: dict, is_current: bool) -> QFrame:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        ver_lbl = QLabel(f"Version {ver_num}")
        ver_lbl.setObjectName("cardTitle")
        top.addWidget(ver_lbl)

        if is_current:
            badge = QLabel("Active")
            badge.setObjectName("versionActiveBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            top.addWidget(badge)

        top.addStretch()

        if not is_current:
            use_btn = QPushButton("Use This Version")
            use_btn.setObjectName("primaryButton")
            use_btn.clicked.connect(lambda _=False, vn=ver_num: self._activate(vn))
            top.addWidget(use_btn)

        layout.addLayout(top)

        desc = ver_data.get("description", "").strip()
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setObjectName("cardText")
            desc_lbl.setWordWrap(True)
            layout.addWidget(desc_lbl)

        created = _fmt_ts(ver_data.get("version_created_at", ""))
        meta = QLabel(f"Created: {created}")
        meta.setObjectName("detailMetaValue")
        layout.addWidget(meta)

        return card

    def _activate(self, ver_num: int):
        script_uuid = self._script_data.get("uuid")
        try:
            updated = self._script_manager.set_active_version(script_uuid, ver_num)
        except Exception as exc:
            QMessageBox.critical(self, "Rollback Failed", str(exc))
            return
        self.version_changed.emit(updated)
        self.accept()
