#!/usr/bin/env python3
"""Public interface and command-line entry point for cec2info.

Internal responsibilities are split between ``cec2info_network`` for
downloads, ``cec2info_parser`` for HTML parsing, and ``cec2info_output`` for
generation. Historical imports remain available from this module to preserve
backward compatibility.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from cec2info_language import (
    DEFAULT_LANGUAGE,
    LANGUAGE_PROFILES,
    get_language_profile,
)
from cec2info_model import (
    Entry,
    assign_nodes,
    entry_path_titles,
    flatten_entries,
    heading_key,
    normalize_text,
)
from cec2info_network import (
    DEFAULT_INDEX,
    USER_AGENT,
    VERSION,
    cache_filename,
    clean_page_url,
    fetch,
    write_cache_atomically,
)
from cec2info_output import (
    body_to_texinfo,
    build_generation_report,
    compile_epub,
    compile_info,
    compile_pdf,
    conditional_entry_heading,
    deduplicate_paragraph_indexes,
    effective_tex_level,
    emit_generation_report,
    emit_menu,
    human_size,
    is_biblical_reference,
    is_repeated_path_heading,
    menu_label,
    paragraph_index_numbers,
    render_texinfo,
    sibling_pointers,
    tex_section_command,
    tex_semantic_level,
    texi_escape,
    validate_paragraph_indexes,
)
from cec2info_parser import (
    append_page_body,
    assign_orphan_chain,
    boilerplate_penalty,
    content_score,
    correct_paragraph_numbers,
    direct_li_title,
    discover_orphan_chain,
    download_linked_pages,
    downloadable_entries,
    extract_main_text,
    first_direct_link,
    load_bodies,
    next_page_url,
    parse_index,
    strip_leading_duplicate_title,
    text_regions_from_html,
)

# These names form the historical API of the monolithic module.
__all__ = [
    "DEFAULT_INDEX",
    "DEFAULT_LANGUAGE",
    "LANGUAGE_PROFILES",
    "USER_AGENT",
    "VERSION",
    "Entry",
    "append_page_body",
    "assign_nodes",
    "assign_orphan_chain",
    "body_to_texinfo",
    "boilerplate_penalty",
    "build_generation_report",
    "build_parser",
    "cache_filename",
    "clean_page_url",
    "compile_epub",
    "compile_info",
    "compile_pdf",
    "conditional_entry_heading",
    "content_score",
    "correct_paragraph_numbers",
    "deduplicate_paragraph_indexes",
    "direct_li_title",
    "discover_orphan_chain",
    "download_linked_pages",
    "downloadable_entries",
    "effective_tex_level",
    "emit_generation_report",
    "emit_menu",
    "entry_path_titles",
    "extract_main_text",
    "fetch",
    "first_direct_link",
    "flatten_entries",
    "get_language_profile",
    "heading_key",
    "human_size",
    "is_biblical_reference",
    "is_repeated_path_heading",
    "load_bodies",
    "main",
    "menu_label",
    "next_page_url",
    "nonnegative_float",
    "nonnegative_int",
    "normalize_text",
    "paragraph_index_numbers",
    "parse_index",
    "render_texinfo",
    "run",
    "sibling_pointers",
    "strip_leading_duplicate_title",
    "tex_section_command",
    "tex_semantic_level",
    "texi_escape",
    "text_regions_from_html",
    "validate_paragraph_indexes",
    "write_cache_atomically",
]


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def nonnegative_float(value: str) -> float:
    result = float(value)
    if result < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return result


def nonnegative_int(value: str) -> int:
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert the official Vatican Catechism to GNU Texinfo/Info."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "--language",
        choices=sorted(LANGUAGE_PROFILES),
        default=DEFAULT_LANGUAGE,
        help=f"source language (default: {DEFAULT_LANGUAGE})",
    )
    parser.add_argument(
        "--index-url",
        help="override the Vatican index URL selected by --language",
    )
    parser.add_argument("--cache-dir", type=Path, default=Path(".cec-cache"))
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Texinfo output path (default depends on --language)",
    )
    parser.add_argument(
        "--info",
        type=Path,
        help="Info output path used with --compile (default depends on --language)",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="run makeinfo after generating the .texi file",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="run texi2dvi in PDF mode after generating the .texi file",
    )
    parser.add_argument(
        "--pdf-output",
        type=Path,
        help="PDF output path used with --pdf (default depends on --language)",
    )
    parser.add_argument(
        "--epub",
        action="store_true",
        help="run makeinfo to generate an EPUB 3 file",
    )
    parser.add_argument(
        "--epub-output",
        type=Path,
        help="EPUB output path used with --epub (default depends on --language)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="download pages again even when they are cached",
    )
    parser.add_argument(
        "--delay",
        type=nonnegative_float,
        default=0.05,
        help="pause between downloads in seconds (default: 0.05)",
    )
    parser.add_argument(
        "--expected-last-paragraph",
        type=nonnegative_int,
        default=2865,
        help="last expected paragraph for validation (0 disables the check)",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="also write the generation report as JSON",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    profile = get_language_profile(args.language)
    index_url = args.index_url or profile.index_url
    output = args.output or Path(f"{profile.info_basename}.texi")
    info_output = args.info or Path(f"{profile.info_basename}.info")
    pdf_output = args.pdf_output or Path(f"{profile.info_basename}.pdf")
    epub_output = args.epub_output or Path(f"{profile.info_basename}.epub")

    eprint(f"Downloading table of contents: {index_url}")
    index_data = fetch(
        index_url,
        args.cache_dir,
        refresh=args.refresh,
        delay=args.delay,
    )
    roots = parse_index(index_data, args.language, index_url)
    entries = assign_nodes(roots)
    eprint(f"Detected {len(entries)} table-of-contents entries.")
    linked_pages = len(downloadable_entries(entries, index_url, args.language))
    orphan_pages = load_bodies(
        roots,
        index_url,
        args.cache_dir,
        refresh=args.refresh,
        delay=args.delay,
        language=args.language,
    )

    texi = deduplicate_paragraph_indexes(render_texinfo(roots, index_url, args.language))
    validate_paragraph_indexes(texi, args.expected_last_paragraph)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(texi, encoding="utf-8")
    eprint(f"Wrote Texinfo: {output}")
    outputs = {"texinfo": output}

    if args.compile:
        compile_info(output, info_output)
        eprint(f"Wrote Info: {info_output}")
        outputs["info"] = info_output
    if args.pdf:
        compile_pdf(output, pdf_output)
        eprint(f"Wrote PDF: {pdf_output}")
        outputs["pdf"] = pdf_output
    if args.epub:
        compile_epub(output, epub_output)
        eprint(f"Wrote EPUB: {epub_output}")
        outputs["epub"] = epub_output

    report = build_generation_report(
        source_url=index_url,
        entry_count=len(entries),
        linked_pages=linked_pages,
        orphan_pages=orphan_pages,
        texi=texi,
        outputs=outputs,
        language=args.language,
    )
    emit_generation_report(report, args.report_json)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        eprint(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
