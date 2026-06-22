import json
import os
import sys
import base64
import sqlite3
import threading
import logging

logger = logging.getLogger(__name__)

CONFIG_DB = "config.sqlite"
_OLD_DB = "tasks_cache.sqlite"
_OLD_ENC = "nodes.enc"
_OLD_SALT = "nodes.salt"
_OLD_JSON = "nodes.json"

_KEYRING_SERVICE = "pve-center"
_DB_LOCK = threading.Lock()

# ── paths ──────────────────────────────────────────────────────

def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _config_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        d = os.path.join(base, "pve-center")
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        d = os.path.join(home, "Library", "Application Support", "pve-center")
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        d = os.path.join(xdg, "pve-center")
    os.makedirs(d, exist_ok=True)
    return d


def _migrate_file(name):
    src = os.path.join(_base_dir(), name)
    dst = os.path.join(_config_dir(), name)
    if os.path.exists(src) and not os.path.exists(dst):
        import shutil
        shutil.move(src, dst)


def _db_path():
    return os.path.join(_config_dir(), CONFIG_DB)


# ── keyring ────────────────────────────────────────────────────

_keyring_available: bool | None = None


def _get_keyring():
    global _keyring_available
    if _keyring_available is False:
        return None
    try:
        import keyring as _kr
        _kr.get_keyring()
        _keyring_available = True
        return _kr
    except Exception:
        _keyring_available = False
        return None


def _keyring_key(name: str) -> str:
    return f"node:{name}"


def _save_token(name: str, token_value: str):
    kr = _get_keyring()
    if kr is None:
        logger.warning("keyring not available, token for %s not saved", name)
        return
    try:
        kr.set_password(_KEYRING_SERVICE, _keyring_key(name), token_value)
    except Exception as e:
        logger.error("keyring set_password failed for %s: %s", name, e)


def _load_token(name: str) -> str | None:
    kr = _get_keyring()
    if kr is None:
        return None
    try:
        return kr.get_password(_KEYRING_SERVICE, _keyring_key(name))
    except Exception as e:
        logger.error("keyring get_password failed for %s: %s", name, e)
        return None


def _delete_token(name: str):
    kr = _get_keyring()
    if kr is None:
        return
    try:
        kr.delete_password(_KEYRING_SERVICE, _keyring_key(name))
    except Exception:
        pass


# ── sqlite init ─────────────────────────────────────────────────

def _init_db():
    path = _db_path()
    conn = sqlite3.connect(path, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            name TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)
    conn.execute("CREATE TABLE IF NOT EXISTS tasks_cache (id INTEGER PRIMARY KEY, data TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS ui_state (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS translations (
            lang  TEXT NOT NULL,
            msgid TEXT NOT NULL,
            msgstr TEXT NOT NULL,
            PRIMARY KEY (lang, msgid)
        )
    """)
    conn.commit()
    return conn


def _migrate_old_db():
    """tasks_cache.sqlite → config.sqlite"""
    old = os.path.join(_config_dir(), _OLD_DB)
    new = _db_path()
    if not os.path.exists(old):
        return
    if os.path.exists(new):
        return
    try:
        import shutil
        shutil.move(old, new)
        logger.info("migrated %s → %s", _OLD_DB, CONFIG_DB)
    except Exception as e:
        logger.warning("db migration failed: %s", e)


# ── nodes config (public API) ───────────────────────────────────

_NODE_FIELDS = ("name", "host", "user", "token_name", "cluster", "cluster_rep", "skip")


def load_config() -> list[dict]:
    """Load nodes from sqlite, attach token_value from keyring.
    Returns list of node dicts (never None — no password dialog needed)."""
    for fn in (_OLD_DB,):
        _migrate_file(fn)
    _migrate_old_db()

    with _DB_LOCK:
        conn = _init_db()
        cur = conn.execute("SELECT data FROM nodes")
        rows = cur.fetchall()
        conn.close()

    config = []
    for (raw,) in rows:
        try:
            cfg = json.loads(raw)
        except Exception:
            continue
        name = cfg.get("name", "")
        if name:
            token = _load_token(name)
            cfg["token_value"] = token or ""
        config.append(cfg)
    return config


def save_config(config_list: list[dict]):
    """Save nodes to sqlite, token_value to keyring."""
    with _DB_LOCK:
        conn = _init_db()
        # replace all
        conn.execute("DELETE FROM nodes")
        for cfg in config_list:
            name = cfg.get("name", "")
            if not name:
                continue
            # store everything except token_value
            store = {k: v for k, v in cfg.items() if k != "token_value"}
            conn.execute("INSERT OR REPLACE INTO nodes (name, data) VALUES (?, ?)",
                         (name, json.dumps(store, ensure_ascii=False)))
            # token_value → keyring
            token_value = cfg.get("token_value")
            if token_value:
                _save_token(name, token_value)
        conn.commit()
        conn.close()


def delete_node_tokens(names: list[str]):
    """Delete token secrets from keyring for given node names."""
    for name in names:
        _delete_token(name)


# ── encrypted bundle (export/import) ────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def _encrypt_bundle(data: list[dict], password: str) -> bytes:
    from cryptography.fernet import Fernet
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    plain = json.dumps(data, ensure_ascii=False, indent=2).encode()
    token = Fernet(key).encrypt(plain)
    return salt + token


def _decrypt_bundle(raw: bytes, password: str) -> list[dict]:
    from cryptography.fernet import Fernet
    salt, token = raw[:16], raw[16:]
    key = _derive_key(password, salt)
    plain = Fernet(key).decrypt(token)
    return json.loads(plain.decode())


def _ask_password(mode="enter"):
    """Show password input dialog for export/import bundle.
    mode='enter' — existing password, mode='set' — set new password.
    Returns password or None (cancelled)."""
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                   QLineEdit, QPushButton)
    from .ui.i18n import tr
    from .ui.theme import Color
    dialog = QDialog()
    dialog.setWindowTitle(tr("PVE Center — Password"))
    dialog.setMinimumSize(380, 160)
    layout = QVBoxLayout(dialog)

    if mode == "set":
        layout.addWidget(QLabel(tr("Set password to encrypt configuration:")))
    else:
        layout.addWidget(QLabel(tr("Enter password:")))

    pwd_input = QLineEdit()
    pwd_input.setEchoMode(QLineEdit.Password)
    layout.addWidget(pwd_input)

    if mode == "set":
        layout.addWidget(QLabel(tr("Repeat password:")))
        confirm_input = QLineEdit()
        confirm_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(confirm_input)
    else:
        confirm_input = None

    error_label = QLabel("")
    error_label.setStyleSheet(f"color: {Color.GRAY_400};")
    layout.addWidget(error_label)

    btn_layout = QHBoxLayout()
    ok_btn = QPushButton(tr("OK"))
    cancel_btn = QPushButton(tr("Cancel"))
    btn_layout.addStretch()
    btn_layout.addWidget(ok_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)

    result = [None]

    def on_ok():
        pwd = pwd_input.text()
        if not pwd:
            error_label.setText(tr("Password cannot be empty"))
            return
        if confirm_input is not None and pwd != confirm_input.text():
            error_label.setText(tr("Passwords do not match"))
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


def export_config(dest_path: str) -> bool:
    """Export all nodes (with token_value) as encrypted bundle."""
    config = load_config()
    if not config:
        return False
    password = _ask_password("set")
    if password is None:
        return False
    raw = _encrypt_bundle(config, password)
    with open(dest_path, "wb") as f:
        f.write(raw)
    return True


def import_config(src_path: str, merge: bool = True) -> list[dict] | None:
    """Import encrypted bundle, merge with existing config."""
    from PySide6.QtWidgets import QMessageBox
    from .ui.i18n import tr
    if not os.path.exists(src_path):
        return None

    while True:
        password = _ask_password("enter")
        if password is None:
            return None
        try:
            imported = _decrypt_bundle(open(src_path, "rb").read(), password)
            break
        except Exception:
            QMessageBox.warning(None, tr("Error"),
                                 tr("Wrong password. Try again."))

    if not merge:
        save_config(imported)
        return imported

    current = load_config()
    current_map = {(c.get("host"), c.get("user")): c for c in current}
    for imp_cfg in imported:
        key = (imp_cfg.get("host"), imp_cfg.get("user"))
        current_map[key] = imp_cfg
    merged = list(current_map.values())
    save_config(merged)
    return merged


# ── tasks cache ─────────────────────────────────────────────────

_tasks_cache_lock = threading.Lock()


def save_tasks_cache(tasks: list[dict]):
    try:
        data = json.dumps(tasks, ensure_ascii=False, default=str)
        with _tasks_cache_lock:
            conn = _init_db()
            conn.execute("INSERT OR REPLACE INTO tasks_cache (id, data) VALUES (1, ?)", (data,))
            conn.commit()
            conn.close()
    except Exception as e:
        logger.warning("save_tasks_cache: %s", e)


def load_tasks_cache() -> list[dict]:
    try:
        with _tasks_cache_lock:
            conn = _init_db()
            cur = conn.execute("SELECT data FROM tasks_cache WHERE id = 1")
            row = cur.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
    except Exception as e:
        logger.warning("load_tasks_cache: %s", e)
    return []


# ── ui state ────────────────────────────────────────────────────

_ui_state_lock = threading.Lock()


def save_ui_state(key: str, value: str):
    try:
        with _ui_state_lock:
            conn = _init_db()
            conn.execute("INSERT OR REPLACE INTO ui_state (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
            conn.close()
    except Exception as e:
        logger.warning("save_ui_state(%s): %s", key, e)


def load_ui_state(key: str) -> str | None:
    try:
        with _ui_state_lock:
            conn = _init_db()
            cur = conn.execute("SELECT value FROM ui_state WHERE key = ?", (key,))
            row = cur.fetchone()
            conn.close()
            return row[0] if row else None
    except Exception as e:
        logger.warning("load_ui_state(%s): %s", key, e)
        return None


# ── translations ────────────────────────────────────────────────

_translations_lock = _ui_state_lock


def seed_translations(lang: str, translations: dict[str, str], version: int = 0):
    try:
        with _translations_lock:
            conn = _init_db()
            if version:
                cur = conn.execute(
                    "SELECT value FROM ui_state WHERE key = 'i18n_version'"
                )
                row = cur.fetchone()
                stored = int(row[0]) if row else 0
                if stored != version:
                    conn.execute("DELETE FROM translations")
                    conn.execute(
                        "INSERT OR REPLACE INTO ui_state (key, value) VALUES ('i18n_version', ?)",
                        (str(version),),
                    )
            inserted = 0
            for msgid, msgstr in translations.items():
                cur = conn.execute(
                    "SELECT 1 FROM translations WHERE lang = ? AND msgid = ?",
                    (lang, msgid),
                )
                if cur.fetchone() is None:
                    conn.execute(
                        "INSERT INTO translations (lang, msgid, msgstr) VALUES (?, ?, ?)",
                        (lang, msgid, msgstr),
                    )
                    inserted += 1
            conn.commit()
            conn.close()
            if inserted:
                logger.info("Seeded %d translations for %s", inserted, lang)
    except Exception as e:
        logger.warning("seed_translations(%s): %s", lang, e)