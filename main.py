import sys
import logging
from PySide6.QtWidgets import QApplication, QMessageBox
from .config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    force=True
)

def main():
    app = QApplication(sys.argv)

    nodes_cfg = load_config()
    if nodes_cfg is None:
        return

    from .ui.mainwindow import MainWindow
    window = MainWindow(nodes_cfg)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
