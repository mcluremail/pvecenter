"""Общие утилиты UI: переводы, форматирование."""

STATUS_RU = {
    "running": "Работает",
    "stopped": "Остановлена",
    "paused": "Приостановлена",
    "error": "Ошибка",
    "offline": "Недоступен",
    "online": "Доступен",
    "unknown": "Неизвестно",
    "mounted": "Подключено",
}


def ru_status(s):
    """Возвращает русский перевод статуса для отображения."""
    return STATUS_RU.get(s, s)


def format_uptime(seconds):
    """Форматирует uptime в секундах в компактный вид: '5d 3h 20m 10s'."""
    if not seconds or seconds <= 0:
        return ""
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)
