from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CaptionSeg:
    start: float
    end: float
    text: str
