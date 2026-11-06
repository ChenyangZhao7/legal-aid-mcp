from __future__ import annotations

import sys
import traceback
from typing import Callable, TypeVar

T = TypeVar("T")


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def error_dict(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def run_tool(fn: Callable[[], T]) -> T | dict:
    try:
        return fn()
    except ToolError as exc:
        return exc.to_dict()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return error_dict("INTERNAL", "工具内部错误，请稍后重试")
