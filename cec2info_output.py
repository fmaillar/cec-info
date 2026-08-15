"""Texinfo transformation, validation, reporting, and output compilation."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from cec2info_language import DEFAULT_LANGUAGE, get_language_profile
from cec2info_model import Entry, flatten_entries, heading_key, normalize_text

PARA_RE = re.compile(r'^\s*(\d{1,4})[.]?(?:\s+|(?=["«]))(.+)$')
BIBLE_REFERENCE_RE = re.compile(
    r"^(?:[1-3]\s+)?[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-öø-ÿ.]{0,5}\s+\d",
    re.IGNORECASE,
)
ROMAN_RE = re.compile(r"^[IVXLCDM]+[.]\s+", re.IGNORECASE)


def eprint(*args: object) -> None:
    import sys

    print(*args, file=sys.stderr)


def texi_escape(text: str) -> str:
    return text.replace("@", "@@").replace("{", "@{").replace("}", "@}")


def is_repeated_path_heading(text: str, path_titles: list[str]) -> bool:
    """Detect a title fragment already represented by the table-of-contents tree."""
    key = heading_key(text)
    if not key or len(key) < 3:
        return False
    for title in path_titles:
        title_key = heading_key(title)
        if (
            key == title_key
            or (len(key) >= 8 and key in title_key)
            or (len(title_key) >= 8 and title_key in key)
        ):
            return True
    return False


def is_biblical_reference(text: str) -> bool:
    """Return whether text starts with a numbered Bible book reference."""
    first_word = text.split(maxsplit=1)[0].casefold() if text else ""
    if first_word in {"das", "der", "die"}:
        return False
    return BIBLE_REFERENCE_RE.match(text) is not None


def body_to_texinfo(
    text: str,
    path_titles: list[str] | None = None,
    language: str = DEFAULT_LANGUAGE,
    *,
    index_paragraphs: bool = True,
) -> str:
    if not text:
        return ""

    paragraphs = _split_text_paragraphs(text)
    output: list[str] = []
    before_first_number = True
    path_titles = path_titles or []

    for paragraph in paragraphs:
        part = normalize_text(" ".join(paragraph.splitlines()))
        match = PARA_RE.match(part)
        if match:
            number, rest = match.groups()
            # A Bible reference split by the page layout can look like a false
            # paragraph, such as ``1 P 3, 21`` or ``2 S 7, 14``.
            if not is_biblical_reference(rest):
                before_first_number = False
                if index_paragraphs:
                    output.append(f"@cindex {number}")
                    prefix = get_language_profile(language).paragraph_prefix
                    output.append(f"@cindex {prefix} {number}")
                output.append(f"@strong{{{number}}} {texi_escape(rest)}")
                output.append("")
                continue

        escaped = texi_escape(part)
        if before_first_number and is_repeated_path_heading(part, path_titles):
            output.extend(["@ifinfo", escaped, "@end ifinfo", ""])
        else:
            output.extend([escaped, ""])

    return "\n".join(output).rstrip()


def _split_text_paragraphs(text: str) -> list[str]:
    """Split paragraphs and recover consecutive numbers merged by malformed HTML."""
    paragraphs: list[str] = []
    for raw_part in re.split(r"\n\s*\n", text):
        dotted_parts = re.split(r"(?m)(?=^\s*\d{1,4}[.]\s+)", raw_part)
        for dotted_part in dotted_parts:
            _append_split_paragraph(paragraphs, dotted_part)
    return paragraphs


def _append_split_paragraph(paragraphs: list[str], raw_part: str) -> None:
    part = normalize_text(" ".join(raw_part.splitlines()))
    if not part:
        return

    match = PARA_RE.match(part)
    while match:
        next_number = int(match.group(1)) + 1
        boundary = re.search(rf"\s+(?={next_number}[.]?(?:\s+|(?=[\"«])))", part)
        if boundary is None:
            break
        paragraphs.append(part[: boundary.start()].rstrip())
        part = part[boundary.end() :].lstrip()
        match = PARA_RE.match(part)
    paragraphs.append(part)


def sibling_pointers(entry: Entry, roots: list[Entry]) -> tuple[str, str]:
    siblings = entry.parent.children if entry.parent else roots
    index = siblings.index(entry)
    previous_node = siblings[index - 1].node if index > 0 else ""
    next_node = siblings[index + 1].node if index + 1 < len(siblings) else ""
    return next_node, previous_node


def menu_label(title: str) -> str:
    return texi_escape(title.replace(":", " —"))


def emit_menu(children: list[Entry]) -> str:
    if not children:
        return ""
    lines = ["@menu"]
    for child in children:
        lines.append(f"* {menu_label(child.title)}: {child.node}.")
    lines.append("@end menu")
    return "\n".join(lines)


def tex_semantic_level(title: str, language: str = DEFAULT_LANGUAGE) -> int | None:
    """Return the desired TeX level: 0=part, 1=chapter, ..., 4=subsubsection."""
    profile = get_language_profile(language)
    title = title.strip()
    if re.search(profile.part_pattern, title, re.IGNORECASE):
        return 0
    if re.search(profile.section_pattern, title, re.IGNORECASE):
        return 1
    if re.search(profile.chapter_pattern, title, re.IGNORECASE):
        return 2
    if re.search(profile.article_pattern, title, re.IGNORECASE):
        return 3
    if re.search(profile.paragraph_pattern, title, re.IGNORECASE) or ROMAN_RE.search(title):
        return 4
    return None


def effective_tex_level(entry: Entry, language: str = DEFAULT_LANGUAGE) -> int | None:
    """Compute a usable Texinfo level without gaps in the actual tree."""
    profile = get_language_profile(language)
    folded = heading_key(entry.title.strip())
    desired = tex_semantic_level(entry.title.strip(), language)
    if (
        folded in profile.unnumbered_titles
        or folded in profile.brief_titles
        or desired is None
    ):
        return None
    if desired == 0:
        return 0

    parent = entry.parent
    parent_level: int | None = None
    while parent is not None:
        level = effective_tex_level(parent, language)
        if level is not None:
            parent_level = level
            break
        parent = parent.parent

    if parent_level is None or parent_level == 0:
        return 1
    return min(desired, parent_level + 1)


def tex_section_command(entry: Entry, language: str = DEFAULT_LANGUAGE) -> str:
    """Return the sectioning command derived from the effective tree."""
    profile = get_language_profile(language)
    escaped = texi_escape(entry.title.strip())
    folded = heading_key(entry.title.strip())
    if folded in profile.unnumbered_titles:
        return f"@unnumbered {escaped}"
    if folded in profile.brief_titles:
        return f"@subsubheading {escaped}"

    level = effective_tex_level(entry, language)
    if level is None:
        return f"@subsubheading {escaped}"
    if level == 0:
        return f"@unnumbered {escaped}"
    commands = {1: "chapter", 2: "section", 3: "subsection", 4: "subsubsection"}
    return f"@{commands[level]} {escaped}"


def conditional_entry_heading(entry: Entry, language: str = DEFAULT_LANGUAGE) -> str:
    """Use @heading for Info and sectioning commands for other formats."""
    return "\n".join(
        [
            "@ifinfo",
            f"@heading {texi_escape(entry.title)}",
            "@end ifinfo",
            "@ifnotinfo",
            tex_section_command(entry, language),
            "@end ifnotinfo",
        ]
    )


def render_texinfo(
    roots: list[Entry],
    source_url: str,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    profile = get_language_profile(language)
    entries = list(flatten_entries(roots))
    chunks: list[str] = []
    top_menu = emit_menu(roots)
    if top_menu:
        top_menu = top_menu[: -len("@end menu")] + "* Index::\n@end menu"
    else:
        top_menu = "@menu\n* Index::\n@end menu"

    chunks.append(
        "\\input texinfo\n"
        "@documentencoding UTF-8\n"
        f"@documentlanguage {profile.texinfo_language}\n"
        f"@setfilename {profile.info_basename}.info\n"
        f"@settitle {profile.document_title}\n\n"
        "@dircategory Religion\n"
        "@direntry\n"
        f"* {profile.dir_entry_name}: ({profile.info_basename}). "
        f"{profile.document_title}.\n"
        "@end direntry\n\n"
        "@copying\n"
        f"{profile.conversion_notice}\n"
        f"Source: @uref{{{texi_escape(source_url)}}}.\n"
        f"{profile.source_rights_notice}\n"
        "@end copying\n\n"
        "@titlepage\n"
        f"@title {profile.document_title}\n"
        f"@subtitle {profile.subtitle}\n"
        "@page\n@vskip 0pt plus 1filll\n@insertcopying\n@end titlepage\n\n"
        "@iftex\n@headings off\n@contents\n@page\n@end iftex\n\n"
        "@node Top\n"
        f"@top {profile.document_title}\n\n"
        f"{profile.introduction}\n\n"
        f"{profile.navigation_help}\n\n"
        f"{top_menu}\n"
    )

    for entry in entries:
        next_node, previous_node = sibling_pointers(entry, roots)
        chunks.append(
            "\n".join(
                [
                    "",
                    f"@node {entry.node}, {next_node}, {previous_node}, {entry.up_node}",
                    conditional_entry_heading(entry, language),
                    "",
                    emit_menu(entry.children),
                    "",
                    entry.body,
                    "",
                ]
            )
        )

    chunks.append(
        "\n@node Index\n"
        f"@unnumbered {profile.paragraph_index_title}\n"
        "@printindex cp\n\n"
        "@bye\n"
    )
    return "\n".join(chunks)


def paragraph_index_numbers(texi: str) -> list[int]:
    return [int(number) for number in re.findall(r"(?m)^@cindex (\d+)$", texi)]


def deduplicate_paragraph_indexes(texi: str) -> str:
    """Keep the first index entry when embedded numbered lists reuse a number."""
    lines = texi.splitlines(keepends=True)
    output: list[str] = []
    seen: set[int] = set()
    discard_prefixed_number: int | None = None
    for line in lines:
        numeric = re.fullmatch(r"@cindex (\d+)\n?", line)
        if numeric:
            number = int(numeric.group(1))
            if number in seen:
                discard_prefixed_number = number
                continue
            seen.add(number)
            discard_prefixed_number = None
            output.append(line)
            continue
        if discard_prefixed_number is not None and re.fullmatch(
            rf"@cindex \S+ {discard_prefixed_number}\n?", line
        ):
            discard_prefixed_number = None
            continue
        discard_prefixed_number = None
        output.append(line)
    return "".join(output)


def validate_paragraph_indexes(texi: str, expected_last: int) -> None:
    if expected_last <= 0:
        return
    numbers = paragraph_index_numbers(texi)
    counts: dict[int, int] = {}
    for number in numbers:
        counts[number] = counts.get(number, 0) + 1

    missing = [number for number in range(1, expected_last + 1) if number not in counts]
    duplicates = [number for number, count in counts.items() if count > 1]
    unexpected = [number for number in counts if not 1 <= number <= expected_last]
    if missing or duplicates or unexpected:
        details = []
        if missing:
            details.append(f"missing: {missing}")
        if duplicates:
            details.append(f"duplicates: {duplicates}")
        if unexpected:
            details.append(f"out of range: {unexpected}")
        raise RuntimeError(
            "Incomplete or invalid paragraph index (" + "; ".join(details) + ")"
        )
    eprint(f"Paragraphs 1 through {expected_last} are present exactly once.")


def build_generation_report(
    *,
    source_url: str,
    entry_count: int,
    linked_pages: int,
    orphan_pages: int,
    texi: str,
    outputs: dict[str, Path],
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, object]:
    numbers = paragraph_index_numbers(texi)
    unique_numbers = set(numbers)
    output_details: dict[str, object] = {}
    for name, path in outputs.items():
        if path.exists():
            output_details[name] = {"path": str(path), "bytes": path.stat().st_size}
    return {
        "language": language,
        "source_url": source_url,
        "entries": entry_count,
        "pages": {
            "linked": linked_pages,
            "orphan": orphan_pages,
            "total": linked_pages + orphan_pages,
        },
        "paragraphs": {
            "count": len(numbers),
            "unique": len(unique_numbers),
            "first": min(unique_numbers) if unique_numbers else None,
            "last": max(unique_numbers) if unique_numbers else None,
        },
        "outputs": output_details,
    }


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def emit_generation_report(
    report: dict[str, object],
    json_path: Path | None = None,
) -> None:
    pages = report["pages"]
    paragraphs = report["paragraphs"]
    outputs = report["outputs"]
    assert isinstance(pages, dict)
    assert isinstance(paragraphs, dict)
    assert isinstance(outputs, dict)

    eprint("\nGeneration report")
    eprint(f"  Language            : {report['language']}")
    eprint(f"  Table of contents   : {report['entries']} entries")
    eprint(
        "  HTML pages          : "
        f"{pages['total']} ({pages['linked']} linked, {pages['orphan']} orphan)"
    )
    eprint(
        "  Paragraphs         : "
        f"{paragraphs['unique']} unique, range {paragraphs['first']}–{paragraphs['last']}"
    )
    for name, details in outputs.items():
        assert isinstance(details, dict)
        eprint(
            f"  {str(name).upper():<18}: "
            f"{human_size(int(details['bytes']))} — {details['path']}"
        )

    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        eprint(f"  JSON report         : {json_path}")


def compile_info(texi_path: Path, info_path: Path) -> None:
    if shutil.which("makeinfo") is None:
        raise RuntimeError("makeinfo was not found. Install the Debian 'texinfo' package.")
    info_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["makeinfo", "--no-split", "--output", str(info_path), str(texi_path)],
        check=True,
    )


def compile_pdf(texi_path: Path, pdf_path: Path) -> None:
    if shutil.which("texi2dvi") is None:
        raise RuntimeError("texi2dvi was not found. Install Texinfo/TeX.")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "texi2dvi",
            "--batch",
            "--build=clean",
            "--dvipdf",
            "--output",
            str(pdf_path.resolve()),
            texi_path.name,
        ],
        check=True,
        cwd=texi_path.parent,
    )


def compile_epub(texi_path: Path, epub_path: Path) -> None:
    if shutil.which("makeinfo") is None:
        raise RuntimeError("makeinfo was not found. Install the Debian 'texinfo' package.")
    epub_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["makeinfo", "--epub3", "--output", str(epub_path), str(texi_path)],
        check=True,
    )
