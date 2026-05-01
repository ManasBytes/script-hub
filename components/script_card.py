from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


class ScriptCardWidget(QFrame):
    selection_changed = pyqtSignal()

    def __init__(self, index, script_data, run_callback, view_callback):
        super().__init__()
        self.setObjectName("scriptCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(136)

        script_name = script_data.get("name") or Path(script_data.get("script_path", "")).stem
        script_path = script_data.get("script_path", "")
        description = script_data.get("description") or "No description provided."
        self.script_uuid = script_data.get("uuid", "")
        version = script_data.get("current_version", 1)
        self.setToolTip(f"{script_name}\nUUID: {self.script_uuid}\nVersion: {version}\n{script_path}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        self.checkbox = QCheckBox()
        self.checkbox.setObjectName("scriptSelectCheckbox")
        self.checkbox.stateChanged.connect(lambda _: self.selection_changed.emit())

        number_badge = QLabel(str(index))
        number_badge.setObjectName("scriptNumberBadge")

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(4)

        name_label = QLabel(script_name)
        name_label.setObjectName("scriptCardTitle")
        name_label.setWordWrap(True)

        path_label = QLabel(f"UUID: {self.script_uuid} • Version {version}")
        path_label.setObjectName("scriptCardUuid")
        path_label.setWordWrap(True)

        text_wrap.addWidget(name_label)
        text_wrap.addWidget(path_label)

        top_row.addWidget(self.checkbox)
        top_row.addWidget(number_badge)
        top_row.addLayout(text_wrap, 1)

        description_label = QLabel(description)
        description_label.setObjectName("scriptCardDescription")
        description_label.setWordWrap(True)
        description_label.setMaximumHeight(42)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addStretch()

        view_button = QPushButton("View")
        view_button.setObjectName("viewScriptButton")
        view_button.clicked.connect(lambda: view_callback(script_data))
        footer.addWidget(view_button)

        run_button = QPushButton("Run")
        run_button.setObjectName("runScriptButton")
        run_button.clicked.connect(lambda: run_callback(script_data))
        footer.addWidget(run_button)

        layout.addLayout(top_row)
        layout.addWidget(description_label)
        layout.addLayout(footer)

    def is_selected(self) -> bool:
        return self.checkbox.isChecked()
