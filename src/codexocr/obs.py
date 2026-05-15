from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class BrowserSourceConfig:
    name: str
    url: str
    width: int
    height: int
    transparent: bool
    shutdown_when_invisible: bool
    refresh_when_active: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_browser_source_config(
    host: str = "127.0.0.1",
    port: int = 8765,
    name: str = "CodexOCR Card Price Overlay",
    width: int = 1920,
    height: int = 1080,
) -> BrowserSourceConfig:
    return BrowserSourceConfig(
        name=name,
        url=f"http://{host}:{port}/overlay",
        width=width,
        height=height,
        transparent=True,
        shutdown_when_invisible=False,
        refresh_when_active=True,
    )
