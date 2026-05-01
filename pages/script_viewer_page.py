from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ScriptViewerPage(QWidget):
    back_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ScriptViewerPage")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(14)

        # ── Header ────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)

        back_btn = QPushButton("Back to Details")
        back_btn.setObjectName("ghostButton")
        back_btn.clicked.connect(self.back_requested.emit)

        self.title_label = QLabel("")
        self.title_label.setObjectName("pageTitle")

        self.path_label = QLabel("")
        self.path_label.setObjectName("hintText")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        header.addWidget(back_btn)
        header.addWidget(self.title_label, 1)

        # ── Meta bar (path + line count) ──────────────────────────────────
        meta_bar = QFrame()
        meta_bar.setObjectName("viewerMetaBar")
        meta_layout = QHBoxLayout(meta_bar)
        meta_layout.setContentsMargins(14, 8, 14, 8)
        meta_layout.setSpacing(16)

        self.path_label = QLabel("")
        self.path_label.setObjectName("viewerMetaLabel")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.line_count_label = QLabel("")
        self.line_count_label.setObjectName("viewerMetaLabel")
        self.line_count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        meta_layout.addWidget(self.path_label, 1)
        meta_layout.addWidget(self.line_count_label)

        # ── Code view ─────────────────────────────────────────────────────
        self.code_box = QPlainTextEdit()
        self.code_box.setObjectName("scriptSourceBox")
        self.code_box.setReadOnly(True)
        self.code_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        main_layout.addLayout(header)
        main_layout.addWidget(meta_bar)
        main_layout.addWidget(self.code_box, 1)

    # ─────────────────────────────────────────────────────────────────────
    #  Public API
    # ─────────────────────────────────────────────────────────────────────

    def load(self, script_data: dict) -> None:
        name = script_data.get("name", "Script")
        script_path = script_data.get("script_path", "")

        self.title_label.setText(f"{name} — source")
        self.path_label.setText(script_path)
        self.code_box.clear()

        try:
            source = Path(script_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            source = f"# Could not read script file:\n# {exc}"

        self.code_box.setPlainText(source)

        line_count = source.count("\n") + (1 if source else 0)
        self.line_count_label.setText(f"{line_count} lines")
