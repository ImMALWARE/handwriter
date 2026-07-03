from json import load, dump
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self, Any

@dataclass(slots=True)
class FontMetadata:
    baseline: float = 0.0
    cap_height: float = 8.0
    units: str = "mm"

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline,
            "cap_height": self.cap_height,
            "units": self.units
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            baseline=float(data.get("baseline", 0.0)),
            cap_height=float(data.get("cap_height", 8.0)),
            units=str(data.get("units", "mm"))
        )

@dataclass(slots=True)
class GlyphVariant:
    paths: list[str] = field(default_factory=list)
    start: tuple[float, float] | None = None
    end: tuple[float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "paths": self.paths,
        }
        if self.start is not None:
            d["start"] = list(self.start)
        if self.end is not None:
            d["end"] = list(self.end)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        start_data = data.get("start")
        end_data = data.get("end")
        return cls(
            paths=list(data.get("paths", [])),
            start=(float(start_data[0]), float(start_data[1])) if start_data and len(start_data) >= 2 else None,
            end=(float(end_data[0]), float(end_data[1])) if end_data and len(end_data) >= 2 else None
        )

@dataclass(slots=True)
class HFont:
    version: int = 1
    metadata: FontMetadata = field(default_factory=FontMetadata)
    glyphs: dict[str, list[GlyphVariant]] = field(default_factory=dict)
    path: Path | None = field(default=None, compare=False, repr=False)

    @property
    def name(self) -> str:
        return self.path.stem if self.path else "Untitled Font"

    def clone(self) -> 'HFont':
        cloned = self.__class__.from_dict(self.to_dict())
        cloned.path = self.path
        return cloned

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "metadata": self.metadata.to_dict(),
            "glyphs": {
                char: [v.to_dict() for v in variants]
                for char, variants in self.glyphs.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        glyphs = {
            char: [GlyphVariant.from_dict(v) for v in variants_data]
            for char, variants_data in data.get("glyphs", {}).items()
        }

        return cls(
            version=int(data.get("version", 1)),
            metadata=FontMetadata.from_dict(data.get("metadata", {})),
            glyphs=glyphs
        )

    @classmethod
    def load(cls, path: str | Path) -> Self:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Font file not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = load(f)
        font = cls.from_dict(data)
        font.path = p
        return font

    def save(self, path: str | Path | None = None) -> None:
        p = Path(path) if path else self.path
        if p is None:
            raise ValueError("No path specified for saving")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        self.path = p

    def get_variants(self, char: str) -> list[GlyphVariant]:
        return self.glyphs.get(char, [])

    def add_variant(self, char: str, variant: GlyphVariant) -> None:
        self.glyphs.setdefault(char, []).append(variant)

    def remove_variant(self, char: str, index: int) -> None:
        variants = self.glyphs.get(char)
        if variants:
            try:
                variants.pop(index)
                if not variants:
                    del self.glyphs[char]
            except IndexError:
                pass

    def insert_variant(self, char: str, index: int, variant: GlyphVariant) -> None:
        self.glyphs.setdefault(char, []).insert(index, variant)

    def remove_char(self, char: str) -> None:
        self.glyphs.pop(char, None)

    def set_variants(self, char: str, variants: list[GlyphVariant]) -> None:
        self.glyphs[char] = variants

    def has_char(self, char: str) -> bool:
        return bool(self.glyphs.get(char))

    @property
    def chars(self) -> list[str]:
        return sorted(self.glyphs.keys())

    @property
    def char_count(self) -> int:
        return len(self.glyphs)