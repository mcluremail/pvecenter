"""Mixin providing dict-compatible ``.get()`` and ``__getitem__`` on frozen dataclasses.

Allows domain objects to be passed anywhere a PVE dict was expected,
enabling gradual migration without touching every ``.get("field")`` call.
"""

from __future__ import annotations


class DictCompat:
    """Mixin that makes a frozen dataclass behave like a read-only dict.

    Subclasses must define ``_FIELD_MAP`` — a dict mapping PVE dict keys
    to domain attribute names or computed-property names.
    """

    _FIELD_MAP: dict[str, str] = {}

    def get(self, key: str, default=None):
        """Dict-compatible field access.

        Maps PVE API field names to domain attributes.
        Falls back to ``getattr(self, key, default)`` for unmapped keys.
        """
        attr = self._FIELD_MAP.get(key, key)
        val = getattr(self, attr, None)
        if val is None:
            return default
        return val

    def __getitem__(self, key: str):
        """Square-bracket access (``obj["field"]``)."""
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __contains__(self, key: str) -> bool:
        """``"field" in obj`` — checks if the attribute exists."""
        attr = self._FIELD_MAP.get(key, key)
        return hasattr(self, attr)

    def keys(self):
        """Return PVE dict keys for ``**`` unpacking support."""
        return list(self._FIELD_MAP.keys())
