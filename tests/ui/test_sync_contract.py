"""M0.1: статический контракт «sync-клиент не живёт в UI» (ROADMAP v3.0).

AST-скан pve_center/ui/**: UI-модули не импортируют и не вызывают
sync-клиент (proxmoxer, provider-фасад, create_provider, requests) —
весь сетевой I/O идёт через QRunnable-воркеры backend/ и ui/api/.
Регресс «sync-вызов в UI» = падение этого теста.

Allowlist швов:
- pve_center/ui/api/** — QRunnable-воркеры (metrics): вызовы
  create_provider легитимны только внутри run() в потоке пула;
- старт воркеров через QThreadPool.start (mainwindow, WorkerManager) —
  не sync-клиент и правилами не запрещается.
"""

import ast
import os
from pathlib import Path
from textwrap import dedent

import pytest

REPO = Path(__file__).resolve().parents[2]
UI_DIR = REPO / "pve_center" / "ui"

# QRunnable-воркеры слоя ui/api — единственный шов, где provider-фасад
# легитимен (использование только внутри run() в потоке пула).
ALLOWLIST_PREFIXES = ("pve_center.ui.api",)

# Импорт sync-клиента/транспорта в UI запрещён вне allowlist:
# - proxmoxer — sync-клиент напрямую;
# - requests — HTTP-транспорт вне воркеров;
# - (pve_center.)backend.pve — legacy-путь sync-клиента (защита от
#   рецидивов после возможных рефакторингов);
# - (pve_center.)provider — фасад PVE API (ProxmoxProvider, VmAPI, ...).
FORBIDDEN_IMPORT_PREFIXES = (
    "proxmoxer",
    "requests",
    "backend.pve",
    "pve_center.backend.pve",
    "provider",
    "pve_center.provider",
)

# Прямые вызовы sync-клиента по имени (вне allowlist).
FORBIDDEN_CALLS = frozenset({"ProxmoxAPI", "PVE", "create_provider"})


def _matches(name, prefixes):
    return any(name == p or name.startswith(p + ".") for p in prefixes)


def _is_allowed(modpath):
    return _matches(modpath, ALLOWLIST_PREFIXES)


def _resolve_import(module, level, modpath):
    """Абсолютное имя модуля для ImportFrom (учёт относительных точек)."""
    if not level:
        return module
    parts = modpath.split(".")
    base = parts[: len(parts) - level] if level <= len(parts) else []
    if module:
        return ".".join([*base, module])
    return ".".join(base)


def _scan_source(source, modpath):
    """Вернуть [(lineno, message)] нарушений контракта в исходнике."""
    issues = []
    allowed = _is_allowed(modpath)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not allowed and _matches(alias.name, FORBIDDEN_IMPORT_PREFIXES):
                    issues.append(
                        (node.lineno, f"импорт sync-клиента «{alias.name}» в UI")
                    )
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_import(node.module, node.level, modpath) or ""
            for alias in node.names:
                full = f"{resolved}.{alias.name}" if resolved else alias.name
                hit = _matches(resolved, FORBIDDEN_IMPORT_PREFIXES) or _matches(
                    full, FORBIDDEN_IMPORT_PREFIXES
                )
                if not allowed and (
                    hit
                    or (
                        (resolved == "pve_center.plugins" or resolved == "plugins")
                        and alias.name == "create_provider"
                    )
                ):
                    issues.append(
                        (node.lineno, f"импорт sync-клиента «{full}» в UI")
                    )
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            else:
                name = None
            if name in FORBIDDEN_CALLS and not allowed:
                issues.append((node.lineno, f"вызов sync-клиента «{name}()» в UI"))
    return issues


def _iter_ui_modules():
    for path in sorted(UI_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(REPO)
        modpath = str(rel.with_suffix("")).replace(os.sep, ".")
        source = path.read_text(encoding="utf-8")
        yield path, modpath, source


def _scan_engine(code, modpath="pve_center.ui.tabs"):
    return _scan_source(dedent(code), modpath)


class TestScannerEngine:
    """Движок сканера ловит все способы протащить sync-клиент в UI."""

    def test_proxmoxer_import_detected(self):
        issues = _scan_engine("import proxmoxer")
        assert len(issues) == 1
        assert "proxmoxer" in issues[0][1]

    def test_proxmoxer_submodule_import_detected(self):
        assert _scan_engine("from proxmoxer import ProxmoxAPI")

    def test_provider_import_detected(self):
        issues = _scan_engine("from pve_center.provider import ProxmoxProvider")
        assert len(issues) == 1
        assert "pve_center.provider" in issues[0][1]

    def test_relative_provider_import_detected(self):
        issues = _scan_engine(
            "from ...provider._session import build_requests_session",
            modpath="pve_center.ui.detail_panel.vm_tab",
        )
        assert len(issues) == 1

    def test_backend_pve_legacy_import_detected(self):
        assert _scan_engine("from pve_center.backend.pve import PVE")
        assert _scan_engine("from backend.pve import PVE")

    def test_create_provider_import_detected(self):
        issues = _scan_engine("from pve_center.plugins import create_provider")
        assert len(issues) == 1
        assert "create_provider" in issues[0][1]

    def test_relative_create_provider_import_detected(self):
        issues = _scan_engine(
            "from ...plugins import create_provider",
            modpath="pve_center.ui.detail_panel.vm_tab",
        )
        assert len(issues) == 1

    def test_requests_import_detected(self):
        assert _scan_engine("import requests")

    def test_proxmoxapi_call_detected(self):
        issues = _scan_engine("api = ProxmoxAPI('host')")
        assert len(issues) == 1
        assert "ProxmoxAPI()" in issues[0][1]

    def test_create_provider_call_detected(self):
        assert _scan_engine("provider = create_provider(cfg, timeout=10)")

    def test_clean_ui_module_passes(self):
        code = """
            from PySide6.QtCore import QObject, Signal
            from PySide6.QtWidgets import QWidget

            from ..i18n import tr


            class MyWidget(QWidget):
                clicked = Signal()

                def refresh(self):
                    self.setWindowTitle(tr("Refresh"))
        """
        assert _scan_engine(code) == []

    def test_allowlisted_worker_module_passes(self):
        code = """
            import requests

            from ...plugins import create_provider


            def make_session(cfg):
                return requests.Session()

            def provider(cfg):
                return create_provider(cfg, timeout=10)
        """
        assert _scan_engine(code, modpath="pve_center.ui.api.metrics") == []

    def test_from_import_nonmodule_alias_passes(self):
        code = """
            from pve_center.ui.i18n import tr
            from pve_center.domain.models import VmRow
        """
        assert _scan_engine(code) == []


class TestUITree:
    """Реальное дерево pve_center/ui/** чисто."""

    def test_ui_tree_has_no_sync_client(self):
        issues = []
        for path, modpath, source in _iter_ui_modules():
            for lineno, message in _scan_source(source, modpath):
                issues.append(f"{path}:{lineno}: {message}")
        assert not issues, "Контракт «sync-клиент не живёт в UI» нарушен:\n" + "\n".join(
            issues
        )

    def test_allowlist_modules_are_workers(self):
        """Шов ui/api/** остаётся allowlist'ом, только пока состоит из
        QRunnable-воркеров; появление там Qt-виджетов — повод пересмотреть."""
        api_dir = UI_DIR / "api"
        for path in sorted(api_dir.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            widget_bases = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
                for base in node.bases
                if isinstance(base, ast.Name)
                and base.id in {"QWidget", "QDialog", "QMainWindow"}
            ]
            assert not widget_bases, (
                f"{path}: Qt-виджет в allowlist-модуле воркеров ui/api — "
                "sync-клиент стал доступен виджету напрямую"
            )


@pytest.mark.parametrize(
    "modpath",
    ["pve_center.ui.api", "pve_center.ui.api.metrics", "pve_center.ui.api.future_worker"],
)
def test_allowlist_matches_submodules(modpath):
    assert _is_allowed(modpath)


def test_non_allowlist_modules_are_checked():
    assert not _is_allowed("pve_center.ui.mainwindow")
    assert not _is_allowed("pve_center.ui.tree_panel")
    assert not _is_allowed("pve_center.ui.detail_panel")
