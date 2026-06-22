from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                                QHBoxLayout, QFrame)
from PySide6.QtCore import Qt
from .i18n import tr
from .theme import Color


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("About"))
        self.setMinimumWidth(380)
        self.setStyleSheet(f"QDialog {{ background: {Color.PANEL}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 20)

        from .. import __version__, __author__, __license__

        title = QLabel("PVE Center")
        f = title.font()
        f.setPointSize(20)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {Color.TEXT};")
        layout.addWidget(title)

        version_label = QLabel(f"v{__version__}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet(f"color: {Color.TEXT_SEC}; font-size: 13px;")
        layout.addWidget(version_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {Color.BORDER};")
        layout.addWidget(sep)

        info_rows = [
            (tr("Author"), __author__),
            (tr("License"), __license__),
            (tr("Source"), "github.com/mcluremail/pvecenter"),
        ]
        for label, value in info_rows:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {Color.TEXT_SEC}; font-size: 12px;")
            lbl.setFixedWidth(80)
            val = QLabel(value)
            val.setStyleSheet(f"color: {Color.TEXT}; font-size: 12px;")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(lbl)
            row.addWidget(val)
            row.addStretch()
            layout.addLayout(row)

        desc = QLabel(tr("Desktop client for Proxmox VE"))
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Color.TEXT_DIM}; font-size: 12px; padding-top: 8px;")
        layout.addWidget(desc)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton(tr("Close"))
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)