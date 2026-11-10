"""Module 6 placeholder: modes, warning priority, deduplication and speech."""
from thirdeyes.contracts import PlaceholderResult


class CoordinatorAudio:
    default_mode = "obstacle_warning"

    def process(self, results: list[PlaceholderResult]) -> PlaceholderResult:
        return PlaceholderResult("coordinator_audio", message="Chua co am thanh/canh bao.")
