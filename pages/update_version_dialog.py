from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pages.add_script_page import KeyTypeEditor, _BreadcrumbItem
from script_manager import ScriptManager
from workers import ScriptAnalysisWorker


class UpdateVersionDialog(QDialog):
    """5-step wizard dialog for uploading a new version of an existing script."""

    version_added = pyqtSignal(dict)

    def __init__(self, script_data: dict, script_manager: ScriptManager, parent=None):
        super().__init__(parent)
        self._script_data = script_data
        self._script_manager = script_manager
        self._detected_dependencies: list[str] = []
        self._analysis_worker: ScriptAnalysisWorker | None = None

        current_ver = script_data.get("current_version", 1)
        self.setWindowTitle(f"Update Script — Version {current_ver} → {current_ver + 1}")
        self.setMinimumSize(720, 580)
        self.setObjectName("UpdateVersionDialog")

        self.step_titles = [
            "1. Upload New Version",
            "2. Input Variables",
            "3. Config Variables",
            "4. Output Variables",
            "5. Validation",
        ]

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(12)

        hdr_title = QLabel(f"Update Script: {script_data.get('name', '')}")
        hdr_title.setObjectName("pageTitle")
        hdr_sub = QLabel(
            f"Upload a new .py file to create version {current_ver + 1}. "
            "Variables are pre-filled from the current version — edit as needed."
        )
        hdr_sub.setObjectName("pageSubtitle")
        hdr_sub.setWordWrap(True)

        self.step_label = QLabel("")
        self.step_label.setObjectName("stepIndicator")

        breadcrumb_bar = QFrame()
        breadcrumb_bar.setObjectName("wizardBreadcrumbBar")
        bc_layout = QHBoxLayout(breadcrumb_bar)
        bc_layout.setContentsMargins(12, 8, 12, 8)
        bc_layout.setSpacing(8)
        self.breadcrumb_items: list[_BreadcrumbItem] = []
        for i, title in enumerate(self.step_titles):
            item = _BreadcrumbItem(title, i)
            item.setObjectName("wizardBreadcrumbItem")
            item.setProperty("state", "pending")
            item.clicked.connect(self._go_to_step)
            self.breadcrumb_items.append(item)
            bc_layout.addWidget(item)
            if i < len(self.step_titles) - 1:
                sep = QLabel(">")
                sep.setObjectName("wizardBreadcrumbSep")
                bc_layout.addWidget(sep)
        bc_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        self.steps = QStackedWidget()
        self.steps.setObjectName("wizardStack")
        self.steps.addWidget(self._build_upload_step())
        self.steps.addWidget(self._build_inputs_step())
        self.steps.addWidget(self._build_config_step())
        self.steps.addWidget(self._build_outputs_step())
        self.steps.addWidget(self._build_validation_step())
        scroll_layout.addWidget(self.steps)
        scroll.setWidget(scroll_content)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("ghostButton")
        cancel_btn.clicked.connect(self.reject)

        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("ghostButton")
        self.back_btn.clicked.connect(self._prev_step)

        self.next_btn = QPushButton("Next")
        self.next_btn.setObjectName("primaryButton")
        self.next_btn.clicked.connect(self._next_step)

        actions.addWidget(cancel_btn)
        actions.addStretch()
        actions.addWidget(self.back_btn)
        actions.addWidget(self.next_btn)

        root.addWidget(hdr_title)
        root.addWidget(hdr_sub)
        root.addWidget(breadcrumb_bar)
        root.addWidget(self.step_label)
        root.addWidget(scroll, 1)
        root.addLayout(actions)

        self._prefill()
        self._update_step_ui()

    # ── Step builders ─────────────────────────────────────────────────────────

    def _build_step_card(self, heading, description):
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)
        title = QLabel(heading)
        title.setObjectName("cardTitle")
        text = QLabel(description)
        text.setObjectName("cardText")
        text.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(text)
        return card, layout

    def _build_upload_step(self):
        card, layout = self._build_step_card(
            "Upload New Script File",
            "Select the updated .py file. The name and description are pre-filled from the current version.",
        )

        name_label = QLabel("Script Name")
        name_label.setObjectName("sectionLabel")
        self.script_name_input = QLineEdit()
        self.script_name_input.setObjectName("lineInput")

        path_label = QLabel("New Script File")
        path_label.setObjectName("sectionLabel")
        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(8)
        self.script_path_input = QLineEdit()
        self.script_path_input.setObjectName("lineInput")
        self.script_path_input.setPlaceholderText("Choose the updated .py file")
        self.script_path_input.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("secondaryButton")
        browse_btn.clicked.connect(self._choose_script)
        path_row.addWidget(self.script_path_input, 1)
        path_row.addWidget(browse_btn)

        desc_label = QLabel("Description")
        desc_label.setObjectName("sectionLabel")
        self.script_description_input = QPlainTextEdit()
        self.script_description_input.setObjectName("descriptionInput")
        self.script_description_input.setFixedHeight(88)

        help_label = QLabel("Help File (optional)")
        help_label.setObjectName("sectionLabel")
        help_row = QHBoxLayout()
        help_row.setContentsMargins(0, 0, 0, 0)
        help_row.setSpacing(8)
        self.help_path_input = QLineEdit()
        self.help_path_input.setObjectName("lineInput")
        self.help_path_input.setPlaceholderText("Attach a help or documentation file")
        self.help_path_input.setReadOnly(True)
        help_browse = QPushButton("Browse")
        help_browse.setObjectName("secondaryButton")
        help_browse.clicked.connect(self._choose_help_file)
        help_row.addWidget(self.help_path_input, 1)
        help_row.addWidget(help_browse)

        layout.addWidget(name_label)
        layout.addWidget(self.script_name_input)
        layout.addWidget(path_label)
        layout.addLayout(path_row)
        layout.addWidget(desc_label)
        layout.addWidget(self.script_description_input)
        layout.addWidget(help_label)
        layout.addLayout(help_row)
        return card

    def _build_inputs_step(self):
        card, layout = self._build_step_card(
            "Input Variables",
            "Pre-filled from the current version. Add new variables or edit existing ones.",
        )
        self.inputs_editor = KeyTypeEditor("Input variable name", [".xlsx", ".xls", ".csv", "Directory"])
        layout.addWidget(self.inputs_editor)
        return card

    def _build_config_step(self):
        card, layout = self._build_step_card(
            "Config Variables",
            "Pre-filled from the current version.",
        )
        self.config_editor = KeyTypeEditor("Config variable name", ["string", "int", "float", "bool"])
        layout.addWidget(self.config_editor)
        return card

    def _build_outputs_step(self):
        card, layout = self._build_step_card(
            "Output Variables",
            "Pre-filled from the current version.",
        )
        self.outputs_editor = KeyTypeEditor("Output variable name", [".xlsx", ".xls", ".csv", "Directory"])
        layout.addWidget(self.outputs_editor)
        return card

    def _build_validation_step(self):
        card, layout = self._build_step_card(
            "Validation",
            "Review your update and wait for script analysis to complete.",
        )
        summary_heading = QLabel("Summary")
        summary_heading.setObjectName("sectionLabel")
        self.validation_box = QPlainTextEdit()
        self.validation_box.setObjectName("summaryBox")
        self.validation_box.setReadOnly(True)
        self.validation_box.setFixedHeight(130)
        analysis_heading = QLabel("Script Analysis")
        analysis_heading.setObjectName("sectionLabel")
        self.analysis_status = QLabel("Analysis will run when you reach this step.")
        self.analysis_status.setObjectName("hintText")
        self.analysis_box = QPlainTextEdit()
        self.analysis_box.setObjectName("analysisBox")
        self.analysis_box.setReadOnly(True)
        self.analysis_box.setMinimumHeight(200)
        layout.addWidget(summary_heading)
        layout.addWidget(self.validation_box)
        layout.addWidget(analysis_heading)
        layout.addWidget(self.analysis_status)
        layout.addWidget(self.analysis_box)
        return card

    # ── Pre-fill ──────────────────────────────────────────────────────────────

    def _prefill(self):
        d = self._script_data
        self.script_name_input.setText(d.get("name", ""))
        self.script_description_input.setPlainText(d.get("description", ""))
        self.help_path_input.setText(d.get("help_file_path", ""))
        self._prefill_editor(self.inputs_editor, d.get("input_variables", []))
        self._prefill_editor(self.config_editor, d.get("config_variable", []))
        self._prefill_editor(self.outputs_editor, d.get("output_variable", []))

    def _prefill_editor(self, editor: KeyTypeEditor, variables: list):
        if not variables:
            return
        # Remove default empty row
        while editor.rows:
            editor.rows[-1][0].deleteLater()
            editor.rows.pop()
        for var in variables:
            editor.add_row()
            row_wrap, key_input, type_combo = editor.rows[-1]
            key_input.setText(var.get("name", ""))
            var_type = var.get("type", "")
            idx = type_combo.findText(var_type, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                type_combo.setCurrentIndex(idx)
            else:
                type_combo.setCurrentText(var_type)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _choose_script(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Updated Python Script", str(Path.home()), "Python Scripts (*.py)")
        if path:
            self.script_path_input.setText(path)

    def _choose_help_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Help File", str(Path.home()), "All Files (*)")
        if path:
            self.help_path_input.setText(path)

    def _prev_step(self):
        idx = self.steps.currentIndex()
        if idx > 0:
            self.steps.setCurrentIndex(idx - 1)
            self._update_step_ui()

    def _next_step(self):
        idx = self.steps.currentIndex()
        if idx == 0 and not self._validate_upload_step():
            return
        if idx == self.steps.count() - 1:
            self._submit()
            return
        if idx == self.steps.count() - 2:
            self._build_validation_summary()
            self._run_analysis()
        self.steps.setCurrentIndex(idx + 1)
        self._update_step_ui()

    def _validate_upload_step(self) -> bool:
        if not self.script_name_input.text().strip():
            QMessageBox.warning(self, "Missing Name", "Please enter a script name.")
            return False
        path = self.script_path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Missing File", "Please select a .py file for the new version.")
            return False
        if Path(path).suffix.lower() != ".py":
            QMessageBox.warning(self, "Invalid File", "Only .py files are allowed.")
            return False
        return True

    def _submit(self):
        payload = self._collect_data()
        try:
            updated = self._script_manager.add_version(self._script_data["uuid"], payload)
        except Exception as exc:
            QMessageBox.critical(self, "Update Failed", str(exc))
            return
        self.version_added.emit(updated)
        self.accept()

    def _collect_data(self) -> dict:
        return {
            "name": self.script_name_input.text().strip(),
            "description": self.script_description_input.toPlainText().strip(),
            "script_path": self.script_path_input.text().strip(),
            "help_file_path": self.help_path_input.text().strip(),
            "input_variables": self.inputs_editor.get_pairs(),
            "config_variable": self.config_editor.get_pairs(),
            "output_variable": self.outputs_editor.get_pairs(),
            "dependencies": self._detected_dependencies,
        }

    # ── Validation summary ────────────────────────────────────────────────────

    def _build_validation_summary(self):
        d = self._collect_data()
        lines = [
            f"Name: {d['name'] or '(not set)'}",
            f"New File: {d['script_path'] or '(not set)'}",
            f"Description: {d['description'] or '(not set)'}",
            "",
            "Input Variables:",
        ]
        for v in d["input_variables"]:
            lines.append(f"  {v['name']}: {v['type']}")
        if not d["input_variables"]:
            lines.append("  None")
        lines += ["", "Config Variables:"]
        for v in d["config_variable"]:
            lines.append(f"  {v['name']}: {v['type']}")
        if not d["config_variable"]:
            lines.append("  None")
        lines += ["", "Output Variables:"]
        for v in d["output_variable"]:
            lines.append(f"  {v['name']}: {v['type']}")
        if not d["output_variable"]:
            lines.append("  None")
        self.validation_box.setPlainText("\n".join(lines))

    def _run_analysis(self):
        if self._analysis_worker is not None:
            try:
                self._analysis_worker.analysis_complete.disconnect()
                self._analysis_worker.analysis_failed.disconnect()
            except RuntimeError:
                pass

        self.analysis_status.setText("Analyzing script…")
        self.analysis_box.setPlainText("Please wait — running AST analysis in background.")
        self.next_btn.setEnabled(False)

        d = self._collect_data()
        self._analysis_worker = ScriptAnalysisWorker(
            d["script_path"], d["input_variables"], d["config_variable"], d["output_variable"]
        )
        self._analysis_worker.analysis_complete.connect(self._on_analysis_complete)
        self._analysis_worker.analysis_failed.connect(self._on_analysis_failed)
        self._analysis_worker.start()

    def _on_analysis_complete(self, result: dict) -> None:
        self.next_btn.setEnabled(True)
        self._detected_dependencies = result.get("dependencies", [])
        lines = []
        deps = result.get("dependencies", [])
        if deps:
            lines.append(f"Dependencies detected ({len(deps)}):")
            for dep in deps:
                lines.append(f"  • {dep}")
        else:
            lines.append("Dependencies: none detected.")
        variables = result.get("variables", {})
        if variables:
            lines += ["", "Variable Check:"]
            for name, info in variables.items():
                found = info["found"]
                line_no = info.get("first_line", "?")
                marker = "✓" if found else "✗"
                detail = f"line {line_no}" if found else "NOT FOUND"
                lines.append(f"  {marker} {name} [{info['category']} / {info['declared_type']}] — {detail}")
        self.analysis_status.setText("Analysis complete.")
        self.analysis_box.setPlainText("\n".join(lines))

    def _on_analysis_failed(self, error: str) -> None:
        self.next_btn.setEnabled(True)
        self.analysis_status.setText("Analysis failed.")
        self.analysis_box.setPlainText(f"Error during analysis:\n{error}")

    # ── Breadcrumb / step UI ──────────────────────────────────────────────────

    def _go_to_step(self, index: int) -> None:
        if index < self.steps.currentIndex():
            self.steps.setCurrentIndex(index)
            self._update_step_ui()

    def _update_step_ui(self):
        idx = self.steps.currentIndex()
        self.step_label.setText(f"Step {idx + 1} of {len(self.step_titles)}")
        self.back_btn.setEnabled(idx > 0)

        for i, item in enumerate(self.breadcrumb_items):
            if i < idx:
                state = "done"
            elif i == idx:
                state = "active"
            else:
                state = "pending"
            item.setProperty("state", state)
            item.style().unpolish(item)
            item.style().polish(item)
            item.update()
            item.setCursor(
                Qt.CursorShape.PointingHandCursor if state == "done" else Qt.CursorShape.ArrowCursor
            )

        self.next_btn.setText("Update Script" if idx == self.steps.count() - 1 else "Next")
