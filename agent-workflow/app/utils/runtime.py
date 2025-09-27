from datetime import datetime, timezone


class RuntimeState:
    """Tracks application start time and uptime information."""

    def __init__(self) -> None:
        self.started_at = datetime.now(timezone.utc)

    def uptime_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()


runtime_state = RuntimeState()
