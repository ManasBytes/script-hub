import sys
from pathlib import Path

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
	QApplication,
	QHBoxLayout,
	QMainWindow,
	QMessageBox,
	QStackedWidget,
	QVBoxLayout,
	QWidget,
)

from components import Navbar, Sidebar
from pages import AddScriptPage, Page, ScriptDetailPage, ScriptViewerPage, ScriptsPage, HistoryPage, TrashPage
from pages.script_run_dialog import ScriptRunDialog
from pages.update_version_dialog import UpdateVersionDialog
from pages.rollback_dialog import RollbackDialog
from script_manager import ScriptManager


def resource_path(relative_path):
	"""Resolve bundled resources for both dev runs and PyInstaller executables."""
	base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
	return base_path / relative_path


def _build_light_palette() -> QPalette:
	"""
	Explicit QPalette for light mode.

	Qt Fusion computes hover/selection colours from the QPalette, not only from
	QSS.  The two roles that cause invisible text are:
	  • HighlightedText — used for text on selected/hovered list items (defaults
	    to white in the stock Fusion palette → white text on our light hover bg)
	  • ButtonText — used as the fallback button text colour during hover
	Setting both to dark values here fixes those cases at the root level.
	"""
	p = QPalette()
	p.setColor(QPalette.ColorRole.Window,          QColor("#edf1f7"))
	p.setColor(QPalette.ColorRole.Base,            QColor("#ffffff"))
	p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#f5f8fc"))
	p.setColor(QPalette.ColorRole.Button,          QColor("#edf1f7"))
	p.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#ffffff"))
	p.setColor(QPalette.ColorRole.WindowText,      QColor("#1e293b"))
	p.setColor(QPalette.ColorRole.Text,            QColor("#1e293b"))
	p.setColor(QPalette.ColorRole.ButtonText,      QColor("#1e293b"))
	p.setColor(QPalette.ColorRole.BrightText,      QColor("#0f172a"))
	p.setColor(QPalette.ColorRole.ToolTipText,     QColor("#1e293b"))
	p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#94a3b8"))
	p.setColor(QPalette.ColorRole.Highlight,       QColor("#dbeafe"))
	p.setColor(QPalette.ColorRole.HighlightedText, QColor("#1d4ed8"))
	p.setColor(QPalette.ColorRole.Light,           QColor("#f5f8fc"))
	p.setColor(QPalette.ColorRole.Midlight,        QColor("#e8edf5"))
	p.setColor(QPalette.ColorRole.Mid,             QColor("#c9d4e0"))
	p.setColor(QPalette.ColorRole.Dark,            QColor("#b6c4d4"))
	p.setColor(QPalette.ColorRole.Shadow,          QColor("#7e95b0"))
	p.setColor(QPalette.ColorRole.Link,            QColor("#2563eb"))
	p.setColor(QPalette.ColorRole.LinkVisited,     QColor("#6d28d9"))
	for role, col in [
		(QPalette.ColorRole.WindowText, "#94a3b8"),
		(QPalette.ColorRole.Text,       "#94a3b8"),
		(QPalette.ColorRole.ButtonText, "#94a3b8"),
		(QPalette.ColorRole.Base,       "#f5f8fc"),
		(QPalette.ColorRole.Button,     "#f5f8fc"),
	]:
		p.setColor(QPalette.ColorGroup.Disabled, role, QColor(col))
	return p


class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Scripts Architect")
		self.setObjectName("appRoot")
		self._current_theme = "light"

		root = QWidget()
		root_layout = QVBoxLayout(root)
		root_layout.setContentsMargins(0, 0, 0, 0)
		root_layout.setSpacing(0)

		self.navbar = Navbar(self.switch_page, self.toggle_sidebar, self.toggle_theme)
		self.sidebar = Sidebar()
		self.script_manager = ScriptManager()

		self.pages = QStackedWidget()
		self.pages.setObjectName("mainContent")

		self.home_page = Page("Home", "Home", "Your command center and quick overview.")
		self.scripts_page = ScriptsPage()
		self.history_page = HistoryPage()
		self.trash_page = TrashPage()
		# Connect trash page refresh signal to refresh scripts/sidebar
		try:
			self.trash_page.request_refresh.connect(self._refresh_after_trash_action)
		except Exception:
			pass
		self.add_script_page = AddScriptPage()
		self.script_detail_page = ScriptDetailPage()
		self.script_viewer_page = ScriptViewerPage()

		self._pending_folder_id: str | None = None
		self.scripts_page.add_requested.connect(self.open_add_script_page)
		self.scripts_page.scripts_changed.connect(self.sidebar.reload)
		self.scripts_page.view_script_requested.connect(self.open_script_detail)
		self.scripts_page.run_script_requested.connect(self.open_script_runner)
		self.sidebar.script_selected.connect(self.open_script_detail)
		self.sidebar.folder_navigate_requested.connect(self._open_folder_in_scripts)
		self.add_script_page.back_to_scripts.connect(self.open_scripts_page)
		self.add_script_page.submit_requested.connect(self.handle_script_submission)
		self.script_detail_page.back_requested.connect(
			lambda: self.pages.setCurrentWidget(self.scripts_page)
		)
		self.script_detail_page.view_source_requested.connect(self.open_script_viewer)
		self.script_detail_page.run_requested.connect(self.open_script_runner)
		self.script_detail_page.update_version_requested.connect(self.open_update_version_dialog)
		self.script_detail_page.rollback_requested.connect(self.open_rollback_dialog)
		self.script_detail_page.delete_version_requested.connect(self.handle_delete_version)
		self.script_viewer_page.back_requested.connect(
			lambda: self.pages.setCurrentWidget(self.script_detail_page)
		)

		self.pages.addWidget(self.home_page)
		self.pages.addWidget(self.scripts_page)
		self.pages.addWidget(self.history_page)
		self.pages.addWidget(self.trash_page)
		self.pages.addWidget(self.add_script_page)
		self.pages.addWidget(self.script_detail_page)
		self.pages.addWidget(self.script_viewer_page)

		content_row = QHBoxLayout()
		content_row.setContentsMargins(0, 0, 0, 0)
		content_row.setSpacing(0)
		content_row.addWidget(self.sidebar)
		content_row.addWidget(self.pages, 1)

		root_layout.addWidget(self.navbar)
		root_layout.addLayout(content_row, 1)

		self.setCentralWidget(root)
		self._apply_stylesheet()

	def switch_page(self, index):
		# If switching to trash page, refresh its contents
		widget = self.pages.widget(index) if 0 <= index < self.pages.count() else None
		if widget is self.trash_page:
			try:
				self.trash_page.reload()
			except Exception:
				pass
		self.pages.setCurrentIndex(index)

	def open_add_script_page(self, folder_id=None):
		self._pending_folder_id = folder_id
		self.add_script_page.reset()
		self.pages.setCurrentWidget(self.add_script_page)

	def open_scripts_page(self):
		self.scripts_page.reload_scripts()
		self.pages.setCurrentWidget(self.scripts_page)

	def handle_script_submission(self, payload):
		payload["folder_id"] = self._pending_folder_id
		self._pending_folder_id = None
		try:
			entry = self.script_manager.save_script(payload)
		except Exception as error:
			QMessageBox.critical(self, "Save Failed", f"Could not save script:\n{error}")
			return

		self.scripts_page.reload_scripts()
		self.sidebar.reload()
		self.pages.setCurrentWidget(self.scripts_page)
		QMessageBox.information(self, "Script Added", f"Registered {entry['name']} successfully.")

	def open_script_detail(self, script_data: dict) -> None:
		self.script_detail_page.load(script_data)
		self.pages.setCurrentWidget(self.script_detail_page)

	def open_script_viewer(self, script_data: dict) -> None:
		self.script_viewer_page.load(script_data)
		self.pages.setCurrentWidget(self.script_viewer_page)

	def open_update_version_dialog(self, script_data: dict) -> None:
		dialog = UpdateVersionDialog(script_data, self.script_manager, self)

		def _on_version_added(updated: dict) -> None:
			self.scripts_page.reload_scripts()
			self.sidebar.reload()
			self.script_detail_page.load(updated)

		dialog.version_added.connect(_on_version_added)
		dialog.exec()

	def open_rollback_dialog(self, script_data: dict) -> None:
		dialog = RollbackDialog(script_data, self.script_manager, self)

		def _on_version_changed(updated: dict) -> None:
			self.scripts_page.reload_scripts()
			self.sidebar.reload()
			self.script_detail_page.load(updated)

		dialog.version_changed.connect(_on_version_changed)
		dialog.exec()

	def handle_delete_version(self, script_data: dict) -> None:
		script_uuid = script_data.get("uuid")
		current_ver = script_data.get("current_version", 1)
		versions = script_data.get("versions", {})
		active_count = sum(1 for v in versions.values() if not v.get("trashed"))

		if active_count <= 1:
			confirm = QMessageBox.question(
				self, "Delete Version",
				"This is the only active version. The script will be moved to trash. Continue?",
				QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
			)
			if confirm != QMessageBox.StandardButton.Yes:
				return
			try:
				self.script_manager.delete_script(script_uuid)
			except Exception as exc:
				QMessageBox.critical(self, "Error", str(exc))
				return
			self.scripts_page.reload_scripts()
			self.sidebar.reload()
			self.pages.setCurrentWidget(self.scripts_page)
		else:
			confirm = QMessageBox.question(
				self, "Delete Version",
				f"Move version {current_ver} to trash?\n"
				"The script will switch to the latest remaining version.",
				QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
			)
			if confirm != QMessageBox.StandardButton.Yes:
				return
			try:
				updated = self.script_manager.delete_version(script_uuid, current_ver)
			except Exception as exc:
				QMessageBox.critical(self, "Error", str(exc))
				return
			self.scripts_page.reload_scripts()
			self.sidebar.reload()
			self.script_detail_page.load(updated)

	def open_script_runner(self, script_data: dict) -> None:
		dialog = ScriptRunDialog(script_data, self.script_manager, self)

		def _on_script_updated(updated_entry: dict) -> None:
			self.scripts_page.reload_scripts()
			self.sidebar.reload()
			if self.pages.currentWidget() is self.script_detail_page:
				self.script_detail_page.load(updated_entry)

		dialog.script_updated.connect(_on_script_updated)
		dialog.exec()

	def _open_folder_in_scripts(self, folder_id) -> None:
		self.navbar.set_active_tab(1)
		self.pages.setCurrentWidget(self.scripts_page)
		self.scripts_page.navigate_to(folder_id)

	def toggle_sidebar(self):
		self.sidebar.setVisible(not self.sidebar.isVisible())

	def toggle_theme(self):
		self._current_theme = "dark" if self._current_theme == "light" else "light"
		self._apply_stylesheet()
		next_label = "Light Mode" if self._current_theme == "dark" else "Dark Mode"
		self.navbar.set_theme_label(next_label)

	def _refresh_after_trash_action(self):
		# Refresh scripts list and sidebar after trash/restore actions
		try:
			self.scripts_page.reload_scripts()
			self.sidebar.reload()
		except Exception:
			pass

	def _apply_stylesheet(self):
		filename = "style_dark.qss" if self._current_theme == "dark" else "style.qss"
		style_path = resource_path(Path("assets") / filename)
		if not style_path.exists():
			style_path = Path(__file__).resolve().parent / "assets" / filename

		app = QApplication.instance()

		if style_path.exists():
			# Apply at app level — ensures every widget in the process gets it,
			# not just descendants of this window.
			app.setStyleSheet(style_path.read_text(encoding="utf-8"))
		else:
			print(f"Warning: Stylesheet not found at {style_path}")

		if self._current_theme == "light":
			app.setPalette(_build_light_palette())
		else:
			# Dark mode works with the default Fusion palette + QSS overrides.
			app.setPalette(app.style().standardPalette())


def main():
	app = QApplication(sys.argv)
	app.setStyle("Fusion")
	# Set the palette BEFORE creating any widgets so every widget starts
	# with the correct colours — not the Fusion defaults.
	app.setPalette(_build_light_palette())
	window = MainWindow()
	window.showMaximized()
	sys.exit(app.exec())


if __name__ == "__main__":
	main()
