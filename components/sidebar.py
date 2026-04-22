from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt


class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Script Library")
        title.setObjectName("sidebarTitle")

        subtitle = QLabel("All your scripts in one place")
        subtitle.setObjectName("sidebarSubtitle")

        script_list = QListWidget()
        script_list.setObjectName("scriptList")

        # Placeholder entries for the initial dashboard shell.
        for script_name in [
            "backup_db.py",
            "cleanup_logs.py",
            "sync_reports.py",
            "generate_invoice.py",
            "health_check.py",
        ]:
            QListWidgetItem(script_name, script_list)

        self.script_list = script_list

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(script_list)
        layout.addStretch()