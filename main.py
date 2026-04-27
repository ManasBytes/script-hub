import sys
from pathlib import Path

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
from pages import AddScriptPage, Page, ScriptDetailPage, ScriptViewerPage, ScriptsPage
from script_manager import ScriptManager


def resource_path(relative_path):
	"""Resolve bundled resources for both dev runs and PyInstaller executables."""
	base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
	return base_path / relative_path


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
		self.history_page = Page("HistoryPage", "History", "Track execution logs and previous runs.")
		self.add_script_page = AddScriptPage()
		self.script_detail_page = ScriptDetailPage()
		self.script_viewer_page = ScriptViewerPage()

		self.scripts_page.add_requested.connect(self.open_add_script_page)
		self.scripts_page.scripts_changed.connect(self.sidebar.reload)
		self.scripts_page.view_script_requested.connect(self.open_script_detail)
		self.sidebar.script_selected.connect(self.open_script_detail)
		self.add_script_page.back_to_scripts.connect(self.open_scripts_page)
		self.add_script_page.submit_requested.connect(self.handle_script_submission)
		self.script_detail_page.back_requested.connect(
			lambda: self.pages.setCurrentWidget(self.scripts_page)
		)
		self.script_detail_page.view_source_requested.connect(self.open_script_viewer)
		self.script_viewer_page.back_requested.connect(
			lambda: self.pages.setCurrentWidget(self.script_detail_page)
		)

		self.pages.addWidget(self.home_page)
		self.pages.addWidget(self.scripts_page)
		self.pages.addWidget(self.history_page)
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
		self.pages.setCurrentIndex(index)

	def open_add_script_page(self):
		self.add_script_page.reset()
		self.pages.setCurrentWidget(self.add_script_page)

	def open_scripts_page(self):
		self.scripts_page.reload_scripts()
		self.pages.setCurrentWidget(self.scripts_page)

	def handle_script_submission(self, payload):
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

	def toggle_sidebar(self):
		self.sidebar.setVisible(not self.sidebar.isVisible())

	def toggle_theme(self):
		self._current_theme = "dark" if self._current_theme == "light" else "light"
		self._apply_stylesheet()
		next_label = "Light Mode" if self._current_theme == "dark" else "Dark Mode"
		self.navbar.set_theme_label(next_label)

	def _apply_stylesheet(self):
		filename = "style_dark.qss" if self._current_theme == "dark" else "style.qss"
		style_path = resource_path(Path("assets") / filename)

		if not style_path.exists():
			style_path = Path(__file__).resolve().parent / "assets" / filename

		if style_path.exists():
			self.setStyleSheet(style_path.read_text(encoding="utf-8"))
		else:
			print(f"Warning: Stylesheet not found at {style_path}")


def main():
	app = QApplication(sys.argv)
	app.setStyle("Fusion")
	window = MainWindow()
	window.showMaximized()
	sys.exit(app.exec())


if __name__ == "__main__":
	main()
