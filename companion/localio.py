"""Small, bounded local reads; no network operations."""

import os
import stat
import sys
import re
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar

MIB = 1024 * 1024
SAVE_LIMIT = 64 * MIB
BLOCK_LIMIT = 2 * MIB
OUTPUT_LIMIT = 128 * MIB
META_LIMIT = MIB
IMAGE_LIMIT = 16 * MIB


_MOUNTS = ContextVar("companion_remote_mounts", default=None)
_REMOTE_FS = {
    "nfs",
    "nfs4",
    "cifs",
    "smb3",
    "ceph",
    "afs",
    "coda",
    "9p",
    "virtiofs",
    "fuse.sshfs",
    "fuse.rclone",
    "davfs",
    "fuse.davfs",
    "fuse.s3fs",
    "fuse.gcsfuse",
}


def _remote_mounts():
    if not sys.platform.startswith("linux"):
        return ()
    result = []
    with open(
        "/proc/self/mountinfo", encoding="utf8", errors="surrogateescape"
    ) as info:
        for line in info:
            left, sep, right = line.partition(" - ")
            if sep and right.split()[0] in _REMOTE_FS:
                name = left.split()[4]
                result.append(
                    Path(re.sub(r"\\\\([0-7]{3})", lambda m: chr(int(m[1], 8)), name))
                )
    return tuple(result)


@contextmanager
def local_read_scope():
    # Snapshot mount information once per request, including mounts below the save root.
    if _MOUNTS.get() is not None:
        yield
        return
    token = _MOUNTS.set(_remote_mounts())
    try:
        yield
    finally:
        _MOUNTS.reset(token)


def _remote_path(path):
    mounts = _MOUNTS.get()
    if mounts is None:
        mounts = _remote_mounts()
    if not mounts:
        return False
    absolute = Path(os.path.abspath(path))
    return any(absolute.is_relative_to(mount) for mount in mounts)


def regular_local(path: Path, directory: bool = False) -> bool:
    if _remote_path(path):
        return False
    try:
        s = path.lstat()
    except OSError:
        return False
    return not getattr(s, "st_file_attributes", 0) & 0x400 and (
        stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)
    )


def read_limited(path: Path, limit: int) -> bytes:
    if not regular_local(path):
        raise ValueError(f"Not a regular local file: {path.name}")
    before = path.lstat()
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(os.open(path, flags), "rb") as f:
        st = os.fstat(f.fileno())
        if not os.path.samestat(before, st):
            raise ValueError(f"File changed before read: {path.name}")
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            raise ValueError(f"File exceeds the supported limit: {path.name}")
        # Read the advertised size plus one; avoid reserving the full budget for small files.
        data = f.read(st.st_size + 1)
        after = os.fstat(f.fileno())
        if len(data) != st.st_size or (st.st_size, st.st_mtime_ns) != (
            after.st_size,
            after.st_mtime_ns,
        ):
            raise ValueError(f"File changed during read: {path.name}")
        return data


def require_local_root(path: Path) -> Path:
    """Reject UNC / mapped network drives and known Linux network mounts without reading their files."""
    text = str(path)
    if text.startswith(("\\\\", "//")):
        raise ValueError("Choose a directory on a local drive")
    root = path.absolute()
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        drive_type = ctypes.WinDLL("kernel32", use_last_error=True).GetDriveTypeW
        drive_type.argtypes = [wintypes.LPCWSTR]
        drive_type.restype = wintypes.UINT
        if drive_type(root.anchor) == 4:
            raise ValueError("Mapped network drives are not supported")
    if _remote_path(root):
        raise ValueError("Network-mounted directories are not supported")
    # Reject links in existing components before traversing a junction / mount alias.
    for parent in list(reversed(root.parents)) + [root]:
        try:
            st = parent.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) & 0x400:
            raise ValueError("Choose a local directory without links or reparse points")
    return root
