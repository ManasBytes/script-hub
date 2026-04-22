from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QStyle

class Navbar(QWidget):
    def __init__(self, switch_page_callback, toggle_sidebar_callback):
        super().__init__()
        self.setObjectName("navbar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(10)

        title = QLabel("ScriptHub")
        title.setObjectName("brandTitle")

        tabs_wrap = QHBoxLayout()
        tabs_wrap.setSpacing(8)
        tabs_wrap.setContentsMargins(0, 0, 0, 0)

        btn_home = QPushButton("Home")
        btn_scripts = QPushButton("Scripts")
        btn_history = QPushButton("History")

        for button in (btn_home, btn_scripts, btn_history):
            button.setObjectName("topTabButton")
            button.setCheckable(True)
            tabs_wrap.addWidget(button)

        btn_home.setChecked(True)

        btn_home.clicked.connect(lambda: self._activate(0, switch_page_callback))
        btn_scripts.clicked.connect(lambda: self._activate(1, switch_page_callback))
        btn_history.clicked.connect(lambda: self._activate(2, switch_page_callback))

        self._tab_buttons = [btn_home, btn_scripts, btn_history]

        status = QLabel("Ready")
        status.setObjectName("navStatus")

        sidebar_toggle = QPushButton("Scripts")
        sidebar_toggle.setObjectName("sidebarToggleButton")
        sidebar_toggle.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton))
        sidebar_toggle.setToolTip("Toggle script sidebar")
        sidebar_toggle.clicked.connect(toggle_sidebar_callback)

        layout.addWidget(sidebar_toggle)
        layout.addWidget(title)
        layout.addStretch()
        layout.addLayout(tabs_wrap)
        layout.addStretch()
        layout.addWidget(status)

    def _activate(self, idx, switch_page_callback):
        for i, button in enumerate(self._tab_buttons):
            button.setChecked(i == idx)
        switch_page_callback(idx)

