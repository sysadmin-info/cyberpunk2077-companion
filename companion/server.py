from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import hmac
import secrets
import socket
import webbrowser
from http.cookies import SimpleCookie, CookieError
import threading
from urllib.parse import parse_qs, urlsplit

from .core import (
    assistant_context,
    assistant_context_markdown,
    build_state,
    scan_saves,
    find_firestarter_saves,
    _metadata_file,
)
from .hidden_encounters import (
    build_hidden_encounters_payload,
    set_user_status,
    import_legacy,
    profile_scope,
    load_hidden_encounter_dataset,
)
from .localio import (
    regular_local,
    read_limited,
    IMAGE_LIMIT,
    require_local_root,
    local_read_scope,
)
from .i18n import localize_state
from .iconic_weapons import build_iconic_payload


def validate_static_assets(static_dir: Path | None = None) -> None:
    """Fail before opening a UI that cannot start without its script."""
    root = static_dir if static_dir is not None else Path(__file__).parent / "static"
    missing = [
        root / name
        for name in (
            "index.html",
            "index.en.html",
            "app.js",
            "app.en.js",
            "boot.js",
            "styles.css",
        )
        if not (root / name).is_file() or (root / name).stat().st_size == 0
    ]
    if missing:
        paths = "\n".join(str(path.resolve()) for path in missing)
        raise FileNotFoundError(
            "Incomplete Companion installation: missing or empty UI files:\n"
            + paths
            + "\nExtract the complete ZIP into a new folder and run run.ps1."
        )


class CompanionApp:
    def __init__(self, save_root: Path, max_saves: int = 500):
        self.save_root = require_local_root(save_root)
        self.max_saves = max_saves
        from .i18n import catalog

        for language in ("pl", "en"):
            catalog(language)  # Fail at startup if a local content catalog is missing.
        self.static_dir = Path(__file__).parent / "static"
        validate_static_assets(self.static_dir)
        self.hidden_encounters_data = (
            Path(__file__).parent.parent / "data" / "hidden_encounters.json"
        )
        self.hidden_encounters_status = (
            Path(__file__).parent.parent / "data" / "hidden_encounters.sqlite3"
        )
        self.iconic_weapons_data = (
            Path(__file__).parent.parent / "data" / "iconic_weapons.json"
        )
        self.session_token = secrets.token_urlsafe(32)
        self._cache_lock = threading.RLock()
        self.selected_save: str | None = None
        self._cache_signature: tuple | None = None
        self._cache_state: dict | None = None

    def _save_signature(self) -> tuple:
        """Cheap change detector; avoids re-parsing sav.dat on every UI poll."""
        rows: list[tuple] = []
        try:
            root_mtime = self.save_root.stat().st_mtime_ns
        except OSError:
            root_mtime = 0
        if not self.save_root.exists():
            return (root_mtime, ())
        try:
            entries = list(self.save_root.iterdir())
        except OSError:
            return (root_mtime, ())
        for path in entries:
            if not regular_local(path, directory=True):
                continue
            try:
                sav = path / "sav.dat"
                sav_sig = (
                    (sav.stat().st_mtime_ns, sav.stat().st_size)
                    if regular_local(sav)
                    else (0, 0)
                )
                newest = _metadata_file(path)
                if newest:
                    meta_sig = (
                        newest.name,
                        newest.stat().st_mtime_ns,
                        newest.stat().st_size,
                    )
                else:
                    meta_sig = ("", 0, 0)
                rows.append((path.name, sav_sig, meta_sig))
            except OSError:
                continue
        rows.sort()
        from .item_catalog import CATALOG_PATH

        try:
            cat = CATALOG_PATH.lstat() if regular_local(CATALOG_PATH) else None
        except OSError:
            cat = None
        return (
            root_mtime,
            tuple(rows),
            (cat.st_size, cat.st_mtime_ns) if cat else None,
        )

    def _build(self, selected_save: str | None) -> dict:
        warnings = []
        try:
            saves = scan_saves(
                self.save_root,
                self.max_saves,
                selected_save=selected_save,
                warnings=warnings,
            )
        except OSError:
            return {"ok": False, "error": "Save directory is unavailable."}
        state = build_state(saves, selected_save=selected_save)
        if state.get("ok"):
            state["iconic_weapons"] = build_iconic_payload(
                state["latest"], self.iconic_weapons_data
            )
        state["scan_warnings"] = warnings
        state["save_selection"] = {
            "mode": "manual" if selected_save is not None else "automatic",
            "selected_save": selected_save,
            "active_save": state.get("latest", {}).get("save_name"),
            "saves": [
                {
                    "save_id": Path(s.save_path).name,
                    "save_name": s.save_name,
                    "timestamp": s.timestamp_string,
                    "level": s.level,
                    "playthrough_hours": s.playthrough_hours,
                }
                for s in saves
            ],
        }
        return state

    @local_read_scope()
    def select_save(self, name: str | None) -> dict:
        # Resolve only by exact membership in the scanned list, never as a path.
        if name is not None and (
            not isinstance(name, str)
            or not name
            or "/" in name
            or "\\" in name
            or name in {".", ".."}
        ):
            raise ValueError("Nieprawidłowa nazwa zapisu")
        with self._cache_lock:
            signature = self._save_signature()
            candidate = self._build(name)
            if not candidate.get("ok"):
                raise ValueError(candidate.get("error", "Brak zapisów"))
            self.selected_save = name
            self._cache_state = candidate
            self._cache_signature = signature
        return {"ok": True}

    @local_read_scope()
    def state(self) -> dict:
        with self._cache_lock:
            signature = self._save_signature()
            if self._cache_state is None or signature != self._cache_signature:
                candidate = self._build(self.selected_save)
                previous = self._cache_state or {}
                last = previous.get("latest", {})
                current = candidate.get("latest", {})
                slot = last.get("save_id")
                # Only retain the same slot, never show a different V under the selected name.
                same_binary_unreadable = (
                    slot
                    and current.get("save_id") == slot
                    and current.get("binary_parser_status") != "ok"
                )
                same_metadata_unreadable = (
                    slot
                    and not candidate.get("ok")
                    and slot in candidate.get("scan_warnings", [])
                )
                if last.get("binary_parser_status") == "ok" and (
                    same_binary_unreadable or same_metadata_unreadable
                ):
                    self._cache_state = {
                        **previous,
                        "scan_stale": True,
                        "scan_warnings": candidate.get("scan_warnings", []),
                        "save_selection": {
                            **candidate["save_selection"],
                            "active_save": last.get("save_name"),
                        },
                    }
                else:
                    self._cache_state = candidate
                self._cache_signature = signature
            base_state = self._cache_state

        # Hidden Encounters is application-local data, not part of sav.dat. Merge a fresh
        # snapshot so manual discovered/completed status updates do not depend on save mtimes.
        state = dict(base_state)
        state["hidden_encounters"] = build_hidden_encounters_payload(
            self.hidden_encounters_data,
            self.hidden_encounters_status,
            profile_scope(state.get("latest", {})),
        )
        return state

    def mark(self, action: str, payload: dict) -> dict:
        with self._cache_lock:
            state = self.state()
            if not state.get("ok"):
                raise ValueError("No active save")
            if state.get("scan_stale"):
                raise ValueError(
                    "Save is being updated or is unreadable. Refresh before continuing."
                )
            scope = profile_scope(state["latest"])
            if payload.get("scope") != scope:
                raise ValueError("Active playthrough changed; refresh first.")
            if action.endswith("/import"):
                ids = {
                    x["id"]
                    for x in load_hidden_encounter_dataset(self.hidden_encounters_data)[
                        "records"
                    ]
                }
                return {
                    "imported": import_legacy(self.hidden_encounters_status, scope, ids)
                }
            return set_user_status(
                payload.get("id", ""),
                payload.get("status", ""),
                self.hidden_encounters_data,
                self.hidden_encounters_status,
                scope,
            )


def normalize_host(host: str) -> str:
    if host in ("localhost", "127.0.0.1"):
        return "127.0.0.1"
    if host == "::1":
        return "::1"
    raise ValueError("Local mode only: choose 127.0.0.1 or ::1")


class Handler(BaseHTTPRequestHandler):
    app: CompanionApp
    timeout = 10

    def _send(self, status: int, body: bytes, mime: str, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, obj, status=200, filename=None):
        headers = (
            {"Content-Disposition": f'attachment; filename="{filename}"'}
            if filename
            else {}
        )
        self._send(
            status,
            json.dumps(obj, ensure_ascii=False).encode(),
            "application/json; charset=utf-8",
            headers,
        )

    def _reject(self, code, message):
        lang = self._locale({})
        from .i18n import catalog

        self._json({"ok": False, "error": catalog(lang).get(message, message)}, code)

    def _host(self):
        hosts = self.headers.get_all("Host", [])
        port = self.server.server_port
        allowed = {f"{name}:{port}" for name in ("localhost", "127.0.0.1", "[::1]")}
        if port == 80:
            allowed.update(("localhost", "127.0.0.1", "[::1]"))
        return (
            hosts[0].lower()
            if len(hosts) == 1 and hosts[0].lower() in allowed
            else None
        )

    def _locale(self, query):
        choice = query.get("lang", [""])[0]
        if choice in ("pl", "en"):
            return choice
        try:
            c = SimpleCookie(self.headers.get("Cookie", "")).get("companion_lang")
            if c and c.value in ("pl", "en"):
                return c.value
        except CookieError:
            pass
        pref = self.headers.get("Accept-Language", "").lower().split(",")[0]
        return "en" if pref.startswith("en") else "pl"

    @local_read_scope()
    def do_GET(self):
        try:
            if not self._host():
                return self._reject(403, "Local host required")
            route = urlsplit(self.path)
            path, query = route.path, parse_qs(route.query)
            lang = self._locale(query)
            if (
                path.startswith("/api/")
                and self.headers.get("Sec-Fetch-Site") == "cross-site"
            ):
                return self._reject(403, "Same-origin access required")
            if path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if path == "/api/health":
                return self._json({"ok": True})
            if path == "/api/session":
                return self._json({"token": self.app.session_token})
            if path == "/api/state":
                state = self.app.state()
                return self._json(
                    localize_state(state, lang) if "lang" in query else state
                )
            if path == "/api/decision-saves/firestarter":
                state = self.app.state()
                if not state.get("ok") or state.get("scan_stale"):
                    return self._reject(
                        409,
                        "Save is being updated or is unreadable. Refresh before continuing.",
                    )
                current = state["latest"]
                result = find_firestarter_saves(
                    self.app.save_root, current["playthrough_id"]
                )
                return self._json(
                    {
                        "ok": True,
                        "selected_slot": current["save_id"],
                        "selected_profile": current["playthrough_id"],
                        **result,
                    }
                )
            if path in (
                "/api/assistant-context.md",
                "/api/assistant-context.json",
                "/api/screenshot",
            ):
                state = self.app.state()
                if not state.get("ok"):
                    return self._reject(409, state.get("error", "No active save"))
                if state.get("scan_stale") or (
                    not path.endswith("screenshot")
                    and state["latest"].get("binary_parser_status") != "ok"
                ):
                    return self._reject(
                        409,
                        "Save is being updated or is unreadable. Refresh before continuing.",
                    )
                if path.endswith("screenshot"):
                    latest = state["latest"]
                    folder = self.app.save_root / latest["save_id"]
                    if not latest["has_screenshot"] or not regular_local(
                        folder, directory=True
                    ):
                        return self._reject(404, "No screenshot")
                    try:
                        data = read_limited(folder / "screenshot.png", IMAGE_LIMIT)
                    except (ValueError, OSError):
                        return self._reject(404, "Screenshot is unavailable")
                    return self._send(200, data, "image/png")
                ctx = assistant_context(state)
                if path.endswith(".json"):
                    return self._json(ctx, filename="assistant-context.json")
                return self._send(
                    200,
                    assistant_context_markdown(ctx).encode(),
                    "text/markdown; charset=utf-8",
                    {
                        "Content-Disposition": 'attachment; filename="assistant-context.md"'
                    },
                )
            names = {
                "/styles.css": "styles.css",
                "/app.js": "app.js",
                "/app.en.js": "app.en.js",
                "/boot.js": "boot.js",
            }
            headers = {}
            if path in ("/", "/index.html"):
                name = "index.en.html" if lang == "en" else "index.html"
                if query.get("lang", [""])[0] in ("pl", "en"):
                    headers["Set-Cookie"] = (
                        f"companion_lang={lang}; Path=/; SameSite=Strict; Max-Age=31536000"
                    )
                headers["Content-Language"] = lang
            elif path in names:
                name = names[path]
            else:
                return self._reject(404, "Not found")
            target = self.app.static_dir / name
            if not regular_local(target):
                return self._reject(404, "Asset unavailable")
            mime = {
                "js": "application/javascript",
                "css": "text/css",
                "html": "text/html",
            }[name.rsplit(".", 1)[1]]
            return self._send(
                200,
                read_limited(target, 2 * 1024 * 1024),
                mime + "; charset=utf-8",
                headers,
            )
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            return
        except Exception:
            self.log_error("local read failed")
            return self._reject(500, "Local read failed")

    @local_read_scope()
    def do_POST(self):
        try:
            host = self._host()
            if (
                not host
                or self.headers.get_all("Origin", []) != ["http://" + host]
                or self.headers.get("Sec-Fetch-Site") == "cross-site"
            ):
                return self._reject(403, "Local origin required")
            token = self.headers.get("X-Companion-Token", "")
            if not token.isascii() or not hmac.compare_digest(
                token, self.app.session_token
            ):
                return self._reject(403, "Refresh the panel and try again")
            path = urlsplit(self.path).path
            if path not in (
                "/api/save-selection",
                "/api/hidden-encounters/status",
                "/api/hidden-encounters/import",
            ):
                return self._reject(404, "Not found")
            if self.headers.get_content_type() != "application/json":
                return self._reject(415, "JSON required")
            lengths = self.headers.get_all("Content-Length", [])
            if (
                self.headers.get("Transfer-Encoding")
                or len(lengths) != 1
                or not lengths[0].isdecimal()
                or not 0 < int(lengths[0]) <= 16384
            ):
                return self._reject(400, "Invalid request size")
            payload = json.loads(self.rfile.read(int(lengths[0])).decode("utf-8"))
            if not isinstance(payload, dict):
                return self._reject(400, "Expected an object")
            if path.endswith("save-selection"):
                if "save_name" not in payload:
                    raise ValueError("Missing save ID")
                return self._json(self.app.select_save(payload["save_name"]))
            return self._json({"ok": True, **self.app.mark(path, payload)})
        except (ValueError, RecursionError) as exc:
            return self._reject(400, str(exc))
        except (ConnectionError, socket.timeout):
            return
        except Exception:
            self.log_error("local update failed")
            return self._reject(500, "Local update failed")


def serve(
    save_root: Path,
    host: str,
    port: int,
    max_saves: int = 500,
    open_browser: bool = False,
):
    host = normalize_host(host)
    app = CompanionApp(save_root, max_saves)
    cls = type("CompanionHandler", (Handler,), {"app": app})
    server_cls = (
        type("LoopbackV6", (ThreadingHTTPServer,), {"address_family": socket.AF_INET6})
        if host == "::1"
        else ThreadingHTTPServer
    )
    with server_cls((host, port), cls) as server:
        url = f"http://{'[::1]' if host == '::1' else host}:{server.server_port}/"
        print("CP2077 Companion:", url, flush=True)
        if open_browser:
            threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
