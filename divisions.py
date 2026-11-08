from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Division:
    code: str
    name: str
    level: int
    type: str
    children: tuple["Division", ...] = field(default_factory=tuple)


def _parse(node: dict) -> Division:
    children = tuple(_parse(child) for child in node.get("children") or [])
    return Division(
        code=str(node.get("code") or ""),
        name=str(node.get("name") or ""),
        level=int(node.get("level") or 0),
        type=str(node.get("type") or ""),
        children=children,
    )


class DivisionIndex:
    def __init__(self, root: Division) -> None:
        self.root = root
        self._by_name: dict[str, Division] = {}
        self._walk(root)

    def _walk(self, node: Division) -> None:
        if node.name:
            self._by_name.setdefault(node.name, node)
        for child in node.children:
            self._walk(child)

    @classmethod
    def from_mca_payload(cls, payload: dict) -> "DivisionIndex":
        root_payload = payload.get("data", payload)
        return cls(_parse(root_payload))

    @classmethod
    def load(cls, path: Path) -> "DivisionIndex":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_mca_payload(payload)

    def districts(self) -> list[Division]:
        return [child for child in self.root.children if child.level == 3]

    def find(self, name: str) -> Division | None:
        return self._by_name.get(name)

    def adcode12(self, name: str) -> str | None:
        node = self.find(name)
        return node.code if node else None

    def adcode6(self, name: str) -> str | None:
        code = self.adcode12(name)
        return code[:6] if code else None
