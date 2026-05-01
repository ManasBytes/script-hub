from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from config import get_manifest_root
from registry import load_registry_entries


class Sidebar(QWidget):
    script_selected = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Script Library")
        title.setObjectName("sidebarTitle")

        self.subtitle = QLabel("")
        self.subtitle.setObjectName("sidebarSubtitle")

        self.script_list = QListWidget()
        self.script_list.setObjectName("scriptList")
        self.script_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.script_list.itemClicked.connect(self._on_item_clicked)

        layout.addWidget(title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.script_list)
        layout.addStretch()

        self.reload()

    def reload(self):
        manifest_root = get_manifest_root()
        entries = load_registry_entries(manifest_root)

        entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)

        self.script_list.clear()
        for entry in entries:
            name = entry.get("name") or Path(entry.get("script_path", "")).stem
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(
                f"UUID: {entry.get('uuid', '')}\n"
                f"Added: {entry.get('created_at', '')}\n"
                f"{entry.get('description', '')}"
            )
            self.script_list.addItem(item)

        count = len(entries)
        self.subtitle.setText(f"{count} script{'s' if count != 1 else ''} registered")

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        script_data = item.data(Qt.ItemDataRole.UserRole)
        if script_data:
            self.script_list.clearSelection()
            self.script_selected.emit(script_data)
