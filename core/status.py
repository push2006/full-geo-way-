"""In-memory collector status for the dashboard."""
from datetime import datetime, timezone
from threading import Lock

_lock = Lock()
_state = {
    "running": False,
    "last_cycle_at": None,
    "last_cycle_num": 0,
    "last_changed": 0,
    "last_errors": 0,
    "last_duration_sec": 0,
    "message": "starting",
}


def set_running(running: bool):
    with _lock:
        _state["running"] = bool(running)


def record_cycle(cycle_num: int = 0, changed: int = 0, errors: int = 0, duration_sec: float = 0, message: str = "ok"):
    with _lock:
        _state["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
        _state["last_cycle_num"] = int(cycle_num or 0)
        _state["last_changed"] = int(changed or 0)
        _state["last_errors"] = int(errors or 0)
        _state["last_duration_sec"] = round(float(duration_sec or 0), 2)
        _state["message"] = message or "ok"
        _state["running"] = True


def get_status() -> dict:
    with _lock:
        return dict(_state)
