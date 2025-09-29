from __future__ import annotations

from contextlib import contextmanager
from typing import IO, Iterator, Optional, Callable

import requests
import tempfile

from tuf.ngclient.fetcher import FetcherInterface
from tuf.api import exceptions


ProgressCallback = Callable[[int, Optional[int], Optional[int]], None]


class ProgressFetcher(FetcherInterface):
    """
    Fetcher that reports true per-byte progress during downloads.

    - callback(bytes_received, total_bytes or None, percent or None)
    - Uses requests with stream=True
    - Enforces max_length like the base class
    """

    def __init__(self, callback: ProgressCallback | None = None, *, chunk_size: int = 64 * 1024, timeout: int = 30):
        self.callback: ProgressCallback | None = callback
        self.chunk_size = chunk_size
        self.timeout = timeout

    def set_callback(self, cb: ProgressCallback | None) -> None:
        self.callback = cb

    def _emit(self, received: int, total: int | None) -> None:
        if not self.callback:
            return
        try:
            pct = int(received * 100 / total) if total else None
            self.callback(received, total, pct)
        except Exception:
            # Best-effort only; never break downloads on UI callback errors
            pass

    def _fetch(self, url: str) -> Iterator[bytes]:
        # Basic byte iterator (not used by Updater.download_target which calls
        # download_file), provided for completeness.
        with requests.get(url, stream=True, timeout=self.timeout) as r:
            if r.status_code >= 400:
                raise exceptions.DownloadHTTPError(f"HTTP {r.status_code} for {url}", r.status_code)
            for chunk in r.iter_content(chunk_size=self.chunk_size):
                if chunk:
                    yield chunk

    @contextmanager
    def download_file(self, url: str, max_length: int) -> Iterator[IO]:
        """
        Stream content to a TemporaryFile and yield it, while emitting
        per-chunk progress updates.
        """
        received = 0
        try:
            with requests.get(url, stream=True, timeout=self.timeout) as r:
                if r.status_code >= 400:
                    raise exceptions.DownloadHTTPError(f"HTTP {r.status_code} for {url}", r.status_code)

                # use server length if available; fall back to max_length
                total: Optional[int]
                try:
                    total = int(r.headers.get("Content-Length")) if r.headers.get("Content-Length") else None
                except Exception:
                    total = None
                if total is None:
                    total = max_length or None

                with tempfile.TemporaryFile() as tmp:
                    for chunk in r.iter_content(chunk_size=self.chunk_size):
                        if not chunk:
                            continue
                        received += len(chunk)
                        if max_length and received > max_length:
                            raise exceptions.DownloadLengthMismatchError(
                                f"Downloaded {received} bytes exceeding the maximum allowed length of {max_length}"
                            )
                        tmp.write(chunk)
                        self._emit(received, total)

                    tmp.seek(0)
                    yield tmp
        except exceptions.DownloadError:
            raise
        except Exception as e:
            raise exceptions.DownloadError(f"Failed to download {url}") from e

