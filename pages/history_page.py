from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QPushButton,
    QComboBox,
)

from history_manager import HistoryManager


class HistoryEventCard(QFrame):
    """A card displaying a single history event."""

    def __init__(self, action: dict):
        super().__init__()
        self.setObjectName("contentCard")
        self.action = action

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        action_type = action.get("action_type", "unknown")

        # ── Header row ───────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(8)

        num_label = QLabel(f"#{action.get('action_number', '?')}")
        num_label.setObjectName("historyActionNum")

        badge = QLabel(action_type.replace("_", " ").title())
        badge.setObjectName("historyTypeBadge")
        badge.setProperty("badgeType", action_type)

        script_name = QLabel(action.get("script_name", "Unknown"))
        script_name.setObjectName("historyScriptName")

        ts = QLabel(action.get("timestamp", ""))
        ts.setObjectName("historyTimestamp")

        header.addWidget(num_label)
        header.addWidget(badge)
        header.addSpacing(4)
        header.addWidget(script_name, 1)
        header.addWidget(ts)
        layout.addLayout(header)

        # ── Divider ──────────────────────────────────────────────────────────
        div = QFrame()
        div.setObjectName("historyDivider")
        div.setFixedHeight(1)
        layout.addWidget(div)

        # ── Description ──────────────────────────────────────────────────────
        if action.get("script_description"):
            desc = QLabel(action["script_description"])
            desc.setObjectName("cardText")
            desc.setWordWrap(True)
            layout.addWidget(desc)

        # ── Action-specific details ───────────────────────────────────────────
        if action_type == "script_added":
            self._build_added(layout, action)
        elif action_type == "script_run":
            self._build_run(layout, action)

    def _build_added(self, layout: QVBoxLayout, action: dict) -> None:
        details = action.get("details", {})
        iv = details.get("input_variables", [])
        cv = details.get("config_variables", [])
        ov = details.get("output_variables", [])
        deps = details.get("dependencies", [])

        vars_lbl = QLabel(
            f"Variables: {len(iv)} input · {len(cv)} config · {len(ov)} output"
        )
        vars_lbl.setObjectName("historyDetailText")
        layout.addWidget(vars_lbl)

        if deps:
            deps_lbl = QLabel(f"Dependencies: {', '.join(str(d) for d in deps)}")
            deps_lbl.setObjectName("historyDetailText")
            deps_lbl.setWordWrap(True)
            layout.addWidget(deps_lbl)

    def _build_run(self, layout: QVBoxLayout, action: dict) -> None:
        success = action.get("success", False)
        exit_code = action.get("exit_code", 0)

        # Status + exit code row
        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        status_pill = QLabel("✓  Success" if success else "✗  Failed")
        status_pill.setObjectName("historyStatusBadge")
        status_pill.setProperty("status", "success" if success else "failed")

        exit_lbl = QLabel(f"exit {exit_code}")
        exit_lbl.setObjectName("historyExitCode")

        status_row.addWidget(status_pill)
        status_row.addWidget(exit_lbl)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Runtime values
        rv = action.get("runtime_values", {})
        inputs = rv.get("input_variables", {})
        configs = rv.get("config_variables", {})
        outputs = rv.get("output_variables", {})

        if inputs or configs or outputs:
            sec = QLabel("Runtime Values")
            sec.setObjectName("historySectionTitle")
            layout.addWidget(sec)

            for prefix, data in [("In", inputs), ("Cfg", configs), ("Out", outputs)]:
                if not data:
                    continue
                text = f"{prefix}:  " + "   ".join(
                    f"{n} = {d.get('value')}" for n, d in data.items()
                )
                lbl = QLabel(text)
                lbl.setObjectName("historyRuntimeText")
                lbl.setWordWrap(True)
                layout.addWidget(lbl)

        # Execution log
        log = action.get("execution_log", "")
        if log:
            sec2 = QLabel("Execution Log")
            sec2.setObjectName("historySectionTitle")
            layout.addWidget(sec2)

            preview = log[:500] + (" …" if len(log) > 500 else "")
            log_box = QLabel(preview)
            log_box.setObjectName("historyLogBox")
            log_box.setWordWrap(True)
            layout.addWidget(log_box)


class HistoryPage(QWidget):
    """Main history page displaying all logged events."""

    def __init__(self):
        super().__init__()
        self.setObjectName("HistoryPage")
        self.history_manager = HistoryManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(16)

        title = QLabel("History")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel("Track all script additions and executions with detailed logs.")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        # ── Controls bar ─────────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        filter_label = QLabel("Filter:")
        filter_label.setObjectName("cardText")
        ctrl.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("filterCombo")
        self.filter_combo.addItems(["All Actions", "Script Additions", "Script Runs"])
        self.filter_combo.currentIndexChanged.connect(self.refresh_history)
        ctrl.addWidget(self.filter_combo)

        ctrl.addStretch()

        self.stats_display = QLabel("")
        self.stats_display.setObjectName("historyStatsLabel")
        ctrl.addWidget(self.stats_display)

        refresh_btn = QPushButton("↻  Refresh")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self.refresh_history)
        ctrl.addWidget(refresh_btn)

        layout.addLayout(ctrl)

        # ── Scroll area ───────────────────────────────────────────────────────
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("historyScrollArea")
        self.scroll_area.setWidgetResizable(True)

        self.history_container = QWidget()
        self.history_container.setObjectName("historyContainer")
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 6, 0)
        self.history_layout.setSpacing(10)

        self.scroll_area.setWidget(self.history_container)
        layout.addWidget(self.scroll_area)

        self.refresh_history()

    def refresh_history(self):
        """Refresh the history display with current data."""
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        filter_text = self.filter_combo.currentText()
        actions = self.history_manager.get_all_actions()

        if filter_text == "Script Additions":
            actions = [a for a in actions if a.get("action_type") == "script_added"]
        elif filter_text == "Script Runs":
            actions = [a for a in actions if a.get("action_type") == "script_run"]

        if not actions:
            empty = QLabel("No history yet. Run or add scripts to see events here.")
            empty.setObjectName("historyDetailText")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_layout.addWidget(empty)
        else:
            for action in actions:
                card = HistoryEventCard(action)
                self.history_layout.addWidget(card)

        stats = self.history_manager.get_statistics()
        self.stats_display.setText(
            f"Total: {stats['total_actions']}  ·  "
            f"Added: {stats['total_scripts_added']}  ·  "
            f"Runs: {stats['total_script_runs']}  "
            f"(✓ {stats['successful_runs']}  ✗ {stats['failed_runs']})"
        )

        self.history_layout.addStretch()
