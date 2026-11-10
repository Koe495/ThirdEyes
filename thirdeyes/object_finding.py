"""Module 5 placeholder: requested object, direction and optional distance."""
from thirdeyes.contracts import FrameBundle, PlaceholderResult


class ObjectFinder:
    def process(self, frames: FrameBundle, target: str = "") -> PlaceholderResult:
        return PlaceholderResult("object_finding")
