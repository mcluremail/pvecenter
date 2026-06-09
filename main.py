import sys
import logging
from PySide6.QtWidgets import QApplication
from .config import load_config, load_ui_state

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

    # Initialize i18n from saved language preference
    lang = load_ui_state("language") or "en"
    from .ui.i18n import set_language
    set_language(lang)

    from .ui.mainwindow import MainWindow
    window = MainWindow(nodes_cfg)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
