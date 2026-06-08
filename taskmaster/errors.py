"""Common error types for TaskMaster."""

from __future__ import annotations

from typing import Any


class TaskMasterError(Exception):
    """Base error class for TaskMaster."""
    code: str = "internal_error"
    recoverable: bool = False

    def __init__(self, message: str, code: str | None = None, recoverable: bool | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        if recoverable is not None:
            self.recoverable = recoverable

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": str(self),
                "recoverable": self.recoverable
            }
        }


class CycleError(TaskMasterError):
    """Raised when a dependency cycle is detected."""
    code = "cycle"
    recoverable = True

    def __init__(self, cycle: list[str]) -> None:
        msg = f"Dependency cycle detected: {' -> '.join(cycle)}"
        super().__init__(msg)
        self.cycle = cycle


class InstallError(TaskMasterError):
    """Raised when skill installation fails."""
    code = "install_failed"
    recoverable = True


class InstallUsageError(InstallError):
    """Raised when ``install`` is called with invalid arguments (e.g. unknown skill name)."""
    code = "install_usage"
    recoverable = False


class EmbeddingError(TaskMasterError):
    """Raised when embedding operations fail."""
    code = "embedding_error"
    recoverable = True
