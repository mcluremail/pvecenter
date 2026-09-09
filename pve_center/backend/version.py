"""GitHub release version check."""

import logging

from PySide6.QtCore import QObject, QRunnable, Signal

from .core import _safe_emit

logger = logging.getLogger(__name__)

_GITHUB_API_LATEST = "https://api.github.com/repos/mcluremail/pvecenter/releases/latest"
class VersionCheckSignals(QObject):
    update_available = Signal(str, str)  # latest_version, release_url
    finished = Signal()
class VersionCheckWorker(QRunnable):
    """Check GitHub releases for a newer version of PVE Center."""
    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version
        self.signals = VersionCheckSignals()

    @staticmethod
    def _parse_version(v):
        parts = []
        for p in v.lstrip("v").split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        return parts

    def run(self):
        try:
            import requests
            resp = requests.get(_GITHUB_API_LATEST, timeout=10,
                                headers={"Accept": "application/vnd.github+json"})
            resp.raise_for_status()
            data = resp.json()
            latest = data.get("tag_name", "").strip()
            if not latest:
                return
            release_url = data.get("html_url", "")
            latest_norm = latest.lstrip("v")
            current_norm = self.current_version.lstrip("v")
            if self._parse_version(latest_norm) > self._parse_version(current_norm):
                _safe_emit(self.signals.update_available, latest_norm, release_url)
        except Exception as e:
            logger.debug("version check error: %s", e)
        finally:
            _safe_emit(self.signals.finished)
