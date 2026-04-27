from PyQt6.QtCore import QThread, pyqtSignal

from analyzer import analyze_script


class ScriptAnalysisWorker(QThread):
    """Runs analyze_script() off the main thread."""

    analysis_complete = pyqtSignal(dict)
    analysis_failed = pyqtSignal(str)

    def __init__(
        self,
        script_path: str,
        input_variables: list[dict],
        config_variables: list[dict],
        output_variables: list[dict],
    ) -> None:
        super().__init__()
        self._script_path = script_path
        self._input_variables = input_variables
        self._config_variables = config_variables
        self._output_variables = output_variables

    def run(self) -> None:
        try:
            result = analyze_script(
                self._script_path,
                self._input_variables,
                self._config_variables,
                self._output_variables,
            )
            self.analysis_complete.emit(result)
        except Exception as exc:
            self.analysis_failed.emit(str(exc))
