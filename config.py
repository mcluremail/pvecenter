import json
import os
import base64
import sqlite3
import threading

SALT_FILE = "nodes.salt"
ENC_FILE = "nodes.enc"
CONFIG_JSON = "nodes.json"
TASKS_DB = "tasks_cache.sqlite"

def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))

def _config_dir():
    """Возвращает ~/.config/pve-center/, создавая если нет."""
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = os.path.join(xdg, "pve-center")
    os.makedirs(d, exist_ok=True)
    return d

def _migrate_if_needed(name):
    """Переносит файл из _base_dir() в _config_dir(), если он есть только в старом месте.
    После переноса — если в _base_dir() не осталось наших файлов, удаляет пустую директорию."""
    src = os.path.join(_base_dir(), name)
    dst = os.path.join(_config_dir(), name)
    if os.path.exists(src) and not os.path.exists(dst):
        import shutil
        shutil.move(src, dst)
    # Чистим пустую старую директорию, если там не осталось наших файлов
    for leftover in (SALT_FILE, ENC_FILE, CONFIG_JSON):
        if os.path.exists(os.path.join(_base_dir(), leftover)):
            return
    try:
        if os.path.isdir(_base_dir()) and not os.listdir(_base_dir()):
            os.rmdir(_base_dir())
    except OSError:
        pass

def _derive_key(password: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def _encrypt_to_file(config_list, password, enc_path):
    from cryptography.fernet import Fernet
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    plain = json.dumps(config_list, ensure_ascii=False, indent=2).encode()
    token = Fernet(key).encrypt(plain)
    with open(enc_path, "wb") as fh:
        fh.write(salt + token)

def _decrypt_from_file(enc_path, password):
    from cryptography.fernet import Fernet
    with open(enc_path, "rb") as fh:
        data = fh.read()
    salt, token = data[:16], data[16:]
    key = _derive_key(password, salt)
    plain = Fernet(key).decrypt(token)
    return json.loads(plain.decode())

# ------------------------------------------------------------
# Password dialog (lazy import PySide6 to keep CLI importable)
# ------------------------------------------------------------
def _ask_password(mode="enter"):
    """Показывает диалог ввода пароля.
    mode='enter' — существующий пароль, mode='set' — установка нового.
    Возвращает пароль или None (отмена)."""
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                   QLineEdit, QPushButton, QApplication)
    dialog = QDialog()
    dialog.setWindowTitle("PVE Dashboard — Авторизация")
    dialog.setFixedSize(380, 160)

    layout = QVBoxLayout(dialog)

    if mode == "set":
        layout.addWidget(QLabel("Установите мастер-пароль для шифрования токенов:"))
    else:
        layout.addWidget(QLabel("Введите мастер-пароль:"))

    pwd_input = QLineEdit()
    pwd_input.setEchoMode(QLineEdit.Password)
    layout.addWidget(pwd_input)

    if mode == "set":
        layout.addWidget(QLabel("Повторите пароль:"))
        confirm_input = QLineEdit()
        confirm_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(confirm_input)
    else:
        confirm_input = None

    error_label = QLabel("")
    error_label.setStyleSheet("color: #9ca3af;")
    layout.addWidget(error_label)

    btn_layout = QHBoxLayout()
    ok_btn = QPushButton("OK")
    cancel_btn = QPushButton("Отмена")
    btn_layout.addStretch()
    btn_layout.addWidget(ok_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)

    result = [None]

    def on_ok():
        pwd = pwd_input.text()
        if not pwd:
            error_label.setText("Пароль не может быть пустым")
            return
        if confirm_input is not None and pwd != confirm_input.text():
            error_label.setText("Пароли не совпадают")
            return
        result[0] = pwd
        dialog.accept()

    ok_btn.clicked.connect(on_ok)
    cancel_btn.clicked.connect(dialog.reject)
    pwd_input.returnPressed.connect(on_ok)
    if confirm_input:
        confirm_input.returnPressed.connect(on_ok)

    if dialog.exec() == QDialog.Accepted:
        return result[0]
    return None

_password = None  # кешированный мастер-пароль


def cache_password(pwd):
    global _password
    _password = pwd


def save_config(config_list):
    """Сохраняет конфигурацию, используя кешированный мастер-пароль (если есть)."""
    global _password
    for fn in (SALT_FILE, ENC_FILE, CONFIG_JSON):
        _migrate_if_needed(fn)
    base = _config_dir()
    enc_path = os.path.join(base, ENC_FILE)
    json_path = os.path.join(base, CONFIG_JSON)

    if _password:
        _encrypt_to_file(config_list, _password, enc_path)
        if os.path.exists(json_path):
            os.remove(json_path)
    else:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(config_list, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------
def load_config():
    """Загружает конфигурацию. При необходимости показывает диалог пароля.
    Возвращает список узлов или None (отмена)."""
    global _password
    for fn in (SALT_FILE, ENC_FILE, CONFIG_JSON):
        _migrate_if_needed(fn)
    base = _config_dir()
    enc_path = os.path.join(base, ENC_FILE)

    if os.path.exists(enc_path):
        while True:
            password = _ask_password("enter")
            if password is None:
                return None
            cache_password(password)
            try:
                return _decrypt_from_file(enc_path, password)
            except Exception:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(None, "Ошибка",
                                     "Неверный пароль. Попробуйте снова.")
                # цикл: снова показываем диалог пароля
    else:
        json_path = os.path.join(base, CONFIG_JSON)
        if not os.path.exists(json_path):
            return []
        with open(json_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        # Проверяем, есть ли токены
        has_tokens = any(cfg.get("token_value") for cfg in config)
        if has_tokens:
            password = _ask_password("set")
            if password is None:
                return config
            cache_password(password)
            _encrypt_to_file(config, password, enc_path)
            from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                           QLabel, QPushButton)
            dlg = QDialog()
            dlg.setWindowTitle("Безопасность")
            dlg.setFixedSize(480, 140)
            l = QVBoxLayout(dlg)
            l.addWidget(QLabel("Токены зашифрованы в nodes.enc. Удалить nodes.json "
                               "(исходный файл с токенами в открытом виде)?"))
            l.addStretch()
            bl = QHBoxLayout()
            bl.addStretch()
            yes_b = QPushButton("Да")
            no_b = QPushButton("Нет")
            no_b.setDefault(True)
            bl.addWidget(yes_b)
            bl.addWidget(no_b)
            l.addLayout(bl)
            yes_b.clicked.connect(dlg.accept)
            no_b.clicked.connect(dlg.reject)
            if dlg.exec() == QDialog.Accepted:
                os.remove(json_path)
        return config


# ------------------------------------------------------------
# SQLite кэш задач
# ------------------------------------------------------------

_tasks_cache_lock = threading.Lock()


def _tasks_db_path():
    return os.path.join(_config_dir(), TASKS_DB)


def _init_tasks_db():
    path = _tasks_db_path()
    conn = sqlite3.connect(path, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS tasks_cache (id INTEGER PRIMARY KEY, data TEXT)")
    conn.commit()
    return conn


def save_tasks_cache(tasks: list[dict]):
    try:
        data = json.dumps(tasks, ensure_ascii=False, default=str)
        with _tasks_cache_lock:
            conn = _init_tasks_db()
            conn.execute("INSERT OR REPLACE INTO tasks_cache (id, data) VALUES (1, ?)", (data,))
            conn.commit()
            conn.close()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("save_tasks_cache: %s", e)


def load_tasks_cache() -> list[dict]:
    try:
        with _tasks_cache_lock:
            conn = _init_tasks_db()
            cur = conn.execute("SELECT data FROM tasks_cache WHERE id = 1")
            row = cur.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("load_tasks_cache: %s", e)
    return []


# ------------------------------------------------------------
# UI State — key-value store для сохранения состояния интерфейса
# ------------------------------------------------------------

_ui_state_lock = threading.Lock()


def _init_ui_db():
    path = _tasks_db_path()  # один файл, вторая таблица
    conn = sqlite3.connect(path, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS ui_state (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    return conn


def save_ui_state(key: str, value: str):
    try:
        with _ui_state_lock:
            conn = _init_ui_db()
            conn.execute("INSERT OR REPLACE INTO ui_state (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
            conn.close()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("save_ui_state(%s): %s", key, e)


def load_ui_state(key: str) -> str | None:
    try:
        with _ui_state_lock:
            conn = _init_ui_db()
            cur = conn.execute("SELECT value FROM ui_state WHERE key = ?", (key,))
            row = cur.fetchone()
            conn.close()
            return row[0] if row else None
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("load_ui_state(%s): %s", key, e)
        return None


# Dead code below (kept for reference):
# def load_all_ui_state() -> dict[str, str]: ...
# def delete_ui_state(key: str): ...
