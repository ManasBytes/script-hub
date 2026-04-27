from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
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

from workers import ScriptAnalysisWorker


class _BreadcrumbItem(QLabel):
    """A QLabel that emits clicked(index) on mouse press."""

    clicked = pyqtSignal(int)

    def __init__(self, title: str, index: int) -> None:
        super().__init__(title)
        self._index = index

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._index)
        super().mousePressEvent(event)


def create_searchable_combo(options):
    combo = QComboBox()
    combo.setObjectName("typeCombo")
    combo.setEditable(True)
    combo.addItems(options)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    completer = combo.completer()
    if isinstance(completer, QCompleter):
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
    combo.setCurrentIndex(0)
    return combo


class KeyTypeEditor(QFrame):
    def __init__(self, key_placeholder, options):
        super().__init__()
        self.setObjectName("kvEditor")
        self._options = options

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        label = QLabel("Key Value Pairs")
        label.setObjectName("sectionLabel")

        add_button = QPushButton("+ Add")
        add_button.setObjectName("smallPrimaryButton")
        add_button.clicked.connect(self.add_row)

        header.addWidget(label)
        header.addStretch()
        header.addWidget(add_button)

        self.rows_wrap = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_wrap)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.key_placeholder = key_placeholder
        self.rows = []

        layout.addLayout(header)
        layout.addWidget(self.rows_wrap)

        self.add_row()

    def add_row(self):
        row_wrap = QFrame()
        row_wrap.setObjectName("kvRow")
        row_layout = QHBoxLayout(row_wrap)
        row_layout.setContentsMargins(10, 8, 10, 8)
        row_layout.setSpacing(8)

        key_input = QLineEdit()
        key_input.setObjectName("lineInput")
        key_input.setPlaceholderText(self.key_placeholder)

        type_combo = create_searchable_combo(self._options)

        remove_button = QPushButton("Remove")
        remove_button.setObjectName("dangerGhostButton")

        row_layout.addWidget(key_input, 2)
        row_layout.addWidget(type_combo, 2)
        row_layout.addWidget(remove_button)

        self.rows_layout.addWidget(row_wrap)
        self.rows.append((row_wrap, key_input, type_combo))

        remove_button.clicked.connect(lambda: self.remove_row(row_wrap))

    def remove_row(self, row_wrap):
        if len(self.rows) == 1:
            self.rows[0][1].clear()
            self.rows[0][2].setCurrentIndex(0)
            return

        for i, item in enumerate(self.rows):
            if item[0] is row_wrap:
                self.rows.pop(i)
                break
        row_wrap.deleteLater()

    def get_pairs(self):
        pairs = []
        for _, key_input, type_combo in self.rows:
            key = key_input.text().strip()
            value_type = type_combo.currentText().strip()
            if key:
                pairs.append({"name": key, "type": value_type})
        return pairs


class AddScriptPage(QWidget):
    back_to_scripts = pyqtSignal()
    submit_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setObjectName("AddScriptPage")
        self._detected_dependencies: list[str] = []
        self._analysis_worker: ScriptAnalysisWorker | None = None

        self.step_titles = [
            "1. Upload Script",
            "2. Input Variables",
            "3. Config Variables",
            "4. Output Variables",
            "5. Validation",
        ]

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        header_title = QLabel("Add Script")
        header_title.setObjectName("pageTitle")
        header_subtitle = QLabel("Follow the steps to register a new Python script.")
        header_subtitle.setObjectName("pageSubtitle")

        self.step_label = QLabel("")
        self.step_label.setObjectName("stepIndicator")

        self.breadcrumb_bar = QFrame()
        self.breadcrumb_bar.setObjectName("wizardBreadcrumbBar")
        breadcrumb_layout = QHBoxLayout(self.breadcrumb_bar)
        breadcrumb_layout.setContentsMargins(12, 8, 12, 8)
        breadcrumb_layout.setSpacing(8)

        self.breadcrumb_items: list[_BreadcrumbItem] = []
        for i, title in enumerate(self.step_titles):
            item = _BreadcrumbItem(title, i)
            item.setObjectName("wizardBreadcrumbItem")
            item.setProperty("state", "pending")
            item.clicked.connect(self._go_to_step)
            self.breadcrumb_items.append(item)
            breadcrumb_layout.addWidget(item)
            if i < len(self.step_titles) - 1:
                sep = QLabel(">")
                sep.setObjectName("wizardBreadcrumbSep")
                breadcrumb_layout.addWidget(sep)
        breadcrumb_layout.addStretch()

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

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("ghostButton")
        self.cancel_button.clicked.connect(self.back_to_scripts.emit)

        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("ghostButton")
        self.back_button.clicked.connect(self.prev_step)

        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("primaryButton")
        self.next_button.clicked.connect(self.next_step)

        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.back_button)
        actions.addWidget(self.next_button)

        main_layout.addWidget(header_title)
        main_layout.addWidget(header_subtitle)
        main_layout.addWidget(self.breadcrumb_bar)
        main_layout.addWidget(self.step_label)
        main_layout.addWidget(scroll, 1)
        main_layout.addLayout(actions)

        self.update_step_ui()

    # ------------------------------------------------------------------ #
    #  Step builders                                                       #
    # ------------------------------------------------------------------ #

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
            "Upload Python Script",
            "Enter a script name and select the .py file to register.",
        )

        name_label = QLabel("Script Name")
        name_label.setObjectName("sectionLabel")

        self.script_name_input = QLineEdit()
        self.script_name_input.setObjectName("lineInput")
        self.script_name_input.setPlaceholderText("Enter a friendly script name")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.script_path_input = QLineEdit()
        self.script_path_input.setObjectName("lineInput")
        self.script_path_input.setPlaceholderText("Choose a Python script (.py)")
        self.script_path_input.setReadOnly(True)

        browse = QPushButton("Browse")
        browse.setObjectName("secondaryButton")
        browse.clicked.connect(self.choose_script)

        row.addWidget(self.script_path_input, 1)
        row.addWidget(browse)

        description_label = QLabel("Description (optional)")
        description_label.setObjectName("sectionLabel")

        self.script_description_input = QPlainTextEdit()
        self.script_description_input.setObjectName("descriptionInput")
        self.script_description_input.setPlaceholderText("Write a short summary of what this script does")
        self.script_description_input.setFixedHeight(88)

        note = QLabel("Only Python script files with .py extension are supported.")
        note.setObjectName("hintText")

        help_label = QLabel("Help File (optional)")
        help_label.setObjectName("sectionLabel")

        help_row = QHBoxLayout()
        help_row.setContentsMargins(0, 0, 0, 0)
        help_row.setSpacing(8)

        self.help_path_input = QLineEdit()
        self.help_path_input.setObjectName("lineInput")
        self.help_path_input.setPlaceholderText("Attach a help or documentation file (any type)")
        self.help_path_input.setReadOnly(True)

        help_browse = QPushButton("Browse")
        help_browse.setObjectName("secondaryButton")
        help_browse.clicked.connect(self.choose_help_file)

        help_row.addWidget(self.help_path_input, 1)
        help_row.addWidget(help_browse)

        layout.addWidget(name_label)
        layout.addWidget(self.script_name_input)
        layout.addLayout(row)
        layout.addWidget(description_label)
        layout.addWidget(self.script_description_input)
        layout.addWidget(note)
        layout.addWidget(help_label)
        layout.addLayout(help_row)
        return card

    def _build_inputs_step(self):
        card, layout = self._build_step_card(
            "Input Variables",
            "Add one or more input variable names and select the expected input type.",
        )

        self.inputs_editor = KeyTypeEditor(
            "Input variable name",
            [".xlsx", ".xls", ".csv", "Directory"],
        )

        layout.addWidget(self.inputs_editor)
        return card

    def _build_config_step(self):
        card, layout = self._build_step_card(
            "Config Variables",
            "Define configurable variables and their value type.",
        )

        self.config_editor = KeyTypeEditor(
            "Config variable name",
            ["string", "int", "float", "bool"],
        )

        layout.addWidget(self.config_editor)
        return card

    def _build_outputs_step(self):
        card, layout = self._build_step_card(
            "Output Variables",
            "Define where each output will be written by the script.",
        )

        self.outputs_editor = KeyTypeEditor(
            "Output variable name",
            [".xlsx", ".xls", ".csv", "Directory"],
        )

        layout.addWidget(self.outputs_editor)
        return card

    def _build_validation_step(self):
        card, layout = self._build_step_card(
            "Validation",
            "Review your setup and wait for the script analysis to complete.",
        )

        summary_heading = QLabel("Script Summary")
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

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def choose_script(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Python Script",
            str(Path.home()),
            "Python Scripts (*.py)",
        )
        if file_path:
            self.script_path_input.setText(file_path)

    def choose_help_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Help File",
            str(Path.home()),
            "All Files (*)",
        )
        if file_path:
            self.help_path_input.setText(file_path)

    def prev_step(self):
        idx = self.steps.currentIndex()
        if idx > 0:
            self.steps.setCurrentIndex(idx - 1)
            self.update_step_ui()

    def next_step(self):
        idx = self.steps.currentIndex()
        if idx == 0 and not self._validate_upload_step():
            return

        if idx == self.steps.count() - 1:
            self.submit_requested.emit(self.collect_submission_data())
            return

        if idx == self.steps.count() - 2:
            self._build_validation_summary()
            self._run_analysis()

        self.steps.setCurrentIndex(idx + 1)
        self.update_step_ui()

    def _validate_upload_step(self):
        script_name = self.script_name_input.text().strip()
        script_path = self.script_path_input.text().strip()
        if not script_name:
            QMessageBox.warning(self, "Missing Name", "Please enter a script name before continuing.")
            return False
        if not script_path:
            QMessageBox.warning(self, "Missing Script", "Please upload a .py script file to continue.")
            return False
        if Path(script_path).suffix.lower() != ".py":
            QMessageBox.warning(self, "Invalid File", "Only .py files are allowed.")
            return False
        return True

    def collect_submission_data(self):
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

    # ------------------------------------------------------------------ #
    #  Validation summary (form data)                                     #
    # ------------------------------------------------------------------ #

    def _build_validation_summary(self):
        lines = [
            "Name:",
            self.script_name_input.text().strip() or "(not set)",
            "",
            "Script Path:",
            self.script_path_input.text().strip() or "(not set)",
            "",
            "Description:",
            self.script_description_input.toPlainText().strip() or "(not set)",
            "",
            "Input Variables:",
        ]

        input_pairs = self.inputs_editor.get_pairs()
        config_pairs = self.config_editor.get_pairs()
        output_pairs = self.outputs_editor.get_pairs()

        if input_pairs:
            for item in input_pairs:
                lines.append(f"  {item['name']}: {item['type']}")
        else:
            lines.append("  None")

        lines.append("")
        lines.append("Config Variables:")
        if config_pairs:
            for item in config_pairs:
                lines.append(f"  {item['name']}: {item['type']}")
        else:
            lines.append("  None")

        lines.append("")
        lines.append("Output Variables:")
        if output_pairs:
            for item in output_pairs:
                lines.append(f"  {item['name']}: {item['type']}")
        else:
            lines.append("  None")

        lines.append("")
        lines.append("Help File:")
        lines.append(f"  {self.help_path_input.text().strip() or 'None'}")

        self.validation_box.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------ #
    #  Background script analysis                                          #
    # ------------------------------------------------------------------ #

    def _run_analysis(self):
        # Disconnect any previous worker so stale results don't land in the UI.
        if self._analysis_worker is not None:
            try:
                self._analysis_worker.analysis_complete.disconnect()
                self._analysis_worker.analysis_failed.disconnect()
            except RuntimeError:
                pass

        self.analysis_status.setText("Analyzing script…")
        self.analysis_box.setPlainText("Please wait — running AST analysis in background.")
        self.next_button.setEnabled(False)

        data = self.collect_submission_data()
        self._analysis_worker = ScriptAnalysisWorker(
            data["script_path"],
            data["input_variables"],
            data["config_variable"],
            data["output_variable"],
        )
        self._analysis_worker.analysis_complete.connect(self._on_analysis_complete)
        self._analysis_worker.analysis_failed.connect(self._on_analysis_failed)
        self._analysis_worker.start()

    def _on_analysis_complete(self, result: dict) -> None:
        self.next_button.setEnabled(True)
        self._detected_dependencies = result.get("dependencies", [])

        lines: list[str] = []

        if result.get("parse_error"):
            self.analysis_status.setText("Analysis failed — syntax error in script.")
            lines.append(f"[Syntax Error]  {result['parse_error']}")
            self.analysis_box.setPlainText("\n".join(lines))
            return

        # ── Dependencies ──────────────────────────────────────────────────
        deps = result.get("dependencies", [])
        if deps:
            lines.append(f"Dependencies detected ({len(deps)}):")
            for dep in deps:
                lines.append(f"  • {dep}")
        else:
            lines.append("Dependencies: none detected (stdlib only).")

        # ── Variable check ────────────────────────────────────────────────
        variables: dict = result.get("variables", {})
        if variables:
            lines.append("")
            lines.append("Variable Check:")
            all_found = True

            for name, info in variables.items():
                category      = info["category"]
                dtype         = info["declared_type"]
                found         = info["found"]
                ann           = info.get("annotated_as")
                ann_match     = info.get("annotation_matches")
                line_no       = info.get("first_line")

                if not found:
                    all_found = False
                    marker = "✗"
                    detail = "NOT FOUND in script"
                elif ann is not None:
                    if ann_match is True:
                        marker = "✓"
                        detail = f"found at line {line_no}, annotated as '{ann}' — type OK"
                    elif ann_match is False:
                        marker = "!"
                        detail = f"found at line {line_no}, annotated as '{ann}' — type mismatch"
                    else:
                        # file-type variable with an annotation → just note it
                        marker = "✓"
                        detail = f"found at line {line_no}, annotated as '{ann}'"
                else:
                    if ann_match is None and dtype in (".xlsx", ".xls", ".csv", "Directory"):
                        # file-type, annotation not expected
                        marker = "✓"
                        detail = f"found at line {line_no}"
                    else:
                        # type-checkable but no annotation found
                        marker = "~"
                        detail = f"found at line {line_no} — no type annotation"

                lines.append(f"  {marker} {name}  [{category} / {dtype}]  —  {detail}")

            lines.append("")
            if all_found:
                lines.append("All declared variables were found in the script.")
            else:
                lines.append("Warning: one or more declared variables were NOT found in the script.")
        else:
            lines.append("")
            lines.append("No variables declared — nothing to check.")

        self.analysis_status.setText("Analysis complete.")
        self.analysis_box.setPlainText("\n".join(lines))

    def _on_analysis_failed(self, error: str) -> None:
        self.next_button.setEnabled(True)
        self.analysis_status.setText("Analysis failed.")
        self.analysis_box.setPlainText(f"Unexpected error during analysis:\n{error}")

    # ------------------------------------------------------------------ #
    #  Breadcrumb / step UI                                               #
    # ------------------------------------------------------------------ #

    def reset(self):
        """Return the wizard to step 1 with all fields cleared."""
        # Stop any running analysis worker.
        if self._analysis_worker is not None:
            try:
                self._analysis_worker.analysis_complete.disconnect()
                self._analysis_worker.analysis_failed.disconnect()
            except RuntimeError:
                pass
            self._analysis_worker = None

        self._detected_dependencies = []

        # Clear step 1 fields.
        self.script_name_input.clear()
        self.script_path_input.clear()
        self.script_description_input.clear()
        self.help_path_input.clear()

        # Reset variable editors to a single blank row each.
        for editor in (self.inputs_editor, self.config_editor, self.outputs_editor):
            while len(editor.rows) > 1:
                _, _, _ = editor.rows[-1]
                editor.rows[-1][0].deleteLater()
                editor.rows.pop()
            editor.rows[0][1].clear()
            editor.rows[0][2].setCurrentIndex(0)

        # Clear validation panes.
        self.validation_box.clear()
        self.analysis_box.clear()
        self.analysis_status.setText("Analysis will run when you reach this step.")

        # Re-enable the Next/Add button in case it was disabled during analysis.
        self.next_button.setEnabled(True)

        # Go back to step 1.
        self.steps.setCurrentIndex(0)
        self.update_step_ui()

    def _go_to_step(self, index: int) -> None:
        """Navigate to a step — only backwards navigation is allowed."""
        if index < self.steps.currentIndex():
            self.steps.setCurrentIndex(index)
            self.update_step_ui()

    def update_step_ui(self):
        idx = self.steps.currentIndex()
        self.step_label.setText(f"Step {idx + 1} of {len(self.step_titles)}")
        self.back_button.setEnabled(idx > 0)

        for i, item in enumerate(self.breadcrumb_items):
            state = "pending"
            if i < idx:
                state = "done"
            elif i == idx:
                state = "active"
            item.setProperty("state", state)
            item.style().unpolish(item)
            item.style().polish(item)
            item.update()
            # Done steps are clickable (go back); others are not.
            item.setCursor(
                Qt.CursorShape.PointingHandCursor
                if state == "done"
                else Qt.CursorShape.ArrowCursor
            )

        if idx == self.steps.count() - 1:
            self.next_button.setText("Add Script")
        else:
            self.next_button.setText("Next")
