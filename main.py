import sys
from pathlib import Path

from PyQt6.QtWidgets import (
	QApplication,
	QLabel,
	QMainWindow,
	QStackedWidget,
	QVBoxLayout,
	QWidget,
	QHBoxLayout,
	QFrame,
)
from PyQt6.QtCore import Qt

from components import Navbar, Sidebar


def resource_path(relative_path):
	"""Resolve bundled resources for both dev runs and PyInstaller executables."""
	base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
	return base_path / relative_path


class Page(QWidget):
	def __init__(self, object_name, title_text, subtitle_text):
		super().__init__()
		self.setObjectName(object_name)

		layout = QVBoxLayout(self)
		layout.setContentsMargins(28, 24, 28, 24)
		layout.setSpacing(14)
		layout.setAlignment(Qt.AlignmentFlag.AlignTop)

		title = QLabel(title_text)
		title.setObjectName("pageTitle")

		subtitle = QLabel(subtitle_text)
		subtitle.setObjectName("pageSubtitle")

		card = QFrame()
		card.setObjectName("contentCard")
		card_layout = QVBoxLayout(card)
		card_layout.setContentsMargins(18, 16, 18, 16)
		card_layout.setSpacing(8)

		card_title = QLabel("Starter Section")
		card_title.setObjectName("cardTitle")

		card_text = QLabel(
			"This is a clean base shell for your dashboard. "
			"You can now plug in real data and controls page by page."
		)
		card_text.setWordWrap(True)
		card_text.setObjectName("cardText")

		card_layout.addWidget(card_title)
		card_layout.addWidget(card_text)

		layout.addWidget(title)
		layout.addWidget(subtitle)
		layout.addWidget(card)


class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Scripts Architect")
		self.setObjectName("appRoot")

		root = QWidget()
		root_layout = QVBoxLayout(root)
		root_layout.setContentsMargins(0, 0, 0, 0)
		root_layout.setSpacing(0)

		self.navbar = Navbar(self.switch_page, self.toggle_sidebar)
		self.sidebar = Sidebar()

		self.pages = QStackedWidget()
		self.pages.setObjectName("mainContent")
		self.pages.addWidget(Page("Home", "Home", "Your command center and quick overview."))
		self.pages.addWidget(Page("ScriptsPage", "Scripts", "Manage and run your script collection."))
		self.pages.addWidget(Page("HistoryPage", "History", "Track execution logs and previous runs."))

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

	def toggle_sidebar(self):
		self.sidebar.setVisible(not self.sidebar.isVisible())

	def _apply_stylesheet(self):
		style_path = resource_path(Path("assets") / "style.qss")

		# Fallback for local runs if bundle path is unavailable.
		if not style_path.exists():
			style_path = Path(__file__).resolve().parent / "assets" / "style.qss"

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
