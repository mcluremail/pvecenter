import json
import os
import base64

SALT_FILE = "nodes.salt"
ENC_FILE = "nodes.enc"
CONFIG_JSON = "nodes.json"

def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))

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

    def on_cancel():
        dialog.reject()

    ok_btn.clicked.connect(on_ok)
    cancel_btn.clicked.connect(on_cancel)
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
    base = _base_dir()
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
    base = _base_dir()
    enc_path = os.path.join(base, ENC_FILE)

    if os.path.exists(enc_path):
        password = _ask_password("enter")
        if password is None:
            return None
        cache_password(password)
        try:
            return _decrypt_from_file(enc_path, password)
        except Exception:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Ошибка",
                                 "Неверный пароль или повреждённые данные.")
            return None
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
            from PySide6.QtWidgets import QMessageBox
            _encrypt_to_file(config, password, enc_path)
            reply = QMessageBox.question(
                None, "Безопасность",
                "Токены зашифрованы в nodes.enc. Удалить nodes.json "
                "(исходный файл с токенами в открытом виде)?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                os.remove(json_path)
        return config
