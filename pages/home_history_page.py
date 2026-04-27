from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QFrame, QVBoxLayout, QWidget


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
