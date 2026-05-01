import os
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Small helpers
# ─────────────────────────────────────────────────────────────────────────────

def _card(parent_layout: QVBoxLayout) -> tuple[QFrame, QVBoxLayout]:
    """Create a content card and append it to parent_layout."""
    frame = QFrame()
    frame.setObjectName("contentCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 16, 20, 18)
    layout.setSpacing(10)
    parent_layout.addWidget(frame)
    return frame, layout


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("cardTitle")
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setObjectName("detailDivider")
    return line


def _meta_row(key: str, value: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)

    key_lbl = QLabel(f"{key}:")
    key_lbl.setObjectName("detailMetaKey")
    key_lbl.setFixedWidth(148)

    val_lbl = QLabel(value if value else "—")
    val_lbl.setObjectName("detailMetaValue")
    val_lbl.setWordWrap(True)
    val_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    row.addWidget(key_lbl)
    row.addWidget(val_lbl, 1)
    return row


# ─────────────────────────────────────────────────────────────────────────────
#  Detail page
# ─────────────────────────────────────────────────────────────────────────────

class ScriptDetailPage(QWidget):
    back_requested = pyqtSignal()
    view_source_requested = pyqtSignal(dict)
    run_requested = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ScriptDetailPage")
        self._script_data: dict = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(16)

        # ── Fixed header ──────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)

        back_btn = QPushButton("Back to Scripts")
        back_btn.setObjectName("ghostButton")
        back_btn.clicked.connect(self.back_requested.emit)

        self.title_label = QLabel("")
        self.title_label.setObjectName("pageTitle")

        self.run_btn = QPushButton("Run")
        self.run_btn.setObjectName("runScriptButton")
        self.run_btn.clicked.connect(self._emit_run_requested)

        self.update_btn = QPushButton("Update Script")
        self.update_btn.setObjectName("primaryButton")

        header.addWidget(back_btn)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.run_btn)
        header.addWidget(self.update_btn)

        # ── Scrollable body ───────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(14)
        self._body_layout.addStretch()

        scroll.setWidget(self._body)

        main_layout.addLayout(header)
        main_layout.addWidget(scroll, 1)

    # ─────────────────────────────────────────────────────────────────────
    #  Public API
    # ─────────────────────────────────────────────────────────────────────

    def load(self, script_data: dict) -> None:
        self._script_data = script_data
        self._rebuild()

    def _emit_run_requested(self) -> None:
        if self._script_data:
            self.run_requested.emit(self._script_data)

    # ─────────────────────────────────────────────────────────────────────
    #  Body rebuild
    # ─────────────────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        d = self._script_data
        self.title_label.setText(d.get("name", "Script Detail"))

        self._build_overview(d)
        self._build_variables(d)
        self._build_dependencies(d)
        self._build_help(d)
        self._build_source()
        self._body_layout.addStretch()

    # ── Section builders ──────────────────────────────────────────────────

    def _build_overview(self, d: dict) -> None:
        _, layout = _card(self._body_layout)
        layout.addWidget(_section_title("Overview"))

        desc = d.get("description") or "No description provided."
        desc_lbl = QLabel(desc)
        desc_lbl.setObjectName("cardText")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
        layout.addWidget(_divider())

        layout.addLayout(_meta_row("UUID",          d.get("uuid", "")))
        layout.addLayout(_meta_row("Version",       str(d.get("current_version", 1))))
        layout.addLayout(_meta_row("Created At",    d.get("created_at", "")))
        layout.addLayout(_meta_row("Last Run",      d.get("lastrun_time") or "Never"))
        layout.addLayout(_meta_row("Last Updated",  d.get("lastupdated_datetime_stamp", "")))
        layout.addLayout(_meta_row("Success Rate",  d.get("success_rate") or "—"))

    def _build_variables(self, d: dict) -> None:
        _, layout = _card(self._body_layout)
        layout.addWidget(_section_title("Variables"))

        cols = QHBoxLayout()
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(12)

        cols.addWidget(self._var_section("Input Variables",  d.get("input_variables", [])),  1)
        cols.addWidget(self._var_section("Config Variables", d.get("config_variable", [])),  1)
        cols.addWidget(self._var_section("Output Variables", d.get("output_variable", [])),  1)
        layout.addLayout(cols)

    def _var_section(self, title: str, variables: list) -> QFrame:
        frame = QFrame()
        frame.setObjectName("varFrame")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(6)
        fl.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("varSectionTitle")
        fl.addWidget(title_lbl)

        if not variables:
            empty = QLabel("None")
            empty.setObjectName("detailMetaValue")
            fl.addWidget(empty)
            return frame

        for var in variables:
            item = QFrame()
            item.setObjectName("varItem")
            il = QHBoxLayout(item)
            il.setContentsMargins(8, 6, 8, 6)
            il.setSpacing(8)

            name_lbl = QLabel(var.get("name", ""))
            name_lbl.setObjectName("varItemName")
            type_lbl = QLabel(var.get("type", ""))
            type_lbl.setObjectName("varItemType")
            type_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            il.addWidget(name_lbl, 1)
            il.addWidget(type_lbl)
            fl.addWidget(item)

        return frame

    def _build_dependencies(self, d: dict) -> None:
        deps: list[str] = d.get("dependencies", [])
        _, layout = _card(self._body_layout)
        layout.addWidget(_section_title("Dependencies"))

        if not deps:
            lbl = QLabel("No third-party dependencies detected.")
            lbl.setObjectName("detailMetaValue")
            layout.addWidget(lbl)
            return

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for dep in deps:
            badge = QLabel(dep)
            badge.setObjectName("depBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(badge)
        row.addStretch()
        layout.addLayout(row)

    def _build_help(self, d: dict) -> None:
        help_path = d.get("help_file_path", "").strip()
        _, layout = _card(self._body_layout)
        layout.addWidget(_section_title("Help File"))

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        if help_path and Path(help_path).exists():
            path_lbl = QLabel(help_path)
            path_lbl.setObjectName("detailMetaValue")
            path_lbl.setWordWrap(True)
            path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            open_btn = QPushButton("Open")
            open_btn.setObjectName("secondaryButton")
            open_btn.clicked.connect(lambda: os.startfile(help_path))  # Windows

            row.addWidget(path_lbl, 1)
            row.addWidget(open_btn)
        else:
            lbl = QLabel("No help file attached.")
            lbl.setObjectName("detailMetaValue")
            row.addWidget(lbl)
            row.addStretch()

        layout.addLayout(row)

    def _build_source(self) -> None:
        _, layout = _card(self._body_layout)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(_section_title("Script Source"))
        row.addStretch()

        view_btn = QPushButton("View Script")
        view_btn.setObjectName("viewScriptButton")
        view_btn.clicked.connect(
            lambda: self.view_source_requested.emit(self._script_data)
        )
        row.addWidget(view_btn)

        hint = QLabel("Opens the full source code in a dedicated viewer.")
        hint.setObjectName("hintText")

        layout.addLayout(row)
        layout.addWidget(hint)
