from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from environment_manager import EnvironmentManager


class _VariableRow(QFrame):
    """Editable row: variable name | value | secret toggle | delete."""

    delete_requested = pyqtSignal()

    def __init__(self, name: str = "", value: str = "", is_secret: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("kvRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self.name_input = QLineEdit(name)
        self.name_input.setObjectName("lineInput")
        self.name_input.setPlaceholderText("Variable name")

        self.value_input = QLineEdit(value)
        self.value_input.setObjectName("lineInput")
        self.value_input.setPlaceholderText("Value")

        self.secret_check = QCheckBox("Secret")
        self.secret_check.setChecked(is_secret)
        self.secret_check.toggled.connect(self._on_secret_toggled)
        if is_secret:
            self.value_input.setEchoMode(QLineEdit.EchoMode.Password)

        delete_btn = QPushButton("✕")
        delete_btn.setObjectName("dangerGhostButton")
        delete_btn.setFixedWidth(32)
        delete_btn.clicked.connect(self.delete_requested.emit)

        layout.addWidget(self.name_input, 2)
        layout.addWidget(self.value_input, 3)
        layout.addWidget(self.secret_check)
        layout.addWidget(delete_btn)

    def _on_secret_toggled(self, checked: bool) -> None:
        self.value_input.setEchoMode(
            QLineEdit.EchoMode.Password if checked else QLineEdit.EchoMode.Normal
        )

    def get_data(self) -> dict | None:
        name = self.name_input.text().strip()
        if not name:
            return None
        return {
            "name": name,
            "value": self.value_input.text(),
            "is_secret": self.secret_check.isChecked(),
        }


class EnvironmentManagerDialog(QDialog):
    """Bruno-style environment manager: list on the left, variable editor on the right."""

    environments_changed = pyqtSignal()

    def __init__(self, environment_manager: EnvironmentManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Environments")
        self.setMinimumSize(880, 580)
        self._environment_manager = environment_manager
        self._current_env_uuid: str | None = None
        self._variable_rows: list[_VariableRow] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left panel: environment list ──────────────────────────────────
        left_panel = QFrame()
        left_panel.setObjectName("envManagerLeft")
        left_panel.setFixedWidth(230)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 16, 12, 12)
        left_layout.setSpacing(8)

        left_title = QLabel("Environments")
        left_title.setObjectName("cardTitle")

        self.env_list = QListWidget()
        self.env_list.setObjectName("analysisBox")
        self.env_list.currentItemChanged.connect(self._on_env_selected)

        add_env_btn = QPushButton("+ New Environment")
        add_env_btn.setObjectName("primaryButton")
        add_env_btn.clicked.connect(self._add_environment)

        left_layout.addWidget(left_title)
        left_layout.addWidget(self.env_list, 1)
        left_layout.addWidget(add_env_btn)

        # ── Vertical separator ─────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("detailDivider")

        # ── Right stack: placeholder vs editor ─────────────────────────────
        self.right_stack = QStackedWidget()

        placeholder = QLabel("Select an environment or create a new one.")
        placeholder.setObjectName("hintText")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_stack.addWidget(placeholder)   # index 0

        # Editor panel
        editor = QFrame()
        editor.setObjectName("envManagerRight")
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(20, 16, 20, 16)
        editor_layout.setSpacing(12)

        # Name + delete row
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(8)

        name_lbl = QLabel("Name:")
        name_lbl.setObjectName("sectionLabel")
        name_lbl.setFixedWidth(52)

        self.env_name_input = QLineEdit()
        self.env_name_input.setObjectName("lineInput")
        self.env_name_input.setPlaceholderText("Environment name")

        self.delete_env_btn = QPushButton("Delete")
        self.delete_env_btn.setObjectName("dangerGhostButton")
        self.delete_env_btn.clicked.connect(self._delete_environment)

        name_row.addWidget(name_lbl)
        name_row.addWidget(self.env_name_input, 1)
        name_row.addWidget(self.delete_env_btn)

        # Column header bar
        col_header = QFrame()
        col_header.setObjectName("kvRow")
        ch = QHBoxLayout(col_header)
        ch.setContentsMargins(8, 4, 8, 4)
        ch.setSpacing(8)
        for text, stretch in [("Variable Name", 2), ("Value", 3)]:
            lbl = QLabel(text)
            lbl.setObjectName("sectionLabel")
            ch.addWidget(lbl, stretch)
        secret_hdr = QLabel("Secret")
        secret_hdr.setObjectName("sectionLabel")
        ch.addWidget(secret_hdr)
        spacer_w = QWidget()
        spacer_w.setFixedWidth(32)
        ch.addWidget(spacer_w)

        # Scrollable variable rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.vars_widget = QWidget()
        self.vars_layout = QVBoxLayout(self.vars_widget)
        self.vars_layout.setContentsMargins(0, 0, 0, 0)
        self.vars_layout.setSpacing(4)
        self.vars_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.vars_widget)

        add_var_btn = QPushButton("+ Add Variable")
        add_var_btn.setObjectName("secondaryButton")
        add_var_btn.clicked.connect(lambda: self._add_variable_row())

        # Bottom actions
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("ghostButton")
        close_btn.clicked.connect(self.accept)

        save_btn = QPushButton("Save Environment")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_environment)

        actions.addWidget(close_btn)
        actions.addStretch()
        actions.addWidget(save_btn)

        editor_layout.addLayout(name_row)
        editor_layout.addWidget(col_header)
        editor_layout.addWidget(scroll, 1)
        editor_layout.addWidget(add_var_btn)
        editor_layout.addLayout(actions)

        self.right_stack.addWidget(editor)  # index 1

        root.addWidget(left_panel)
        root.addWidget(sep)
        root.addWidget(self.right_stack, 1)

        self._populate_env_list()

    # ── List management ───────────────────────────────────────────────────

    def _populate_env_list(self) -> None:
        target_uuid = self._current_env_uuid
        self.env_list.blockSignals(True)
        self.env_list.clear()
        for env in self._environment_manager.list_environments():
            item = QListWidgetItem(env.get("name", "Unnamed"))
            item.setData(Qt.ItemDataRole.UserRole, str(env.get("uuid", "")))
            self.env_list.addItem(item)
        self.env_list.blockSignals(False)

        if target_uuid:
            for i in range(self.env_list.count()):
                item = self.env_list.item(i)
                if str(item.data(Qt.ItemDataRole.UserRole)) == target_uuid:
                    self.env_list.setCurrentItem(item)
                    return

    def _on_env_selected(self, current: QListWidgetItem | None, _previous) -> None:
        if current is None:
            self._current_env_uuid = None
            self.right_stack.setCurrentIndex(0)
            return
        self._load_env_for_editing(str(current.data(Qt.ItemDataRole.UserRole)))

    # ── Editor loading ────────────────────────────────────────────────────

    def _load_env_for_editing(self, env_uuid: str) -> None:
        try:
            env_data = self._environment_manager.get_environment(
                env_uuid, include_secret_values=True
            )
        except Exception:
            return

        self._current_env_uuid = env_uuid

        self.env_name_input.blockSignals(True)
        self.env_name_input.setText(env_data.get("name", ""))
        self.env_name_input.blockSignals(False)

        self._clear_variable_rows()

        for var_name, payload in (env_data.get("variables") or {}).items():
            if not isinstance(payload, dict):
                continue
            self._add_variable_row(
                name=str(var_name),
                value=str(payload.get("value", "")),
                is_secret=bool(payload.get("is_secret", False)),
            )

        self.right_stack.setCurrentIndex(1)

    def _clear_variable_rows(self) -> None:
        for row in self._variable_rows:
            row.deleteLater()
        self._variable_rows.clear()

    # ── Variable row management ───────────────────────────────────────────

    def _add_variable_row(self, name: str = "", value: str = "", is_secret: bool = False) -> None:
        row = _VariableRow(name=name, value=value, is_secret=is_secret)
        row.delete_requested.connect(lambda r=row: self._remove_variable_row(r))
        self.vars_layout.addWidget(row)
        self._variable_rows.append(row)

    def _remove_variable_row(self, row: _VariableRow) -> None:
        if row in self._variable_rows:
            self._variable_rows.remove(row)
        row.deleteLater()

    # ── CRUD actions ──────────────────────────────────────────────────────

    def _add_environment(self) -> None:
        name, ok = QInputDialog.getText(self, "New Environment", "Environment name:")
        if not ok or not name.strip():
            return
        try:
            env = self._environment_manager.create_environment(name.strip())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._current_env_uuid = str(env.get("uuid", ""))
        self.environments_changed.emit()
        self._populate_env_list()

    def _delete_environment(self) -> None:
        if not self._current_env_uuid:
            return
        env_name = self.env_name_input.text().strip() or "this environment"
        confirm = QMessageBox.question(
            self, "Delete Environment",
            f"Permanently delete '{env_name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._environment_manager.delete_environment(self._current_env_uuid, permanent=True)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._current_env_uuid = None
        self._clear_variable_rows()
        self.right_stack.setCurrentIndex(0)
        self.environments_changed.emit()
        self._populate_env_list()

    def _save_environment(self) -> None:
        if not self._current_env_uuid:
            return
        name = self.env_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a name for this environment.")
            return
        variables: dict[str, dict] = {}
        seen: set[str] = set()
        for row in self._variable_rows:
            data = row.get_data()
            if data is None:
                continue
            var_name = data["name"]
            if var_name in seen:
                QMessageBox.warning(
                    self, "Duplicate Variable",
                    f"Variable '{var_name}' appears more than once.",
                )
                return
            seen.add(var_name)
            variables[var_name] = {"value": data["value"], "is_secret": data["is_secret"]}
        try:
            self._environment_manager.update_environment(
                self._current_env_uuid, name=name, variables=variables,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.environments_changed.emit()
        self._populate_env_list()
        QMessageBox.information(self, "Saved", f"Environment '{name}' saved successfully.")
