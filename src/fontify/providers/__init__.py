"""Creative artwork providers. The deterministic compiler never imports these."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class DesignRequest:
    prompt: str
    model: str = "recraftv4_1_vector"
    size: str = "1:1"
    style_id: str | None = None
    style_reference_urls: tuple[str, ...] = ()
    seed: int | None = None


@dataclass(frozen=True)
class Artwork:
    svg: bytes
    provenance: dict = field(default_factory=dict)


class DesignProvider(Protocol):
    def generate(
        self, request: DesignRequest, *, allow_paid: bool = False
    ) -> Artwork: ...


class LocalSVGProvider:
    """A supplied vector is a complete, free design-provider implementation."""

    def __init__(self, path):
        from pathlib import Path

        self.path = Path(path)

    def generate(self, request=None, *, allow_paid=False):
        import hashlib

        svg = self.path.read_bytes()
        return Artwork(
            svg,
            {
                "provider": "local",
                "source_name": self.path.name,
                "sha256": hashlib.sha256(svg).hexdigest(),
            },
        )
