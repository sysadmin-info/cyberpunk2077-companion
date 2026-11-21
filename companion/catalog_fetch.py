"""The only outbound application request. Called explicitly, never on GUI startup."""

from __future__ import annotations
from http.client import HTTPException
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import HTTPRedirectHandler, Request, build_opener
from . import __version__

REVISION = "f256a327d533f5058465c7f64e6f4773d0330535"
URL = f"https://raw.githubusercontent.com/ysrdevs/nightcity-console-mac/{REVISION}/runtime/cet_catalog.tsv"
SHA256 = "e69fbab9fcad414980f3ee6e898043912ba80dc2925a7d94f363c4e9bd1dcbf7"
SIZE = 514951
DEST = Path(__file__).resolve().parents[1] / "data" / "cet_catalog.tsv"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def install_stream(source, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".catalog-", dir=dest.parent)
    try:
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(fd, "wb") as out:
            while chunk := source.read(min(65536, SIZE + 1 - total)):
                total += len(chunk)
                if total > SIZE:
                    raise ValueError("Catalog exceeds the pinned size")
                digest.update(chunk)
                out.write(chunk)
            if total != SIZE or digest.hexdigest() != SHA256:
                raise ValueError(
                    "Catalog integrity check failed; existing catalog preserved"
                )
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, dest)
    finally:
        Path(name).unlink(missing_ok=True)


def update_catalog(dest: Path = DEST) -> None:
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(
            Request(
                URL,
                headers={
                    "User-Agent": f"CP2077-Companion/{__version__}",
                    "Accept": "text/plain",
                },
            ),
            timeout=20,
        ) as src:
            install_stream(src, dest)
    except HTTPException as exc:
        raise ValueError(
            "Catalog connection ended before verification; existing catalog preserved"
        ) from exc
