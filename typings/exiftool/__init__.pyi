from types import TracebackType
from typing import Any

class ExifToolHelper:
    def __enter__(self) -> ExifToolHelper: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...
    def get_metadata(
        self, filename: str | list[str], params: list[str] | None = None
    ) -> list[dict[str, Any]]: ...
