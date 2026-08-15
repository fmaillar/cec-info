"""Data model and normalization helpers shared by cec2info."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

SPACE_RE = re.compile(r"[ \t\xa0]+")
MULTIBLANK_RE = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")


@dataclass
class Entry:
    title: str
    href: str | None
    depth: int
    parent: "Entry | None" = None
    children: list["Entry"] = field(default_factory=list)
    node: str = ""
    body: str = ""

    @property
    def up_node(self) -> str:
        return self.parent.node if self.parent else "Top"


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = SPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = MULTIBLANK_RE.sub("\n\n", text)
    return text.strip()


def flatten_entries(roots: Iterable[Entry]) -> Iterable[Entry]:
    for entry in roots:
        yield entry
        yield from flatten_entries(entry.children)


def assign_nodes(roots: list[Entry]) -> list[Entry]:
    entries = list(flatten_entries(roots))
    for i, entry in enumerate(entries, 1):
        entry.node = f"CEC-{i:04d}"
    return entries


def heading_key(text: str) -> str:
    """Normalize a title for comparing Vatican headings with the table of contents."""
    text = unicodedata.normalize("NFKD", html.unescape(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def entry_path_titles(entry: Entry) -> list[str]:
    titles: list[str] = []
    current: Entry | None = entry
    while current is not None:
        titles.append(current.title)
        current = current.parent
    titles.reverse()
    return titles
