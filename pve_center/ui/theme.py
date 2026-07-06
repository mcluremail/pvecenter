"""
Тема оформления PVE Center.
Светлая. Шрифты резолвятся из доступных в системе (Noto Sans / Terminus
приоритетны, на Windows/под macOS подставляются системные аналоги).
"""

import logging
import os

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


def _app() -> QApplication:
    """Возвращает текущий экземпляр QApplication."""
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("theme.load(): QApplication ещё не создан")
    return app


# ── Цветовая палитра ──────────────────────────────────────────────

class Color:
    """Цвета темы — светлая."""

    # Фоны
    BG          = "#fafafa"
    PANEL       = "#ffffff"
    RAISED      = "#f4f5f7"
    ALT_ROW     = "#f8f9fb"

    # Границы
    BORDER      = "#e5e7eb"
    BORDER_LIGHT = "#f0f1f4"

    # Текст
    TEXT        = "#181c26"
    TEXT_SEC    = "#6b7280"
    TEXT_DIM    = "#9ca3af"
    DISABLED    = "#b0b8c4"

    # Акцент
    ACCENT      = "#0a6ed1"
    ACCENT_HOVER = "#005bbf"
    ACCENT_LIGHT = "#e8f0fe"
    ACCENT_GREEN = "#16a34a"

    SUCCESS     = "#16a34a"
    WARNING     = "#d97706"
    DANGER      = "#dc2626"

    STATUS_OK    = "#22c55e"
    STATUS_WARN  = "#f59e0b"
    STATUS_ERR   = "#ef4444"

    GRAY_400    = "#9ca3af"
    GRAY_500    = "#6b7280"
    GRAY_200    = "#e5e7eb"
    GRAY_100    = "#f3f4f6"
    SLATE_100   = "#f1f5f9"
    SLATE_200   = "#e2e8f0"
    SLATE_300   = "#cbd5e1"
    SLATE_400   = "#94a3b8"
    SLATE_500   = "#475569"
    SLATE_700   = "#334155"
    SLATE_800   = "#1f2937"
    SLATE_900   = "#374151"
    D1_D5_DB    = "#d1d5db"

    WARN_ROW_BG = "#fef3c7"
    OK_ROW_BG   = "#bbf7d0"
    ERROR_RED   = "#c0392b"

    # Hover / selection
    HOVER       = "#e8edf4"
    SELECTED    = "#dbe4f0"

    # Специальные
    WARN_BG     = "#fff3cd"   # жёлтый фон для warning-строк
    WARN_BORDER = "#ffc107"

    # Скроллбар
    SCROLLBAR_BG    = "#eef1f5"
    SCROLLBAR_HANDLE = "#c0c6d0"
    SCROLLBAR_HOVER  = "#a4abb8"

    # Шрифты — резолвятся из установленных в системе (см. _resolve_fonts ниже).
    UI_FONT   = "Noto Sans"
    MONO_FONT = "Noto Sans Mono"


# ── Резолвинг шрифтов по доступности в системе ─────────────────────
# Приоритетные кандидаты: первый найденный через QFontDatabase.hasFamily
# используется как имя шрифта в QSS и app.setFont. На Windows/macOS
# Noto-семейства обычно отсутствуют, и выбирается системный аналог.
_UI_CANDIDATES = (
    "Noto Sans", "Cantarell", "Segoe UI", "SF Pro Text", "Helvetica",
)
_MONO_CANDIDATES = (
    "Terminus", "Noto Sans Mono", "Cascadia Code", "Consolas",
    "Menlo", "DejaVu Sans Mono", "Liberation Mono",
)


def _pick_font(candidates):
    """Вернуть первое доступное в системе имя шрифта, иначе последний из списка."""
    db = QFontDatabase
    for name in candidates:
        try:
            if db.hasFamily(name):
                return name
        except Exception:
            pass
    return candidates[-1]


def _resolve_fonts():
    """Резолвинг UI/MONO один раз при load(). Логирует выбранные имена."""
    Color.UI_FONT = _pick_font(_UI_CANDIDATES)
    Color.MONO_FONT = _pick_font(_MONO_CANDIDATES)
    logger.info("theme fonts: ui=%s, mono=%s", Color.UI_FONT, Color.MONO_FONT)


# ── Пути к SVG-индикаторам чекбокса ──
_CHECK_DIR = os.path.dirname(os.path.abspath(__file__))
_CHECK_ON  = _CHECK_DIR + "/checkbox-checked.svg"
_CHECK_OFF = _CHECK_DIR + "/checkbox-unchecked.svg"

# ── QSS ────────────────────────────────────────────────────────────
# QSS собирается функцией _build_qss() в load(), после того как
# _resolve_fonts() подставит доступные имена шрифтов в Color.UI_FONT /
# Color.MONO_FONT. До вызова load() QSS содержит пустую строку —
# использовать app.setStyleSheet(QSS) напрямую нельзя.

QSS = ""


def _build_qss() -> str:
    ui = Color.UI_FONT
    mono = Color.MONO_FONT
    return f"""
    * {{
        font-family: "{ui}", "Cantarell", "sans-serif";
        font-size: 14px;
        color: {Color.TEXT};
    }}

    /* ── Header bar ── */
    QToolBar {{
        background: {Color.PANEL};
        border: none;
        border-bottom: 1px solid {Color.BORDER_LIGHT};
        spacing: 4px;
        padding: 4px 12px;
    }}
    QToolBar::separator {{
        width: 1px;
        background: {Color.BORDER_LIGHT};
        margin: 4px 4px;
    }}
    QToolButton {{
        border: none;
        border-radius: 6px;
        padding: 4px 8px;
        background: transparent;
        color: {Color.TEXT_SEC};
        font-size: 13px;
    }}
    QToolButton:hover {{
        background: {Color.RAISED};
        color: {Color.TEXT};
    }}
    QToolButton:pressed {{
        background: {Color.ALT_ROW};
    }}
    QToolButton:checked {{
        background: {Color.ACCENT_LIGHT};
        color: {Color.ACCENT};
    }}

    /* ── Дерево навигации ── */
    QTreeWidget {{
        font-size: 13px;
        alternate-background-color: transparent;
        border: none;
        outline: none;
        background: {Color.PANEL};
    }}
    QTreeWidget::item {{
        padding: 3px 4px;
        min-height: 22px;
        border-left: 2px solid transparent;
    }}
    QTreeWidget::item:hover {{
        background: {Color.RAISED};
    }}
    QTreeWidget::item:selected {{
        background: {Color.ACCENT_LIGHT};
        color: {Color.ACCENT};
        border-left-color: {Color.ACCENT};
        font-weight: 500;
    }}
    QTreeView::branch {{
        background: transparent;
    }}

    /* ── Таблицы данных ── */
    QTableWidget {{
        font-family: "{ui}", "Cantarell", "sans-serif";
        font-size: 13px;
        background: {Color.PANEL};
        alternate-background-color: {Color.ALT_ROW};
        gridline-color: {Color.BORDER_LIGHT};
        border: 1px solid {Color.BORDER};
        border-radius: 8px;
    }}
    QTableWidget::item {{
        padding: 4px 8px;
    }}
    QTableWidget::item:hover {{
        background: {Color.RAISED};
    }}
    QTableWidget::item:selected {{
        background: {Color.ACCENT_LIGHT};
        color: {Color.TEXT};
    }}

    QHeaderView::section {{
        font-family: "{ui}", "Cantarell", "sans-serif";
        font-weight: 600;
        padding: 6px 8px;
        background-color: transparent;
        border: none;
        border-bottom: 1px solid {Color.BORDER_LIGHT};
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: {Color.TEXT_DIM};
    }}
    QHeaderView::section:hover {{
        color: {Color.TEXT_SEC};
    }}
    QTableCornerButton::section {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {Color.BORDER_LIGHT};
    }}

    /* ── Вкладки (segmented control) ── */
    QTabWidget::pane {{
        border: none;
        border-top: 1px solid {Color.BORDER};
        background: {Color.BG};
        padding: 20px 24px;
    }}
    QTabBar {{
        margin-left: 0;
        background: transparent;
    }}
    QTabBar::tab {{
        padding: 10px 16px;
        font-size: 13px;
        color: {Color.TEXT_SEC};
        border: none;
        border-bottom: 2px solid transparent;
        margin-right: 0;
        font-weight: 500;
    }}
    QTabBar::tab:hover {{
        color: {Color.TEXT};
    }}
    QTabBar::tab:selected {{
        color: {Color.ACCENT};
        font-weight: 600;
        border-bottom: 2px solid {Color.ACCENT};
    }}

    /* ── Прогресс-бар ── */
    QProgressBar {{
        border: none;
        border-radius: 3px;
        text-align: center;
        height: 6px;
        background: {Color.GRAY_100};
        font-size: 11px;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background-color: {Color.ACCENT};
        border-radius: 3px;
    }}

    /* ── Кнопки ── */
    QPushButton {{
        padding: 7px 14px;
        font-size: 13px;
        border: 1px solid {Color.BORDER};
        border-radius: 6px;
        background: {Color.PANEL};
        color: {Color.TEXT};
        font-weight: 500;
    }}
    QPushButton:hover {{
        background: {Color.RAISED};
        border-color: {Color.TEXT_DIM};
    }}
    QPushButton:pressed {{
        background: {Color.ALT_ROW};
    }}
    QPushButton:disabled {{
        color: {Color.DISABLED};
        background: {Color.ALT_ROW};
        border-color: {Color.BORDER_LIGHT};
    }}

    /* ── Диалоги ── */
    QDialog {{
        background: {Color.PANEL};
    }}

    /* Кнопка обновления */
    QPushButton#refreshBtn {{
        background: transparent;
        border: none;
        padding: 2px;
        min-width: 20px;
        max-width: 20px;
        min-height: 20px;
        max-height: 20px;
    }}
    QPushButton#refreshBtn:hover {{
        background: {Color.HOVER};
        border-radius: 3px;
    }}
    QPushButton#refreshBtn:pressed {{
        background: {Color.ALT_ROW};
        border-radius: 3px;
    }}

    /* Акцентные кнопки (Start, Console, Создать ВМ) */
    QPushButton#accentBtn {{
        background: {Color.ACCENT};
        color: white;
        border: 1px solid {Color.ACCENT};
        font-weight: 600;
    }}
    QPushButton#accentBtn:hover {{
        background: {Color.ACCENT_HOVER};
    }}
    QPushButton#accentBtn:pressed {{
        background: {Color.ACCENT_HOVER};
    }}
    QPushButton#accentBtn:disabled {{
        background: {Color.DISABLED};
        border-color: {Color.BORDER};
        color: white;
    }}

    /* Опасные кнопки (Удаление) */
    QPushButton#dangerBtn {{
        background: #c0392b;
        color: white;
        border: 1px solid #c0392b;
        font-weight: 600;
    }}
    QPushButton#dangerBtn:hover {{
        background: #e74c3c;
    }}
    QPushButton#dangerBtn:pressed {{
        background: #a93226;
    }}
    QPushButton#dangerBtn:disabled {{
        background: {Color.DISABLED};
        border-color: {Color.BORDER};
        color: white;
    }}

    /* ── Сплиттер ── */
    QSplitter::handle {{
        width: 6px;
        background: {Color.BORDER};
        margin: 0 1px;
    }}
    QSplitter::handle:hover {{
        background: {Color.SCROLLBAR_HOVER};
    }}

    /* ── Меню ── */
    QMenu {{
        border: 1px solid {Color.BORDER};
        background: {Color.PANEL};
    }}
    QMenu::item {{
        padding: 4px 24px 4px 12px;
    }}
    QMenu::item:selected {{
        background: {Color.ACCENT_LIGHT};
        color: {Color.ACCENT};
    }}
    QMenu::separator {{
        height: 1px;
        background: {Color.BORDER};
        margin: 4px 8px;
    }}

    /* ── Tooltip ── */
    QToolTip {{
        background: {Color.TEXT};
        color: {Color.PANEL};
        border: none;
        padding: 4px 8px;
        font-size: 13px;
    }}

    /* ── Line Edit ── */
    QLineEdit {{
        border: 1px solid {Color.BORDER};
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 13px;
        background: {Color.PANEL};
    }}
    QLineEdit:focus {{
        border-color: {Color.ACCENT};
    }}

    /* ── ComboBox ── */
    QComboBox {{
        border: 1px solid {Color.BORDER};
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 13px;
        background: {Color.PANEL};
    }}
    QComboBox:focus {{
        border-color: {Color.ACCENT};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox::down-arrow {{
        image: url({_CHECK_DIR}/arrow-down.svg);
        width: 10px;
        height: 8px;
    }}

    /* ── Скроллбар (тонкий, закруглённый) ── */
    QScrollBar:vertical {{
        width: 10px;
        background: {Color.SCROLLBAR_BG};
        border-radius: 5px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {Color.SCROLLBAR_HANDLE};
        border-radius: 5px;
        min-height: 30px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {Color.SCROLLBAR_HOVER};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}

    QScrollBar:horizontal {{
        height: 10px;
        background: {Color.SCROLLBAR_BG};
        border-radius: 5px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {Color.SCROLLBAR_HANDLE};
        border-radius: 5px;
        min-width: 30px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {Color.SCROLLBAR_HOVER};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: none;
    }}

    /* ── Чекбоксы ── */
    QCheckBox {{
        font-size: 13px;
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {Color.BORDER};
        border-radius: 3px;
        background: {Color.PANEL};
    }}
    QCheckBox::indicator:hover {{
        border-color: {Color.ACCENT};
    }}
    QCheckBox::indicator:checked {{
        image: url({_CHECK_ON});
    }}
    QCheckBox::indicator:unchecked {{
        image: url({_CHECK_OFF});
    }}
    QCheckBox::indicator:indeterminate {{
        image: url({_CHECK_OFF});
    }}

    /* ── SpinBox ── */
    QSpinBox {{
        border: 1px solid {Color.BORDER};
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 13px;
        background: {Color.PANEL};
        min-height: 22px;
        min-width: 100px;
    }}
    QSpinBox:focus {{
        border-color: {Color.ACCENT};
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        subcontrol-origin: border;
        width: 22px;
        border: none;
        background: transparent;
    }}
    QSpinBox::up-button {{
        subcontrol-position: top right;
        border-top-right-radius: 3px;
    }}
    QSpinBox::down-button {{
        subcontrol-position: bottom right;
        border-bottom-right-radius: 3px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background: {Color.ACCENT_LIGHT};
    }}
    QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
        background: #c6dafc;
    }}
    QSpinBox::up-arrow {{
        image: url({_CHECK_DIR}/arrow-up.svg);
        width: 10px;
        height: 8px;
    }}
    QSpinBox::down-arrow {{
        image: url({_CHECK_DIR}/arrow-down.svg);
        width: 10px;
        height: 8px;
    }}

    /* ── Заголовки секций в диалогах ── */
    QLabel#sectionTitle {{
        font-size: 14px;
        font-weight: 700;
        color: {Color.TEXT};
        letter-spacing: 0.3px;
    }}

    /* ── Подписи полей в форме ── */
    QLabel#fieldLabel {{
        color: {Color.TEXT_SEC};
        font-size: 13px;
    }}

    /* ── Разделитель секций ── */
    QFrame#sectionSep {{
        color: {Color.BORDER};
        margin: 4px 0;
    }}

    /* ── Кнопка «Дополнительно» (collapsible toggle) ── */
    QToolButton#extraToggle {{
        border: none;
        background: transparent;
        font-size: 13px;
        font-weight: 600;
        color: {Color.ACCENT};
        padding: 4px 0;
    }}
    QToolButton#extraToggle:hover {{
        color: {Color.ACCENT_HOVER};
    }}

    /* ── ScrollArea (убираем рамку) ── */
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QPlainTextEdit {{
        font-family: "{mono}", "Noto Sans Mono", monospace;
        font-size: 13px;
        background: {Color.PANEL};
        border: 1px solid {Color.BORDER};
        border-radius: 6px;
    }}

    /* ── Title block (заголовок объекта) ── */
    QLabel#titleMain {{
        font-size: 22px;
        font-weight: 600;
        letter-spacing: -0.02em;
        color: {Color.TEXT};
    }}
    QLabel#titleSub {{
        font-size: 13px;
        color: {Color.TEXT_SEC};
    }}

    /* ── Карточки метрик ── */
    QFrame#metricCard {{
        background: {Color.PANEL};
        border: 1px solid {Color.BORDER};
        border-radius: 10px;
    }}

    /* ── Список карточек ── */
    QFrame#cardList {{
        background: {Color.PANEL};
        border: 1px solid {Color.BORDER};
        border-radius: 10px;
    }}
    QFrame#cardRow {{
        border: none;
        border-bottom: 1px solid {Color.BORDER_LIGHT};
    }}
    QFrame#cardRow:last {{
        border-bottom: none;
    }}
    QFrame#cardRow:hover {{
        background: {Color.RAISED};
    }}

    /* ── Key-value секции (Hardware/Options) ── */
    QLabel#kvSectionHead {{
        font-size: 12px;
        font-weight: 600;
        color: {Color.TEXT_DIM};
        letter-spacing: 0.05em;
    }}
    QFrame#kvSeparator {{
        background: {Color.BORDER_LIGHT};
        max-height: 1px;
    }}

    /* ── Status bar ── */
    QStatusBar {{
        background: {Color.PANEL};
        border-top: 1px solid {Color.BORDER_LIGHT};
        font-size: 12px;
        color: {Color.TEXT_SEC};
    }}
"""


# ── Публичный API ──────────────────────────────────────────────────

def load():
    """Устанавливает шрифты и таблицу стилей для приложения."""
    app = _app()
    _resolve_fonts()
    global QSS
    QSS = _build_qss()
    app.setStyleSheet(QSS)

    ui_font = QFont(Color.UI_FONT, 14)
    ui_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(ui_font)
