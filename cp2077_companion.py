#!/usr/bin/env python3
"""CP2077 Companion: offline GUI, explicit exports and optional catalog download."""

from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

from companion.localio import require_local_root
from companion.core import assistant_context, assistant_context_markdown
from companion.server import CompanionApp, normalize_host, serve, validate_static_assets


def default_save_root() -> Path:
    return (
        Path(os.environ.get("USERPROFILE") or Path.home())
        / "Saved Games"
        / "CD Projekt Red"
        / "Cyberpunk 2077"
    )


def args_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local read-only Cyberpunk 2077 companion")
    p.add_argument("--save-root", type=Path, default=default_save_root())
    p.add_argument("--host", default="127.0.0.1", help="127.0.0.1, localhost or ::1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--max-saves", type=int, default=500)
    p.add_argument("--no-open", action="store_true")
    modes = p.add_mutually_exclusive_group()
    modes.add_argument(
        "--once",
        action="store_true",
        help="export one snapshot without starting a server",
    )
    modes.add_argument(
        "--update-catalog",
        action="store_true",
        help="download the pinned optional public item list, then exit",
    )
    p.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports"),
        help="parent for complete snapshot directories",
    )
    return p


def write_exports(app: CompanionApp, export_dir: Path) -> Path:
    state = app.state()
    if not state.get("ok"):
        raise ValueError(state.get("error", "No save data"))
    if state.get("scan_stale") or state["latest"].get("binary_parser_status") != "ok":
        raise ValueError("Save could not be decoded; previous exports kept")
    ctx = assistant_context(state)
    files = {
        "state.json": json.dumps(state, ensure_ascii=False, indent=2),
        "assistant-context.json": json.dumps(ctx, ensure_ascii=False, indent=2),
        "assistant-context.md": assistant_context_markdown(ctx),
    }
    root = require_local_root(export_dir).resolve()
    saves = app.save_root.resolve()
    if root == saves or root.is_relative_to(saves):
        raise ValueError("Export destination must be outside the save directory")
    root.mkdir(parents=True, exist_ok=True)
    target = root / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    stage = Path(tempfile.mkdtemp(prefix=".pending-", dir=root))
    try:
        for name, value in files.items():
            with (stage / name).open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
        stage.rename(target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return target


def main() -> int:
    args = args_parser().parse_args()
    try:
        if args.update_catalog:
            from companion.catalog_fetch import URL, update_catalog

            update_catalog()
            print("Verified catalog installed:", URL)
            return 0
        host = normalize_host(args.host)
        if not 1 <= args.port <= 65535 or not 1 <= args.max_saves <= 1000:
            raise ValueError("Port: 1..65535; max-saves: 1..1000")
        if args.once:
            app = CompanionApp(args.save_root, args.max_saves)
            print("Exports:", write_exports(app, args.export_dir))
        else:
            validate_static_assets()
            serve(
                args.save_root,
                host,
                args.port,
                args.max_saves,
                open_browser=not args.no_open,
            )
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
