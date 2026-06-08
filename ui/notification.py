from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PySide6.QtCore import QTimer, Qt, QPropertyAnimation, QRect, Property
from PySide6.QtGui import QColor


class FadeToast(QWidget):
    """Затухающее уведомление в правом верхнем углу родителя."""

    def __init__(self, parent, text, color="#1f2937"):
        super().__init__(parent)
        self._opacity = 1.0
        self._text = text
        self._bg_color = color
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        self.label = QLabel(text)
        self.label.setStyleSheet(f"""
            color: white;
            font-size: 12px;
            font-weight: 500;
            background: {color};
            border-radius: 6px;
            padding: 6px 14px;
        """)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(320)
        self.label.setCursor(Qt.PointingHandCursor)
        self.label.mousePressEvent = lambda e: self._copy_to_clipboard()
        layout.addWidget(self.label)

        self.adjustSize()

        # Позиционируем в правом верхнем углу родителя
        parent_rect = parent.rect()
        x = parent_rect.width() - self.width() - 20
        y = 12
        self.move(x, y)

        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.setInterval(4000)
        self._fade_timer.timeout.connect(self._start_fade)

        self._fade_anim = QPropertyAnimation(self, b"opacity")
        self._fade_anim.setDuration(600)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self.deleteLater)

        self.show()
        self._fade_timer.start()

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, val):
        self._opacity = val
        self.setWindowOpacity(val)

    opacity = Property(float, get_opacity, set_opacity)

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self._text)
        self.label.setStyleSheet(self.label.styleSheet().replace("color: white;", "color: #bbf7d0;"))
        QTimer.singleShot(400, self._restore_color)

    def _restore_color(self):
        self.label.setStyleSheet(self.label.styleSheet().replace("color: #bbf7d0;", "color: white;"))

    def _start_fade(self):
        self._fade_anim.start()


class NotificationManager:
    """Показывает тосты об изменении статусов. Не дублирует одинаковые."""

    def __init__(self, parent):
        self.parent = parent
        self._active = {}  # key -> текущий тост

    def host_status_changed(self, host_name, old_status, new_status):
        key = f"host:{host_name}"
        text = ""
        color = ""
        if new_status == "error" or new_status == "offline":
            text = f"❌ {host_name} — недоступен"
            color = "#dc2626"
        elif old_status in ("error", "offline", "unknown") and new_status == "online":
            text = f"✅ {host_name} — снова в сети"
            color = "#16a34a"
        elif new_status == "online":
            text = f"🟢 {host_name} — онлайн"
            color = "#1f2937"
        else:
            text = f"🟡 {host_name} — {new_status}"
            color = "#d97706"

        self._show(key, text, color)

    def vm_status_changed(self, vm_name, host_name, old_status, new_status):
        key = f"vm:{host_name}:{vm_name}"
        status_ru = {"running": "Работает", "stopped": "Остановлена", "paused": "Приостановлена"}
        ru = status_ru.get(new_status, new_status)
        status_icon = "🟢" if new_status == "running" else "🔴" if new_status == "stopped" else "🟡"
        color = "#16a34a" if new_status == "running" else "#dc2626" if new_status == "stopped" else "#d97706"
        self._show(key, f"{status_icon} {vm_name} — {ru}", color)

    def _show(self, key, text, color):
        existing = self._active.get(key)
        if existing:
            existing._fade_timer.stop()
            existing._fade_anim.stop()
            existing.deleteLater()
        toast = FadeToast(self.parent, text, color)
        self._active[key] = toast
        toast.destroyed.connect(lambda k=key: self._active.pop(k, None))

    def show(self, text, error=False):
        color = "#dc2626" if error else "#1f2937"
        self._show(text, text, color)