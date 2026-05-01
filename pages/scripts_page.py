from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from components import ScriptCardWidget
from config import get_manifest_root
from registry import load_registry_entries
from script_manager import ScriptManager


class ScriptsPage(QWidget):
    add_requested = pyqtSignal()
    scripts_changed = pyqtSignal()
    view_script_requested = pyqtSignal(dict)
    run_script_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setObjectName("ScriptsPage")
        self._script_manager = ScriptManager()
        self._card_widgets: list[ScriptCardWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Scripts")
        title.setObjectName("pageTitle")

        add_script_button = QPushButton("Add Script")
        add_script_button.setObjectName("primaryButton")
        add_script_button.clicked.connect(self.add_requested.emit)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._delete_selected)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.delete_button)
        header.addWidget(add_script_button)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("scriptsSearch")
        self.search_input.setPlaceholderText("Search scripts by name or path...")
        self.search_input.textChanged.connect(lambda _text: self._apply_filter(reset_page=True))

        self.meta_label = QLabel("Loading script registry...")
        self.meta_label.setObjectName("scriptsMeta")

        self.scripts_list = QListWidget()
        self.scripts_list.setObjectName("scriptCatalogList")
        self.scripts_list.setSpacing(8)
        self.scripts_list.setUniformItemSizes(False)

        self._all_scripts = []
        self._filtered_scripts = []
        self._page_size = 40
        self._current_page = 0

        pager_row = QHBoxLayout()
        pager_row.setContentsMargins(0, 0, 0, 0)
        pager_row.setSpacing(8)

        self.prev_page_button = QPushButton("Prev")
        self.prev_page_button.setObjectName("ghostButton")
        self.prev_page_button.clicked.connect(self._prev_page)

        self.page_label = QLabel("Page 1")
        self.page_label.setObjectName("scriptsMeta")

        self.next_page_button = QPushButton("Next")
        self.next_page_button.setObjectName("ghostButton")
        self.next_page_button.clicked.connect(self._next_page)

        pager_row.addStretch()
        pager_row.addWidget(self.prev_page_button)
        pager_row.addWidget(self.page_label)
        pager_row.addWidget(self.next_page_button)

        layout.addLayout(header)
        layout.addWidget(self.search_input)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.scripts_list, 1)
        layout.addLayout(pager_row)

        self.reload_scripts()

    def reload_scripts(self):
        manifest_root = get_manifest_root()
        self._all_scripts = load_registry_entries(manifest_root)
        self._apply_filter(reset_page=True)

    def _apply_filter(self, reset_page):
        query = self.search_input.text().strip().lower()
        if query:
            self._filtered_scripts = [
                script_data
                for script_data in self._all_scripts
                if query in script_data.get("name", "").lower()
                or query in script_data.get("description", "").lower()
                or query in script_data.get("uuid", "").lower()
            ]
        else:
            self._filtered_scripts = self._all_scripts

        if reset_page:
            self._current_page = 0

        self._render_filtered()

    def _render_filtered(self):
        self.scripts_list.clear()
        self._card_widgets.clear()
        self.delete_button.setEnabled(False)

        total_items = len(self._filtered_scripts)
        if total_items == 0:
            self.page_label.setText("Page 0 / 0")
            self.prev_page_button.setEnabled(False)
            self.next_page_button.setEnabled(False)
            self.meta_label.setText("Showing 0 scripts")
            return

        page_count = (total_items + self._page_size - 1) // self._page_size
        self._current_page = max(0, min(self._current_page, page_count - 1))
        start = self._current_page * self._page_size
        end = min(start + self._page_size, total_items)
        visible_items = self._filtered_scripts[start:end]

        for display_index, script_data in enumerate(visible_items, start=start + 1):
            list_item = QListWidgetItem()
            list_item.setFlags(list_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.scripts_list.addItem(list_item)
            card = ScriptCardWidget(display_index, script_data, self.run_script, self.view_script)
            card.selection_changed.connect(self._update_delete_button)
            list_item.setSizeHint(card.sizeHint())
            self.scripts_list.setItemWidget(list_item, card)
            self._card_widgets.append(card)

        self.page_label.setText(f"Page {self._current_page + 1} / {page_count}")
        self.prev_page_button.setEnabled(self._current_page > 0)
        self.next_page_button.setEnabled(self._current_page < page_count - 1)
        self.meta_label.setText(
            f"Showing {start + 1}-{end} of {total_items} scripts (limited view)"
        )

    def _update_delete_button(self):
        selected_count = sum(1 for card in self._card_widgets if card.is_selected())
        self.delete_button.setEnabled(selected_count > 0)
        if selected_count > 0:
            self.delete_button.setText(f"Delete Selected ({selected_count})")
        else:
            self.delete_button.setText("Delete Selected")

    def _delete_selected(self):
        selected = [card for card in self._card_widgets if card.is_selected()]
        if not selected:
            return

        names = "\n".join(f"• {card.script_uuid}" for card in selected)
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Permanently delete {len(selected)} script(s) and their files?\n\n{names}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        errors = []
        for card in selected:
            try:
                self._script_manager.delete_script(card.script_uuid)
            except Exception as exc:
                errors.append(f"{card.script_uuid}: {exc}")

        if errors:
            QMessageBox.warning(
                self,
                "Partial Deletion",
                "Some scripts could not be deleted:\n\n" + "\n".join(errors),
            )

        self.reload_scripts()
        self.scripts_changed.emit()

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._render_filtered()

    def _next_page(self):
        total_items = len(self._filtered_scripts)
        page_count = (total_items + self._page_size - 1) // self._page_size if total_items else 0
        if self._current_page < page_count - 1:
            self._current_page += 1
            self._render_filtered()

    def run_script(self, script_data: dict) -> None:
        self.run_script_requested.emit(script_data)

    def view_script(self, script_data: dict) -> None:
        self.view_script_requested.emit(script_data)
