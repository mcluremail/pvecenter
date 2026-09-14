"""M0.5: PVE compat matrix — версии нод и capabilities.

Ядро не хардкодит версии PVE: потребители (M4 — rrddata/version
расхождения, M5 — migrate/HA nuances) спрашивают ``supports(feature)``
у провайдера. Матрица ``PVE_FEATURES`` — минимальные версии для
известных фич; расширять через :func:`register_feature`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PveVersion:
    major: int
    minor: int
    patch: int = 0

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __str__(self) -> str:
        return (
            f"{self.major}.{self.minor}"
            if self.patch == 0
            else f"{self.major}.{self.minor}.{self.patch}"
        )


# feature -> минимальная версия (major, minor). Поддерживаемая матрица:
# 7.x/8.x/9.x; старше 7.x — best effort без гарантий.
PVE_FEATURES: dict[str, tuple[int, int]] = {
    "version": (6, 2),  # GET /nodes/{node}/version
    "rrddata": (6, 0),  # GET .../rrddata — метрики нод и гостей
    "guest_tags": (8, 0),  # теги ВМ/контейнеров (API + UI)
}


def register_feature(name: str, major: int, minor: int) -> None:
    """Добавить фичу в матрицу (для M4/M5 и плагинов)."""
    PVE_FEATURES[name] = (int(major), int(minor))


def _parse_dotted(part: str) -> PveVersion | None:
    """'8.2.4' / '8.2' / '8' / '7.4-3' (minor-patch) → PveVersion; иначе None."""
    nums: list[int] = []
    for c in part.split("."):
        if "-" in c:
            head, tail = c.split("-", 1)
            if not (head.isdigit() and tail.isdigit()):
                return None
            nums.append(int(head))
            nums.append(int(tail))
        elif c.isdigit():
            nums.append(int(c))
        else:
            return None
    if not 1 <= len(nums) <= 3:
        return None
    while len(nums) < 3:
        nums.append(0)
    return PveVersion(*nums)


def parse_pve_version(raw: str | None) -> PveVersion | None:
    """Разобрать pveversion: ``pve-manager/8.2.4/1ac2f4b`` или ``8.2.4``.

    Хэш-часть (``1ac2f4b``) и мусор отбрасываются; без версии → None.
    """
    if not raw:
        return None
    text = str(raw).strip()
    if "/" in text:
        for part in text.split("/"):
            v = _parse_dotted(part)
            if v is not None:
                return v
        return None
    return _parse_dotted(text)


def supports(version: PveVersion | None, feature: str) -> bool:
    """Поддерживает ли версия фичу. Неизвестная версия/фича → False
    (консервативно: вызывающий код делает фоллбэк)."""
    min_version = PVE_FEATURES.get(feature)
    if version is None or min_version is None:
        return False
    return version.as_tuple()[:2] >= min_version
