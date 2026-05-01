import ast
import importlib.metadata
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from analyzer import analyze_script


# ── Dependency helpers ────────────────────────────────────────────────────────

class DepCheckWorker(QThread):
    """Check which packages from a list are installed in the active environment."""
    result_ready = pyqtSignal(dict)  # {package_name: bool}

    def __init__(self, deps: list[str]) -> None:
        super().__init__()
        self._deps = deps

    def run(self) -> None:
        results: dict[str, bool] = {}
        for dep in self._deps:
            normalized = dep.strip()
            if not normalized:
                continue

            package_name = normalized.split("==", 1)[0].split(">=", 1)[0].split("<=", 1)[0].strip()
            found = False
            try:
                importlib.metadata.version(package_name)
                found = True
            except importlib.metadata.PackageNotFoundError:
                # Fall back to bare import (handles alias mismatches e.g. Pillow→PIL)
                proc = subprocess.run(
                    [sys.executable, "-c", f"import {package_name}"],
                    capture_output=True,
                )
                found = proc.returncode == 0
            results[normalized] = found
        self.result_ready.emit(results)


class DepInstallWorker(QThread):
    """Install a list of packages using `uv pip install`."""
    line_output  = pyqtSignal(str)
    finished_ok  = pyqtSignal()
    finished_err = pyqtSignal(str)

    def __init__(self, deps: list[str], python_executable: str) -> None:
        super().__init__()
        self._deps   = deps
        self._python = python_executable

    def run(self) -> None:
        uv = shutil.which("uv")
        if not uv:
            self.finished_err.emit(
                "uv not found in PATH.\n"
                "Install it from https://github.com/astral-sh/uv"
            )
            return
        cmd = [uv, "pip", "install", "--python", self._python] + self._deps
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for line in proc.stdout:
                self.line_output.emit(line.rstrip())
            proc.wait()
            if proc.returncode == 0:
                self.finished_ok.emit()
            else:
                self.finished_err.emit(f"uv exited with code {proc.returncode}")
        except Exception as exc:
            self.finished_err.emit(str(exc))


# ── Script execution ──────────────────────────────────────────────────────────

class ScriptRunWorker(QThread):
    """Run a Python script in a subprocess; stream combined stdout/stderr."""
    line_output  = pyqtSignal(str)
    finished_ok  = pyqtSignal()
    finished_err = pyqtSignal(int)  # exit code

    def __init__(self, python: str, script_path: str, env: dict, variables: dict | None = None) -> None:
        super().__init__()
        self._python      = python
        self._script_path = script_path
        self._env         = env
        self._variables   = variables or {}
        self._proc: subprocess.Popen | None = None
        self._runtime_script_path: Path | None = None

    def _value_literal(self, value: object) -> str:
        return repr(str(value)) if isinstance(value, Path) else repr(value)

    def _build_runtime_script(self) -> Path:
        source_path = Path(self._script_path)
        source = source_path.read_text(encoding="utf-8")

        try:
            tree = ast.parse(source, filename=str(source_path))
        except SyntaxError:
            raise

        line_offsets = [0]
        for line in source.splitlines(keepends=True):
            line_offsets.append(line_offsets[-1] + len(line))

        replacements: list[tuple[int, int, str]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name):
                continue
            if not isinstance(node.ctx, ast.Load):
                continue
            if node.id not in self._variables:
                continue
            if any(getattr(node, attr, None) is None for attr in ("lineno", "col_offset", "end_lineno", "end_col_offset")):
                continue

            start = line_offsets[node.lineno - 1] + node.col_offset
            end = line_offsets[node.end_lineno - 1] + node.end_col_offset
            replacements.append((start, end, self._value_literal(self._variables[node.id])))

        if not replacements:
            return source_path

        rewritten = source
        for start, end, replacement in sorted(replacements, reverse=True):
            rewritten = rewritten[:start] + replacement + rewritten[end:]

        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            prefix=f"{source_path.stem}_runtime_",
            dir=str(source_path.parent),
            delete=False,
            encoding="utf-8",
        )
        try:
            temp_file.write(rewritten)
            temp_file.flush()
        finally:
            temp_file.close()

        self._runtime_script_path = Path(temp_file.name)
        return self._runtime_script_path

    def run(self) -> None:
        try:
            runtime_script = self._build_runtime_script()
            command = [self._python, str(runtime_script)]

            self._proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self._env,
                cwd=str(Path(self._script_path).parent),
            )
            for line in self._proc.stdout:
                self.line_output.emit(line.rstrip())
            self._proc.wait()
            if self._proc.returncode == 0:
                self.finished_ok.emit()
            else:
                self.finished_err.emit(self._proc.returncode)
        except Exception as exc:
            self.line_output.emit(f"[Runner error] {exc}")
            self.finished_err.emit(-1)
        finally:
            if self._runtime_script_path is not None and self._runtime_script_path.exists():
                try:
                    self._runtime_script_path.unlink()
                except OSError:
                    pass
                self._runtime_script_path = None

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()


# ── Script analysis (existing) ────────────────────────────────────────────────

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
