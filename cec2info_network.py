"""HTTP downloads and local caching for cec2info."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from importlib import metadata
from pathlib import Path, PurePosixPath

from cec2info_language import DEFAULT_LANGUAGE, FRENCH, get_language_profile

DEFAULT_INDEX = FRENCH.index_url
try:
    VERSION = metadata.version("cec2info")
except metadata.PackageNotFoundError:
    VERSION = "development"

USER_AGENT = f"cec2info/{VERSION} (+GNU Info + TeX structured conversion)"
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
RETRYABLE_HTTP_STATUS = {408, 429, 500, 502, 503, 504}


def clean_page_url(
    index_url: str,
    href: str,
    language: str = DEFAULT_LANGUAGE,
) -> str | None:
    absolute = urllib.parse.urljoin(index_url, href)
    parsed = urllib.parse.urlsplit(absolute)
    index = urllib.parse.urlsplit(index_url)
    if (
        index.scheme == "https"
        and parsed.scheme == "http"
        and parsed.netloc.casefold() == index.netloc.casefold()
    ):
        parsed = parsed._replace(scheme="https")
        absolute = urllib.parse.urlunsplit(parsed)
    name = PurePosixPath(parsed.path).name

    if re.fullmatch(r"_P[A-Za-z0-9]+\.HTM?", name, re.IGNORECASE):
        clean_name = "_" + name
        path = str(PurePosixPath(parsed.path).with_name(clean_name))
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
        )
    if re.fullmatch(r"__P[A-Za-z0-9]+\.HTM?", name, re.IGNORECASE):
        return absolute
    profile = get_language_profile(language)
    if profile.source_format == "legacy":
        same_directory = (
            parsed.netloc.casefold() == index.netloc.casefold()
            and PurePosixPath(parsed.path).parent == PurePosixPath(index.path).parent
        )
        is_html = PurePosixPath(parsed.path).suffix.casefold() in {".htm", ".html"}
        is_index = parsed.path.casefold() == index.path.casefold()
        if same_directory and is_html and not is_index:
            return urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.query, "")
            )
    return None


def cache_filename(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    name = PurePosixPath(parsed.path).name or "index.html"
    safe_name = SAFE_FILENAME_RE.sub("_", name)

    # Preserve historical names for the official source to avoid invalidating
    # the existing cache. For any other URL, include a digest of the complete
    # URL so two corpora using the same IntraText names cannot silently share
    # the same files.
    official = urllib.parse.urlsplit(FRENCH.index_url)
    if (
        parsed.scheme == official.scheme
        and parsed.netloc == official.netloc
        and PurePosixPath(parsed.path).parent == PurePosixPath(official.path).parent
        and not parsed.query
    ):
        return safe_name

    normalized = urllib.parse.urlunsplit(parsed._replace(fragment=""))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{digest}-{safe_name}"


def write_cache_atomically(target: Path, data: bytes) -> None:
    """Replace a cache file without exposing partially written content."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            delete=False,
        ) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fetch(
    url: str,
    cache_dir: Path,
    refresh: bool,
    delay: float,
    *,
    timeout: float = 30.0,
    retries: int = 2,
    retry_backoff: float = 0.5,
) -> bytes:
    if delay < 0:
        raise ValueError("delay must be non-negative")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if retries < 0 or retry_backoff < 0:
        raise ValueError("retries and retry_backoff must be non-negative")

    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / cache_filename(url)
    if target.exists() and target.stat().st_size > 0 and not refresh:
        return target.read_bytes()

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    last_error: BaseException | None = None
    attempts = retries + 1
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
            if not data.strip():
                raise ValueError("empty response")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in RETRYABLE_HTTP_STATUS:
                break
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
        else:
            write_cache_atomically(target, data)
            if delay > 0:
                time.sleep(delay)
            return data

        if attempt + 1 < attempts and retry_backoff > 0:
            time.sleep(retry_backoff * (2**attempt))

    detail = str(last_error) if last_error is not None else "unknown error"
    raise RuntimeError(
        f"Failed to download {url} after {attempt + 1} attempt(s): {detail}"
    ) from last_error
