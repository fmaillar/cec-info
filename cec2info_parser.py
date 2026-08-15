"""Parsing of the IntraText table of contents and HTML pages."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup, NavigableString, Tag

from cec2info_language import DEFAULT_LANGUAGE, get_language_profile
from cec2info_model import (
    Entry,
    entry_path_titles,
    flatten_entries,
    normalize_text,
)
from cec2info_network import clean_page_url, fetch
from cec2info_output import body_to_texinfo, is_biblical_reference


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


def _legacy_entry_level(title: str, language: str) -> int | None:
    profile = get_language_profile(language)
    patterns = (
        profile.part_pattern,
        profile.section_pattern,
        profile.chapter_pattern,
        profile.article_pattern,
        profile.paragraph_pattern,
    )
    for level, pattern in enumerate(patterns, 1):
        if re.search(pattern, title, re.IGNORECASE):
            return level
    if normalize_text(title).casefold() in profile.unnumbered_titles:
        return 1
    return None


def parse_legacy_index(
    data: bytes,
    language: str,
    index_url: str,
) -> list[Entry]:
    """Build a hierarchy from the Vatican's flat, pre-IntraText indexes."""
    soup = BeautifulSoup(data, "html.parser")
    roots: list[Entry] = []
    stack: list[Entry] = []
    seen: set[tuple[str, str]] = set()
    previous_page: str | None = None
    current_structural_level = 0

    for link in soup.find_all("a", href=True):
        title = normalize_text(link.get_text(" ", strip=True))
        href = str(link["href"])
        page_url = clean_page_url(index_url, href, language)
        if not title or page_url is None:
            continue
        key = (title.casefold(), href.casefold())
        if key in seen:
            continue
        seen.add(key)

        semantic_level = _legacy_entry_level(title, language)
        if semantic_level is not None:
            level = semantic_level
            current_structural_level = level
        elif page_url != previous_page:
            level = 1
            current_structural_level = 1
        else:
            level = min(current_structural_level + 1, 5)

        parent = stack[level - 2] if level > 1 and len(stack) >= level - 1 else None
        entry = Entry(title=title, href=href, depth=level, parent=parent)
        if parent is None:
            roots.append(entry)
        else:
            parent.children.append(entry)
        stack[level - 1 :] = [entry]
        previous_page = page_url

    if len(list(flatten_entries(roots))) < 20:
        raise RuntimeError(
            "The detected table of contents looks unusually small; "
            "the Vatican HTML structure may have changed."
        )
    return roots


def parse_index(
    data: bytes,
    language: str = DEFAULT_LANGUAGE,
    index_url: str | None = None,
) -> list[Entry]:
    profile = get_language_profile(language)
    if profile.source_format == "legacy":
        return parse_legacy_index(data, language, index_url or profile.index_url)

    soup = BeautifulSoup(data, "html.parser")
    lists = soup.find_all(["ul", "ol"])
    if not lists:
        raise RuntimeError("No list was found in the Vatican table of contents.")

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
            "The detected table of contents looks unusually small; "
            "the Vatican HTML structure may have changed."
        )
    return roots


def text_regions_from_html(data: bytes) -> list[str]:
    if not data.strip():
        return []
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    marker = "<<<CEC-HR>>>"
    footnote_marker = "<<<CEC-FOOTNOTES>>>"
    for horizontal_rule in soup.find_all("hr"):
        replacement = footnote_marker if _starts_footnotes(horizontal_rule) else marker
        horizontal_rule.replace_with(NavigableString(f"\n\n{replacement}\n\n"))
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
    chunks = re.split(
        f"({re.escape(marker)}|{re.escape(footnote_marker)})",
        body.get_text(" ", strip=False),
    )
    regions: list[str] = []
    keep = True
    for chunk in chunks:
        if chunk == footnote_marker:
            keep = False
        elif chunk == marker:
            keep = True
        elif keep and normalize_text(chunk):
            regions.append(normalize_text(chunk))
    return regions


def _starts_footnotes(horizontal_rule: Tag) -> bool:
    """Return whether an HTML rule introduces an IntraText footnote block."""
    for element in horizontal_rule.next_elements:
        if isinstance(element, Tag) and element.name == "hr":
            return False
        if isinstance(element, Tag) and element.name == "a":
            anchor_name = element.get("name")
            if isinstance(anchor_name, str) and anchor_name.startswith("$"):
                return True
    return False


def boilerplate_penalty(text: str, language: str = DEFAULT_LANGUAGE) -> int:
    folded = text.casefold()
    penalty = 0
    for phrase in get_language_profile(language).boilerplate_phrases:
        if phrase in folded:
            penalty += 5000
    return penalty


def content_score(text: str, language: str = DEFAULT_LANGUAGE) -> int:
    numbered = sum(
        not is_biblical_reference(match.group(1))
        for match in re.finditer(r"(?m)^\s*\d{1,4}\s+(.+)$", text)
    )
    return len(text) + numbered * 1000 - boilerplate_penalty(text, language)


def extract_main_text(data: bytes, language: str = DEFAULT_LANGUAGE) -> str:
    regions = text_regions_from_html(data)
    if not regions:
        return ""
    profile = get_language_profile(language)
    candidate = max(regions, key=lambda text: content_score(text, language))

    lines: list[str] = []
    for line in candidate.splitlines():
        stripped = line.strip()
        folded = stripped.casefold()
        if not stripped:
            lines.append("")
            continue
        if folded in profile.ignored_lines:
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


def next_page_url(
    data: bytes,
    current_url: str,
    language: str = DEFAULT_LANGUAGE,
) -> str | None:
    """Return the reading page referenced by IntraText's next-page link."""
    next_label = get_language_profile(language).next_label
    soup = BeautifulSoup(data, "html.parser")
    for link in soup.find_all("a", href=True):
        if normalize_text(link.get_text(" ", strip=True)).casefold() == next_label:
            return clean_page_url(current_url, str(link["href"]))
    return None


def append_page_body(
    entry: Entry,
    data: bytes,
    language: str = DEFAULT_LANGUAGE,
    *,
    index_paragraphs: bool = True,
) -> None:
    text = extract_main_text(data, language)
    text = correct_paragraph_numbers(text, language)
    text = strip_leading_duplicate_title(text, entry.title)
    body = body_to_texinfo(
        text,
        entry_path_titles(entry),
        language,
        index_paragraphs=index_paragraphs,
    )
    if body:
        entry.body = "\n\n".join(part for part in (entry.body, body) if part)


def correct_paragraph_numbers(text: str, language: str) -> str:
    """Correct documented source typos only when adjacent numbers confirm them."""
    for incorrect, corrected in get_language_profile(language).paragraph_number_corrections:
        matches = list(re.finditer(r"(?m)^\s*(\d{1,4})[.]\s+", text))
        for index, match in reversed(list(enumerate(matches))):
            if int(match.group(1)) != incorrect or index == 0 or index + 1 >= len(matches):
                continue
            previous = int(matches[index - 1].group(1))
            following = int(matches[index + 1].group(1))
            if previous == corrected - 1 and following == corrected + 1:
                start, end = match.span(1)
                text = text[:start] + str(corrected) + text[end:]
    return text


def downloadable_entries(
    entries: Iterable[Entry],
    index_url: str,
    language: str = DEFAULT_LANGUAGE,
) -> list[tuple[Entry, str]]:
    """Return a single owning entry for each linked page."""
    result: list[tuple[Entry, str]] = []
    seen_urls: set[str] = set()
    for entry in entries:
        url = clean_page_url(index_url, entry.href, language) if entry.href else None
        if url is not None and url not in seen_urls:
            result.append((entry, url))
            seen_urls.add(url)
    return result


def download_linked_pages(
    downloadable: list[tuple[Entry, str]],
    cache_dir: Path,
    refresh: bool,
    delay: float,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, bytes]:
    page_data: dict[str, bytes] = {}
    total = len(downloadable)
    profile = get_language_profile(language)
    content_started = not any(
        re.search(profile.content_start_pattern, entry.title, re.IGNORECASE)
        for entry, _ in downloadable
    )
    for index, (entry, url) in enumerate(downloadable, 1):
        if re.search(profile.content_start_pattern, entry.title, re.IGNORECASE):
            content_started = True
        eprint(f"[{index:3d}/{total}] {entry.title}")
        data = fetch(url, cache_dir, refresh=refresh, delay=delay)
        page_data[url] = data
        append_page_body(
            entry,
            data,
            language,
            index_paragraphs=content_started,
        )
    return page_data


def discover_orphan_chain(
    start_url: str,
    start_data: bytes,
    known_urls: set[str],
    assigned_orphans: set[str],
    cache_dir: Path,
    refresh: bool,
    delay: float,
    language: str = DEFAULT_LANGUAGE,
) -> tuple[list[tuple[str, bytes]], str | None]:
    """Follow next-page links until reaching a known page or a cycle."""
    current_url = start_url
    current_data = start_data
    chain: list[tuple[str, bytes]] = []
    seen_chain = {start_url}

    while True:
        following = next_page_url(current_data, current_url, language)
        if (
            following is None
            or following in seen_chain
            or following in known_urls
            or following in assigned_orphans
        ):
            return chain, following

        eprint(f"[orphan page] {following}")
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
    language: str = DEFAULT_LANGUAGE,
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
        append_page_body(target, orphan_data, language)


def load_bodies(
    roots: list[Entry],
    index_url: str,
    cache_dir: Path,
    refresh: bool,
    delay: float,
    language: str = DEFAULT_LANGUAGE,
) -> int:
    entries = list(flatten_entries(roots))
    downloadable = downloadable_entries(entries, index_url, language)
    entry_positions = {id(entry): index for index, entry in enumerate(entries)}
    url_entries = {url: entry for entry, url in downloadable}
    known_urls = set(url_entries)
    page_data = download_linked_pages(
        downloadable,
        cache_dir,
        refresh,
        delay,
        language,
    )

    if get_language_profile(language).source_format != "intratext":
        return 0

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
            language,
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
            language,
        )
    return len(orphan_urls)
