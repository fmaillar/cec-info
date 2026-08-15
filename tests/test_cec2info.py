import contextlib
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from cec2info import (
    Entry,
    USER_AGENT,
    VERSION,
    assign_nodes,
    body_to_texinfo,
    build_parser,
    build_generation_report,
    cache_filename,
    compile_epub,
    compile_info,
    compile_pdf,
    emit_generation_report,
    fetch,
    flatten_entries,
    load_bodies,
    main,
    next_page_url,
    parse_index,
    render_texinfo,
    run,
    validate_paragraph_indexes,
)


class ParseIndexTests(unittest.TestCase):
    def test_transparent_nested_list_wrapper(self) -> None:
        data = b"""
        <html><body><ul>
          <li><a href="__P1.HTM">Prologue</a><ul><ul>
            <li><a href="__P2.HTM">Section enfant</a></li>
          </ul></ul></li>
          <li><a href="__P3.HTM">Partie</a></li>
          <li>3</li><li>4</li><li>5</li><li>6</li><li>7</li><li>8</li>
          <li>9</li><li>10</li><li>11</li><li>12</li><li>13</li><li>14</li>
          <li>15</li><li>16</li><li>17</li><li>18</li><li>19</li><li>20</li>
        </ul></body></html>
        """
        roots = parse_index(data)
        entries = list(flatten_entries(roots))
        self.assertEqual(entries[1].title, "Section enfant")
        self.assertIs(entries[1].parent, entries[0])
        self.assertEqual(entries[1].depth, 2)


class TexinfoConversionTests(unittest.TestCase):
    def test_real_paragraph_is_indexed(self) -> None:
        result = body_to_texinfo(
            '1 Dieu nous appelle.\n\n26" Nous croyons. "'
        )
        self.assertIn("@cindex 1", result)
        self.assertIn("@cindex 26", result)

    def test_split_biblical_reference_is_not_indexed(self) -> None:
        result = body_to_texinfo("128 Un texte (cf.\n\n1 P 3, 21).")
        self.assertIn("@cindex 128", result)
        self.assertNotIn("@cindex 1\n", result)
        self.assertIn("1 P 3, 21", result)


class NavigationAndValidationTests(unittest.TestCase):
    def test_next_page_url_finds_orphan_page(self) -> None:
        data = '<a href="__P15.HTM">Suivant</a>'.encode()
        self.assertEqual(
            next_page_url(data, "https://example.test/book/__P14.HTM"),
            "https://example.test/book/__P15.HTM",
        )

    def test_cache_is_namespaced_outside_official_source(self) -> None:
        first = cache_filename("https://one.test/book/__P1.HTM")
        second = cache_filename("https://two.test/book/__P1.HTM")
        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith("-__P1.HTM"))

    def test_validation_rejects_missing_and_duplicate_numbers(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "absents.*doublons"):
            validate_paragraph_indexes(
                "@cindex 1\n@cindex 1\n@cindex 3\n",
                expected_last=3,
            )

    def test_orphan_page_is_assigned_to_unlinked_entry(self) -> None:
        source = Entry(title="Source", href="__P1.HTM", depth=1)
        orphan_entry = Entry(title="Section orpheline", href=None, depth=1)
        following = Entry(title="Suite", href="__P3.HTM", depth=1)
        roots = [source, orphan_entry, following]
        pages = {
            "https://example.test/book/__P1.HTM": (
                '<body>1 Début.<a href="__P2.HTM">Suivant</a></body>'.encode()
            ),
            "https://example.test/book/__P2.HTM": (
                '<body>2 Milieu.<a href="__P3.HTM">Suivant</a></body>'.encode()
            ),
            "https://example.test/book/__P3.HTM": (
                "<body>3 Fin.</body>".encode()
            ),
        }

        with patch("cec2info.fetch", side_effect=lambda url, *_args, **_kwargs: pages[url]):
            orphan_count = load_bodies(
                roots,
                "https://example.test/book/_INDEX.HTM",
                Path("unused-cache"),
                refresh=False,
                delay=0,
            )

        self.assertEqual(orphan_count, 1)
        self.assertIn("@cindex 1", source.body)
        self.assertIn("@cindex 2", orphan_entry.body)
        self.assertIn("@cindex 3", following.body)

    def test_duplicate_page_url_is_downloaded_and_assigned_once(self) -> None:
        first = Entry(title="Première entrée", href="__P1.HTM", depth=1)
        duplicate = Entry(title="Entrée dupliquée", href="__P1.HTM", depth=1)
        page = b"<body>1 Contenu unique.</body>"

        with patch("cec2info.fetch", return_value=page) as mocked_fetch:
            orphan_count = load_bodies(
                [first, duplicate],
                "https://example.test/book/_INDEX.HTM",
                Path("unused-cache"),
                refresh=False,
                delay=0,
            )

        self.assertEqual(orphan_count, 0)
        mocked_fetch.assert_called_once()
        self.assertIn("@cindex 1", first.body)
        self.assertEqual(duplicate.body, "")

    def test_orphan_cycle_stops_without_duplicate_download(self) -> None:
        source = Entry(title="Source", href="__P1.HTM", depth=1)
        pages = {
            "https://example.test/book/__P1.HTM": (
                '<body>1 Début.<a href="__P2.HTM">Suivant</a></body>'.encode()
            ),
            "https://example.test/book/__P2.HTM": (
                '<body>2 Suite.<a href="__P1.HTM">Suivant</a></body>'.encode()
            ),
        }

        with patch(
            "cec2info.fetch",
            side_effect=lambda url, *_args, **_kwargs: pages[url],
        ) as mocked_fetch:
            orphan_count = load_bodies(
                [source],
                "https://example.test/book/_INDEX.HTM",
                Path("unused-cache"),
                refresh=False,
                delay=0,
            )

        self.assertEqual(orphan_count, 1)
        self.assertEqual(mocked_fetch.call_count, 2)
        self.assertEqual(source.body.count("@cindex 1"), 1)
        self.assertEqual(source.body.count("@cindex 2"), 1)


class FetchTests(unittest.TestCase):
    url = "https://example.test/book/__P1.HTM"

    def test_nonempty_cache_avoids_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            target = cache_dir / cache_filename(self.url)
            target.write_bytes(b"cached")

            with patch("cec2info.urllib.request.urlopen") as urlopen:
                data = fetch(self.url, cache_dir, refresh=False, delay=0)

            self.assertEqual(data, b"cached")
            urlopen.assert_not_called()

    def test_empty_cache_is_replaced_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            target = cache_dir / cache_filename(self.url)
            target.write_bytes(b"")

            with patch(
                "cec2info.urllib.request.urlopen",
                return_value=io.BytesIO(b"<html>contenu</html>"),
            ):
                data = fetch(self.url, cache_dir, refresh=False, delay=0)

            self.assertEqual(data, b"<html>contenu</html>")
            self.assertEqual(target.read_bytes(), data)
            self.assertFalse(any(cache_dir.glob(f".{target.name}.*")))

    def test_temporary_error_is_retried_with_backoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch(
                    "cec2info.urllib.request.urlopen",
                    side_effect=[URLError("temporaire"), io.BytesIO(b"ok")],
                ) as urlopen,
                patch("cec2info.time.sleep") as sleep,
            ):
                data = fetch(
                    self.url,
                    Path(directory),
                    refresh=True,
                    delay=0,
                    retries=1,
                    retry_backoff=0.25,
                )

            self.assertEqual(data, b"ok")
            self.assertEqual(urlopen.call_count, 2)
            sleep.assert_called_once_with(0.25)

    def test_permanent_http_error_is_not_retried(self) -> None:
        error = HTTPError(self.url, 404, "introuvable", {}, None)
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "cec2info.urllib.request.urlopen",
                side_effect=error,
            ) as urlopen:
                with self.assertRaisesRegex(RuntimeError, "1 tentative"):
                    fetch(
                        self.url,
                        Path(directory),
                        refresh=True,
                        delay=0,
                        retries=3,
                    )

            urlopen.assert_called_once()

    def test_failed_refresh_preserves_previous_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            target = cache_dir / cache_filename(self.url)
            target.write_bytes(b"ancien contenu")

            with patch(
                "cec2info.urllib.request.urlopen",
                return_value=io.BytesIO(b""),
            ):
                with self.assertRaisesRegex(RuntimeError, "réponse vide"):
                    fetch(
                        self.url,
                        cache_dir,
                        refresh=True,
                        delay=0,
                        retries=0,
                    )

            self.assertEqual(target.read_bytes(), b"ancien contenu")


class GenerationReportTests(unittest.TestCase):
    def test_text_and_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output = base / "book.info"
            output.write_bytes(b"generated-info")
            report = build_generation_report(
                source_url="https://example.test/source",
                entry_count=3,
                linked_pages=2,
                orphan_pages=1,
                texi=(
                    "@cindex 1\n@cindex CEC 1\n"
                    "@cindex 2\n@cindex CEC 2\n"
                ),
                outputs={"info": output},
            )
            json_path = base / "report.json"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                emit_generation_report(report, json_path)

            self.assertIn("3 (2 liées, 1 orphelines)", stderr.getvalue())
            self.assertIn("2 uniques, plage 1–2", stderr.getvalue())
            saved = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["paragraphs"]["unique"], 2)
            self.assertEqual(saved["outputs"]["info"]["bytes"], 14)


class CliTests(unittest.TestCase):
    def test_user_agent_uses_package_version(self) -> None:
        self.assertIn(f"cec2info/{VERSION}", USER_AGENT)

    def test_parser_accepts_all_output_formats(self) -> None:
        args = build_parser().parse_args(
            [
                "--compile",
                "--info",
                "manuel.info",
                "--pdf",
                "--pdf-output",
                "manuel.pdf",
                "--epub",
                "--epub-output",
                "manuel.epub",
                "--expected-last-paragraph",
                "0",
            ]
        )

        self.assertTrue(args.compile)
        self.assertEqual(args.info, Path("manuel.info"))
        self.assertTrue(args.pdf)
        self.assertEqual(args.pdf_output, Path("manuel.pdf"))
        self.assertTrue(args.epub)
        self.assertEqual(args.epub_output, Path("manuel.epub"))
        self.assertEqual(args.expected_last_paragraph, 0)

    def test_parser_rejects_negative_delay(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
            build_parser().parse_args(["--delay", "-1"])
        self.assertIn("positive ou nulle", stderr.getvalue())

    def test_main_reports_expected_error_without_traceback(self) -> None:
        stderr = io.StringIO()
        with (
            patch("cec2info.run", side_effect=RuntimeError("échec contrôlé")),
            contextlib.redirect_stderr(stderr),
        ):
            status = main([])

        self.assertEqual(status, 1)
        self.assertIn("Erreur: échec contrôlé", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_run_writes_texinfo_and_report(self) -> None:
        items = "".join(
            f'<li><a href="__P{i}.HTM">Entrée {i}</a></li>'
            for i in range(1, 21)
        )
        index_data = f"<html><body><ul>{items}</ul></body></html>".encode()

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            args = build_parser().parse_args(
                [
                    "--cache-dir",
                    str(base / "cache"),
                    "--output",
                    str(base / "book.texi"),
                    "--expected-last-paragraph",
                    "0",
                    "--report-json",
                    str(base / "report.json"),
                ]
            )
            with (
                patch("cec2info.fetch", return_value=index_data),
                patch("cec2info.load_bodies", return_value=0),
            ):
                status = run(args)

            self.assertEqual(status, 0)
            self.assertIn("@node Top", (base / "book.texi").read_text())
            report = json.loads((base / "report.json").read_text())
            self.assertEqual(report["entries"], 20)
            self.assertEqual(report["pages"]["linked"], 20)


@unittest.skipUnless(
    all(shutil.which(tool) for tool in ("makeinfo", "texi2dvi")),
    "Texinfo/TeX ne sont pas installés",
)
class FormatCompilationTests(unittest.TestCase):
    def test_info_pdf_and_epub_are_generated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            entry = Entry(
                title="Section de test",
                href=None,
                depth=1,
                body=body_to_texinfo("1 Texte de validation des formats."),
            )
            roots = [entry]
            assign_nodes(roots)
            texi = render_texinfo(roots, "https://example.test/source")
            validate_paragraph_indexes(texi, expected_last=1)

            texi_path = base / "test.texi"
            info_path = base / "test.info"
            pdf_path = base / "test.pdf"
            epub_path = base / "test.epub"
            texi_path.write_text(texi, encoding="utf-8")

            compile_info(texi_path, info_path)
            compile_pdf(texi_path, pdf_path)
            compile_epub(texi_path, epub_path)

            self.assertIn(
                "Texte de validation",
                info_path.read_text(encoding="utf-8"),
            )
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))
            self.assertFalse(
                any(
                    (base / f"test{suffix}").exists()
                    for suffix in (".aux", ".cp", ".cps", ".dvi", ".log", ".toc")
                )
            )
            with zipfile.ZipFile(epub_path) as archive:
                xhtml = b"".join(
                    archive.read(name)
                    for name in archive.namelist()
                    if name.endswith(".xhtml")
                )
            self.assertIn(b"Texte de validation", xhtml)


if __name__ == "__main__":
    unittest.main()
