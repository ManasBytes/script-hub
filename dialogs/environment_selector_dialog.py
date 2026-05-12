from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from environment_manager import EnvironmentManager


class EnvironmentSelectorDialog(QDialog):
    def __init__(self, environment_manager: EnvironmentManager, selected_refs: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Environments")
        self.setMinimumSize(580, 460)
        self._environment_manager = environment_manager
        self._selected_refs = {str(ref).strip() for ref in (selected_refs or []) if str(ref).strip()}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header row: title + Manage Environments button
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title = QLabel("Choose one or more environments for this script.")
        title.setWordWrap(True)
        title.setObjectName("cardText")

        manage_btn = QPushButton("Manage Environments")
        manage_btn.setObjectName("secondaryButton")
        manage_btn.clicked.connect(self._open_manager)

        header_row.addWidget(title, 1)
        header_row.addWidget(manage_btn)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("analysisBox")

        self.preview_label = QLabel("Template variables will appear here after selection.")
        self.preview_label.setWordWrap(True)
        self.preview_label.setObjectName("hintText")

        self._populate()

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)

        select_all_btn = QPushButton("Select All")
        select_all_btn.setObjectName("secondaryButton")
        select_all_btn.clicked.connect(self._select_all)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("secondaryButton")
        clear_btn.clicked.connect(self._clear_all)

        button_row.addWidget(select_all_btn)
        button_row.addWidget(clear_btn)
        button_row.addStretch()

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("ghostButton")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Use Selected")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self.accept)

        action_row.addStretch()
        action_row.addWidget(cancel_btn)
        action_row.addWidget(save_btn)

        layout.addLayout(header_row)
        layout.addWidget(self.list_widget, 1)
        layout.addWidget(self.preview_label)
        layout.addLayout(button_row)
        layout.addLayout(action_row)

        self.list_widget.itemChanged.connect(self._refresh_preview)
        self._refresh_preview()

    def _open_manager(self) -> None:
        from dialogs.environment_manager_dialog import EnvironmentManagerDialog
        dialog = EnvironmentManagerDialog(self._environment_manager, self)
        dialog.environments_changed.connect(self._repopulate)
        dialog.exec()

    def _repopulate(self) -> None:
        self._selected_refs = set(self.selected_environment_refs())
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.list_widget.blockSignals(False)
        self._populate()
        self._refresh_preview()

    def _populate(self) -> None:
        self.list_widget.blockSignals(True)
        try:
            for env_data in self._environment_manager.list_environments():
                label = self._environment_manager.get_environment_label(env_data.get("uuid", ""))
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, str(env_data.get("uuid", "")))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setCheckState(Qt.CheckState.Checked if str(env_data.get("uuid", "")) in self._selected_refs else Qt.CheckState.Unchecked)
                self.list_widget.addItem(item)
        finally:
            self.list_widget.blockSignals(False)

    def _select_all(self) -> None:
        for index in range(self.list_widget.count()):
            self.list_widget.item(index).setCheckState(Qt.CheckState.Checked)

    def _clear_all(self) -> None:
        for index in range(self.list_widget.count()):
            self.list_widget.item(index).setCheckState(Qt.CheckState.Unchecked)

    def _refresh_preview(self) -> None:
        selected = self.selected_environment_refs()
        if not selected:
            self.preview_label.setText("No environments selected.")
            return

        variable_names = self._environment_manager.list_template_variable_names(selected)
        if variable_names:
            wrapped = ", ".join(f"{{{{{name}}}}}" for name in variable_names)
            self.preview_label.setText(f"Available template variables: {wrapped}")
        else:
            self.preview_label.setText("Selected environments do not define any variables.")

    def selected_environment_refs(self) -> list[str]:
        refs: list[str] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                refs.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return refs
