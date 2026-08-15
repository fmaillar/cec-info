"""Parsing of the IntraText table of contents and HTML pages."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup, NavigableString, Tag

from cec2info_model import (
    Entry,
    entry_path_titles,
    flatten_entries,
    normalize_text,
)
from cec2info_network import clean_page_url, fetch
from cec2info_output import body_to_texinfo


def eprint(*args: object) -> None:
    import sys

    print(*args, file=sys.stderr)


def direct_li_title(li: Tag) -> str:
    clone = BeautifulSoup(str(li), "html.parser")
    root = clone.find("li")
    if not isinstance(root, Tag):
        return ""
    for nested in root.find_all(["ul", "ol"]):
        nested.decompose()
    return normalize_text(root.get_text(" ", strip=True))


def first_direct_link(li: Tag) -> str | None:
    for child in li.children:
        if isinstance(child, Tag) and child.name == "a" and child.get("href"):
            return str(child["href"])
        if isinstance(child, Tag) and child.name not in {"ul", "ol"}:
            link = child.find("a", href=True)
            if isinstance(link, Tag):
                return str(link["href"])
    return None


def parse_index(data: bytes) -> list[Entry]:
    soup = BeautifulSoup(data, "html.parser")
    lists = soup.find_all(["ul", "ol"])
    if not lists:
        raise RuntimeError("Aucune liste trouvée dans le sommaire Vatican.")

    root_list = max(lists, key=lambda tag: len(tag.find_all("li")))
    roots: list[Entry] = []

    def walk(list_tag: Tag, parent: Entry | None, depth: int) -> None:
        direct_items = list(list_tag.find_all("li", recursive=False))
        # Some invalid ``ul > ul > li`` wrappers do not introduce a logical
        # level, so traverse them using the current parent.
        if not direct_items:
            for nested in list_tag.find_all(["ul", "ol"], recursive=False):
                walk(nested, parent, depth)
            return

        for item in direct_items:
            title = direct_li_title(item)
            if not title:
                for nested in item.find_all(["ul", "ol"], recursive=False):
                    walk(nested, parent, depth)
                continue
            entry = Entry(
                title=title,
                href=first_direct_link(item),
                depth=depth,
                parent=parent,
            )
            if parent is None:
                roots.append(entry)
            else:
                parent.children.append(entry)
            for nested in item.find_all(["ul", "ol"], recursive=False):
                walk(nested, entry, depth + 1)

    walk(root_list, None, 1)
    if len(list(flatten_entries(roots))) < 20:
        raise RuntimeError(
            "Le sommaire détecté semble anormalement petit ; "
            "la structure HTML du Vatican a peut-être changé."
        )
    return roots


def text_regions_from_html(data: bytes) -> list[str]:
    if not data.strip():
        return []
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    marker = "<<<CEC-HR>>>"
    for horizontal_rule in soup.find_all("hr"):
        horizontal_rule.replace_with(NavigableString(f"\n\n{marker}\n\n"))
    for line_break in soup.find_all("br"):
        line_break.replace_with(NavigableString("\n"))
    for tag in soup.find_all(
        [
            "p",
            "div",
            "li",
            "blockquote",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "tr",
            "center",
        ]
    ):
        tag.insert_before(NavigableString("\n"))
        tag.insert_after(NavigableString("\n"))

    body = soup.body or soup
    parts = body.get_text(" ", strip=False).split(marker)
    return [normalize_text(part) for part in parts if normalize_text(part)]


def boilerplate_penalty(text: str) -> int:
    folded = text.casefold()
    penalty = 0
    for phrase in (
        "intratext - lecture du texte",
        "copyright © libreria editrice vaticana",
        "précédent",
        "suivant",
        "aide",
        "le saint-siège",
    ):
        if phrase in folded:
            penalty += 5000
    return penalty


def content_score(text: str) -> int:
    numbered = len(re.findall(r"(?m)^\s*\d{1,4}\s+", text))
    return len(text) + numbered * 1000 - boilerplate_penalty(text)


def extract_main_text(data: bytes) -> str:
    regions = text_regions_from_html(data)
    if not regions:
        return ""
    candidate = max(regions, key=content_score)

    lines: list[str] = []
    for line in candidate.splitlines():
        stripped = line.strip()
        folded = stripped.casefold()
        if not stripped:
            lines.append("")
            continue
        if folded in {
            "catéchisme de l'église catholique",
            "intratext - lecture du texte",
            "précédent - suivant",
            "précédent",
            "suivant",
        }:
            continue
        if folded.startswith("copyright © libreria editrice vaticana"):
            continue
        lines.append(stripped)
    return normalize_text("\n".join(lines))


def strip_leading_duplicate_title(text: str, title: str) -> str:
    text = text.lstrip()
    target = normalize_text(title).casefold()
    lines = text.splitlines()
    for count in range(1, min(5, len(lines)) + 1):
        candidate = normalize_text(" ".join(lines[:count])).casefold()
        if candidate == target:
            return "\n".join(lines[count:]).lstrip()
        if not target.startswith(candidate):
            break
    return text


def next_page_url(data: bytes, current_url: str) -> str | None:
    """Return the reading page referenced by IntraText's ``Suivant`` link."""
    soup = BeautifulSoup(data, "html.parser")
    for link in soup.find_all("a", href=True):
        if normalize_text(link.get_text(" ", strip=True)).casefold() == "suivant":
            return clean_page_url(current_url, str(link["href"]))
    return None


def append_page_body(entry: Entry, data: bytes) -> None:
    text = extract_main_text(data)
    text = strip_leading_duplicate_title(text, entry.title)
    body = body_to_texinfo(text, entry_path_titles(entry))
    if body:
        entry.body = "\n\n".join(part for part in (entry.body, body) if part)


def downloadable_entries(
    entries: Iterable[Entry],
    index_url: str,
) -> list[tuple[Entry, str]]:
    """Return a single owning entry for each linked page."""
    result: list[tuple[Entry, str]] = []
    seen_urls: set[str] = set()
    for entry in entries:
        url = clean_page_url(index_url, entry.href) if entry.href else None
        if url is not None and url not in seen_urls:
            result.append((entry, url))
            seen_urls.add(url)
    return result


def download_linked_pages(
    downloadable: list[tuple[Entry, str]],
    cache_dir: Path,
    refresh: bool,
    delay: float,
) -> dict[str, bytes]:
    page_data: dict[str, bytes] = {}
    total = len(downloadable)
    for index, (entry, url) in enumerate(downloadable, 1):
        eprint(f"[{index:3d}/{total}] {entry.title}")
        data = fetch(url, cache_dir, refresh=refresh, delay=delay)
        page_data[url] = data
        append_page_body(entry, data)
    return page_data


def discover_orphan_chain(
    start_url: str,
    start_data: bytes,
    known_urls: set[str],
    assigned_orphans: set[str],
    cache_dir: Path,
    refresh: bool,
    delay: float,
) -> tuple[list[tuple[str, bytes]], str | None]:
    """Follow ``Suivant`` links until reaching a known page or a cycle."""
    current_url = start_url
    current_data = start_data
    chain: list[tuple[str, bytes]] = []
    seen_chain = {start_url}

    while True:
        following = next_page_url(current_data, current_url)
        if (
            following is None
            or following in seen_chain
            or following in known_urls
            or following in assigned_orphans
        ):
            return chain, following

        eprint(f"[page orpheline] {following}")
        orphan_data = fetch(following, cache_dir, refresh=refresh, delay=delay)
        chain.append((following, orphan_data))
        seen_chain.add(following)
        current_url, current_data = following, orphan_data


def assign_orphan_chain(
    entries: list[Entry],
    entry_positions: dict[int, int],
    url_entries: dict[str, Entry],
    source_entry: Entry,
    orphan_chain: list[tuple[str, bytes]],
    following_url: str | None,
) -> None:
    next_known_entry = url_entries.get(following_url) if following_url else None
    source_position = entry_positions[id(source_entry)]
    next_position = (
        entry_positions[id(next_known_entry)]
        if next_known_entry is not None
        else len(entries)
    )
    empty_entries = [
        entry
        for entry in entries[source_position + 1 : next_position]
        if entry.href is None and not entry.body
    ]

    for _, orphan_data in orphan_chain:
        target = empty_entries.pop(0) if empty_entries else source_entry
        append_page_body(target, orphan_data)


def load_bodies(
    roots: list[Entry],
    index_url: str,
    cache_dir: Path,
    refresh: bool,
    delay: float,
) -> int:
    entries = list(flatten_entries(roots))
    downloadable = downloadable_entries(entries, index_url)
    entry_positions = {id(entry): index for index, entry in enumerate(entries)}
    url_entries = {url: entry for entry, url in downloadable}
    known_urls = set(url_entries)
    page_data = download_linked_pages(downloadable, cache_dir, refresh, delay)

    orphan_urls: set[str] = set()
    for source_entry, source_url in downloadable:
        orphan_chain, following = discover_orphan_chain(
            source_url,
            page_data[source_url],
            known_urls,
            orphan_urls,
            cache_dir,
            refresh,
            delay,
        )
        if not orphan_chain:
            continue
        orphan_urls.update(url for url, _ in orphan_chain)
        assign_orphan_chain(
            entries,
            entry_positions,
            url_entries,
            source_entry,
            orphan_chain,
            following,
        )
    return len(orphan_urls)
