import logging
import sys

from PySide6.QtWidgets import QApplication

from .config import load_config, load_ui_state

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    force=True
)


def main():
    app = QApplication(sys.argv)

    from .ui.i18n import set_language
    lang = load_ui_state("language") or "en"
    set_language(lang)

    nodes_cfg = load_config()

    from .ui.mainwindow import MainWindow
    window = MainWindow(nodes_cfg)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
