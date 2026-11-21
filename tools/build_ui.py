"""Build both offline panels from shared templates and editable JSON catalogs. Stdlib only."""

from pathlib import Path
import argparse
import html
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r"@@(HTML|H[SDT]|[SDT]):(m[0-9a-f]{10})@@")


def render(source, catalog):
    def sub(m):
        kind, key = m.groups()
        s = catalog[key]
        if kind.startswith("H"):
            s = html.escape(s, quote=(kind == "HTML"))
        if kind != "HTML":
            delim = {"S": "'", "D": '"', "T": "`"}[kind[-1]]
            s = (
                s.replace("\\", "\\\\")
                .replace(delim, "\\" + delim)
                .replace("\r", "\\r")
                .replace("\n", "\\n")
            )
            if delim == "`":
                s = s.replace("${", "\\${")
        return s

    return TAG.sub(sub, source)


def build(check=False):
    for lang in ("pl", "en"):
        catalog = json.loads((ROOT / "locales" / f"ui.{lang}.json").read_text("utf8"))
        for file in ("index.html", "app.js"):
            s = (ROOT / "ui-src" / (file + ".in")).read_text("utf8")
            s = render(s, catalog)
            suffix = "" if lang == "pl" else ".en"
            if file == "index.html":
                s = s.replace('lang="pl"', f'lang="{lang}"').replace(
                    "/app.js?v=", f"/app{suffix}.js?v="
                )
                if lang == "en":
                    s = s.replace('value="pl" selected', 'value="pl"').replace(
                        'value="en">English', 'value="en" selected>English'
                    )
            name, ext = file.split(".")
            dest = ROOT / "companion" / "static" / (name + suffix + "." + ext)
            if check:
                if dest.read_text("utf8") != s:
                    raise SystemExit(f"Out of date: {dest.name}")
            else:
                with dest.open("w", encoding="utf-8", newline="\n") as out:
                    out.write(s)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    build(p.parse_args().check)
