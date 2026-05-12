import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from environment_manager import EnvironmentManager
from variable_substitution import substitute_template_value
from script_manager import ScriptManager
from workers import DepCheckWorker, DepInstallWorker, ScriptRunWorker


FILE_TYPES = {".xlsx", ".xls", ".csv"}


class ScriptRunDialog(QDialog):
    script_updated = pyqtSignal(dict)

    def __init__(self, script_data: dict, script_manager: ScriptManager, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ScriptRunDialog")
        self.setWindowTitle(f"Run Script: {script_data.get('name', 'Unnamed')}")
        self.resize(920, 680)

        self._script_data = script_data
        self._script_manager = script_manager
        self._environment_manager = EnvironmentManager(self._script_manager.manifest_root)

        self._dep_check_worker: DepCheckWorker | None = None
        self._dep_install_worker: DepInstallWorker | None = None
        self._run_worker: ScriptRunWorker | None = None

        self._input_widgets: dict[str, tuple[str, QWidget]] = {}
        self._config_widgets: dict[str, tuple[str, QWidget]] = {}
        self._output_widgets: dict[str, tuple[str, QWidget]] = {}

        self._dependencies_ready = False
        self._run_in_progress = False
        self._install_attempted = False
        self._runtime_values: dict[str, dict[str, object]] = {}
        self._resolved_template_values: dict[str, object] = {}
        self._template_variable_names = self._environment_manager.list_template_variable_names(
            [str(ref) for ref in self._script_data.get("environment_refs", []) if str(ref).strip()]
        )
        self._template_tokens = [f"{{{{{name}}}}}" for name in self._template_variable_names]

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        subtitle = QLabel(
            "Runs in a background worker: checks dependencies, installs missing packages with uv, "
            "then executes without blocking the app."
        )
        subtitle.setObjectName("hintText")
        subtitle.setWordWrap(True)

        self.dep_status_label = QLabel("Preparing dependency check...")
        self.dep_status_label.setObjectName("sectionLabel")

        self.variables_card = QFrame()
        self.variables_card.setObjectName("contentCard")
        variables_layout = QVBoxLayout(self.variables_card)
        variables_layout.setContentsMargins(14, 12, 14, 12)
        variables_layout.setSpacing(8)

        variables_title = QLabel("Runtime Variable Values")
        variables_title.setObjectName("cardTitle")

        variables_help = QLabel(
            "Input/output variables use file or folder pickers. Config variables accept typed values."
        )
        variables_help.setObjectName("cardText")
        variables_help.setWordWrap(True)

        self.form_wrap = QWidget()
        self.form_layout = QFormLayout(self.form_wrap)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(10)
        self.form_layout.setVerticalSpacing(10)

        variables_layout.addWidget(variables_title)
        variables_layout.addWidget(variables_help)
        variables_layout.addWidget(self.form_wrap)

        log_title = QLabel("Execution Log")
        log_title.setObjectName("sectionLabel")

        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("analysisBox")
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(240)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("ghostButton")
        self.close_btn.clicked.connect(self.reject)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("dangerGhostButton")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_execution)

        self.run_btn = QPushButton("Run Script")
        self.run_btn.setObjectName("primaryButton")
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._start_run)

        actions.addWidget(self.close_btn)
        actions.addStretch()
        actions.addWidget(self.stop_btn)
        actions.addWidget(self.run_btn)

        root.addWidget(subtitle)
        root.addWidget(self.dep_status_label)
        root.addWidget(self.variables_card)
        root.addWidget(log_title)
        root.addWidget(self.log_box, 1)
        root.addLayout(actions)

        self._build_variable_form()
        self._set_variables_enabled(False)
        self._start_dependency_check()

    def closeEvent(self, event) -> None:
        self._cleanup_workers()
        super().closeEvent(event)

    def _append_log(self, line: str) -> None:
        self.log_box.appendPlainText(line)

    def _set_variables_enabled(self, enabled: bool) -> None:
        self.variables_card.setEnabled(enabled)
        self.run_btn.setEnabled(enabled and not self._run_in_progress)

    def _build_variable_form(self) -> None:
        rows: list[tuple[str, str, str]] = []

        for item in self._script_data.get("input_variables", []):
            rows.append(("Input", item.get("name", "").strip(), item.get("type", "").strip()))
        for item in self._script_data.get("config_variable", []):
            rows.append(("Config", item.get("name", "").strip(), item.get("type", "").strip()))
        for item in self._script_data.get("output_variable", []):
            rows.append(("Output", item.get("name", "").strip(), item.get("type", "").strip()))

        if not rows:
            self.form_layout.addRow(QLabel("No runtime variables were declared."), QLabel(""))
            return

        for category, var_name, var_type in rows:
            if not var_name:
                continue

            label = QLabel(f"{category} - {var_name} ({var_type or 'value'})")
            widget = self._build_editor_for_variable(category, var_type)

            if category == "Input":
                self._input_widgets[var_name] = (var_type, widget)
            elif category == "Config":
                self._config_widgets[var_name] = (var_type, widget)
            else:
                self._output_widgets[var_name] = (var_type, widget)

            if isinstance(widget, QLineEdit) and self._template_tokens:
                completer = QCompleter(self._template_tokens, self)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                widget.setCompleter(completer)
                if category == "Config":
                    widget.setPlaceholderText("Enter value or {{variable_name}}")

            self.form_layout.addRow(label, widget)

    def _build_editor_for_variable(self, category: str, var_type: str) -> QWidget:
        normalized = (var_type or "").strip()

        if normalized in FILE_TYPES:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            path_input = QLineEdit()
            path_input.setObjectName("lineInput")
            path_input.setReadOnly(True)
            path_input.setPlaceholderText("Select file")

            browse_btn = QPushButton("Browse")
            browse_btn.setObjectName("secondaryButton")
            if category == "Output":
                browse_btn.clicked.connect(lambda: self._choose_output_file(path_input, normalized))
            else:
                browse_btn.clicked.connect(lambda: self._choose_input_file(path_input, normalized))

            row_layout.addWidget(path_input, 1)
            row_layout.addWidget(browse_btn)
            return row

        if normalized == "Directory":
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            path_input = QLineEdit()
            path_input.setObjectName("lineInput")
            path_input.setReadOnly(True)
            path_input.setPlaceholderText("Select directory")

            browse_btn = QPushButton("Browse")
            browse_btn.setObjectName("secondaryButton")
            browse_btn.clicked.connect(lambda: self._choose_directory(path_input))

            row_layout.addWidget(path_input, 1)
            row_layout.addWidget(browse_btn)
            return row

        if normalized == "bool":
            checkbox = QCheckBox("True")
            checkbox.setObjectName("scriptSelectCheckbox")
            checkbox.stateChanged.connect(lambda state: checkbox.setText("True" if state else "False"))
            return checkbox

        if normalized in {"int", "float", "string"}:
            line = QLineEdit()
            line.setObjectName("lineInput")
            line.setPlaceholderText(f"Enter {normalized} value")
            return line

        line = QLineEdit()
        line.setObjectName("lineInput")
        line.setPlaceholderText("Enter value")
        return line

    def _choose_input_file(self, target: QLineEdit, ext: str) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select input file",
            str(Path.home()),
            f"{ext} files (*{ext});;All files (*)",
        )
        if selected:
            target.setText(selected)

    def _choose_output_file(self, target: QLineEdit, ext: str) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Select output file",
            str(Path.home()),
            f"{ext} files (*{ext});;All files (*)",
        )
        if selected:
            target.setText(selected)

    def _choose_directory(self, target: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select directory", str(Path.home()))
        if selected:
            target.setText(selected)

    def _start_dependency_check(self) -> None:
        dependencies = [d for d in self._script_data.get("dependencies", []) if str(d).strip()]
        if not dependencies:
            self._dependencies_ready = True
            self.dep_status_label.setText("No third-party dependencies declared. Ready to run.")
            self._append_log("No dependencies detected in metadata.")
            self._set_variables_enabled(True)
            return

        self._append_log("Checking dependencies in current environment...")
        self.dep_status_label.setText("Checking dependencies...")
        self._dep_check_worker = DepCheckWorker(dependencies)
        self._dep_check_worker.result_ready.connect(self._on_dep_check_complete)
        self._dep_check_worker.start()

    def _on_dep_check_complete(self, results: dict) -> None:
        missing = [name for name, ok in results.items() if not ok]
        if not missing:
            self._dependencies_ready = True
            self.dep_status_label.setText("Dependencies ready. Configure variables and run.")
            self._append_log("All dependencies are available.")
            self._set_variables_enabled(True)
            return

        if self._install_attempted:
            self.dep_status_label.setText("Dependencies still missing after install attempt.")
            self._append_log("Dependencies are still missing after uv install.")
            self._set_variables_enabled(False)
            QMessageBox.critical(
                self,
                "Dependencies Missing",
                "Some dependencies are still missing after installation. Check the log for details.",
            )
            return

        self._append_log("Missing dependencies found:")
        for item in missing:
            self._append_log(f"  - {item}")

        self.dep_status_label.setText("Installing missing dependencies with uv...")
        self._append_log("Installing missing dependencies via: uv pip install ...")
        self._install_attempted = True

        self._dep_install_worker = DepInstallWorker(missing, sys.executable)
        self._dep_install_worker.line_output.connect(self._append_log)
        self._dep_install_worker.finished_ok.connect(self._on_dep_install_ok)
        self._dep_install_worker.finished_err.connect(self._on_dep_install_err)
        self._dep_install_worker.start()

    def _on_dep_install_ok(self) -> None:
        self._append_log("Dependency installation finished. Re-checking...")
        self._start_dependency_check()

    def _on_dep_install_err(self, error: str) -> None:
        self.dep_status_label.setText("Dependency installation failed.")
        self._append_log(f"[Dependency error] {error}")
        self._set_variables_enabled(False)
        QMessageBox.critical(
            self,
            "Dependency Installation Failed",
            f"Could not install required dependencies:\n\n{error}",
        )

    def _collect_runtime_values(self, template_values: dict[str, object] | None = None) -> dict[str, dict[str, object]] | None:
        runtime_values: dict[str, dict[str, object]] = {}
        template_values = template_values or {}

        def apply_templates(raw: str) -> str:
            if not raw:
                return raw
            return str(substitute_template_value(raw, template_values))

        def read_widget(widget: QWidget) -> str:
            if isinstance(widget, QLineEdit):
                return apply_templates(widget.text().strip())
            if isinstance(widget, QCheckBox):
                return "True" if widget.isChecked() else "False"
            line_edit = widget.findChild(QLineEdit)
            if line_edit is not None:
                return apply_templates(line_edit.text().strip())
            return ""

        for var_name, (var_type, widget) in self._input_widgets.items():
            value = read_widget(widget)
            if not value:
                QMessageBox.warning(self, "Missing Value", f"Input variable '{var_name}' is required.")
                return None
            runtime_values[var_name] = {
                "value": value,
                "type": var_type,
                "category": "input",
            }

        for var_name, (var_type, widget) in self._output_widgets.items():
            value = read_widget(widget)
            if not value:
                QMessageBox.warning(self, "Missing Value", f"Output variable '{var_name}' is required.")
                return None
            runtime_values[var_name] = {
                "value": value,
                "type": var_type,
                "category": "output",
            }

        for var_name, (var_type, widget) in self._config_widgets.items():
            value = read_widget(widget)
            if not value and var_type != "bool":
                QMessageBox.warning(self, "Missing Value", f"Config variable '{var_name}' is required.")
                return None

            normalized = (var_type or "").strip()
            if normalized == "int":
                try:
                    runtime_values[var_name] = {
                        "value": int(value),
                        "type": var_type,
                        "category": "config",
                    }
                except ValueError:
                    QMessageBox.warning(self, "Invalid Value", f"Config variable '{var_name}' must be an integer.")
                    return None
            elif normalized == "float":
                try:
                    runtime_values[var_name] = {
                        "value": float(value),
                        "type": var_type,
                        "category": "config",
                    }
                except ValueError:
                    QMessageBox.warning(self, "Invalid Value", f"Config variable '{var_name}' must be a float.")
                    return None
            elif normalized == "bool":
                runtime_values[var_name] = {
                    "value": isinstance(widget, QCheckBox) and widget.isChecked(),
                    "type": var_type,
                    "category": "config",
                }
            else:
                runtime_values[var_name] = {
                    "value": value,
                    "type": var_type,
                    "category": "config",
                }

        return runtime_values

    def _build_template_values(self, runtime_values: dict[str, dict[str, object]]) -> dict[str, object]:
        template_values = self._environment_manager.resolve_for_script(self._script_data)
        for var_name, payload in runtime_values.items():
            template_values[var_name] = payload.get("value")
        return template_values

    def _build_execution_env(self) -> dict:
        env = os.environ.copy()

        # Include project root so copied scripts can import local project modules.
        project_root = Path(__file__).resolve().parents[1]
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(project_root)
            if not existing_pythonpath
            else f"{project_root}{os.pathsep}{existing_pythonpath}"
        )
        return env

    def _start_run(self) -> None:
        if not self._dependencies_ready:
            QMessageBox.information(self, "Dependencies", "Please wait until dependency checks complete.")
            return

        script_path = self._script_data.get("script_path", "").strip()
        if not script_path or not Path(script_path).exists():
            QMessageBox.critical(self, "Missing Script", "Script file does not exist.")
            return

        base_template_values = self._environment_manager.resolve_for_script(self._script_data)
        runtime_values = self._collect_runtime_values(base_template_values)
        if runtime_values is None:
            return

        # Store runtime values for later use in logging
        self._runtime_values = runtime_values
        self._resolved_template_values = self._build_template_values(runtime_values)

        for var_name, payload in list(self._runtime_values.items()):
            payload["value"] = substitute_template_value(payload.get("value"), self._resolved_template_values)

        env = self._build_execution_env()

        self._run_in_progress = True
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.close_btn.setEnabled(False)
        self.dep_status_label.setText("Executing script in sandbox...")
        self._append_log("Starting script execution...")

        self._run_worker = ScriptRunWorker(
            sys.executable,
            script_path,
            env,
            runtime_values,
            self._resolved_template_values,
        )
        self._run_worker.line_output.connect(self._append_log)
        self._run_worker.finished_ok.connect(self._on_run_ok)
        self._run_worker.finished_err.connect(self._on_run_err)
        self._run_worker.start()

    def _on_run_ok(self) -> None:
        self._run_in_progress = False
        self.stop_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.dep_status_label.setText("Execution finished successfully.")
        self._append_log("Script completed with exit code 0.")
        self._record_run_result(True, exit_code=0)

    def _on_run_err(self, exit_code: int) -> None:
        self._run_in_progress = False
        self.stop_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.dep_status_label.setText("Execution failed.")
        self._append_log(f"Script failed with exit code {exit_code}.")
        self._record_run_result(False, exit_code=exit_code)

    def _record_run_result(self, success: bool, exit_code: int = 0) -> None:
        script_uuid = str(self._script_data.get("uuid", "")).strip()
        if not script_uuid:
            self.run_btn.setEnabled(True)
            return

        try:
            updated = self._script_manager.record_run_result(script_uuid, success)
            
            # Collect the execution log from the log box
            execution_log = self.log_box.toPlainText()
            
            # Log the script run to history with all details
            self._script_manager.log_script_run(
                script_uuid,
                self._script_data,
                self._runtime_values,
                execution_log,
                success,
                exit_code,
            )
            
            self._script_data = updated
            self.script_updated.emit(updated)
        except Exception as exc:
            self._append_log(f"[Metadata update error] {exc}")

        self.run_btn.setEnabled(True)

    def _stop_execution(self) -> None:
        if self._run_worker is None:
            return
        self._append_log("Stop requested. Terminating subprocess...")
        self._run_worker.stop()

    def _cleanup_workers(self) -> None:
        if self._run_worker is not None and self._run_worker.isRunning():
            self._run_worker.stop()
            self._run_worker.wait(2000)

        for worker in (self._dep_check_worker, self._dep_install_worker):
            if worker is not None and worker.isRunning():
                worker.quit()
                worker.wait(2000)
