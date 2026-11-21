"""Optional offline Chromium check with fictional slot names and two independent profiles."""

import argparse
import sys
import threading
from hashlib import sha256
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from companion.server import CompanionApp, Handler
from tests.test_firestarter import write_slot


def main():
    from playwright.sync_api import expect, sync_playwright

    args = argparse.ArgumentParser()
    args.add_argument("--chromium", required=True)
    opts = args.parse_args()
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_slot(root, "ManualSave-10", "09:00:00, 10.01.2026", ["q304_active=1"])
        write_slot(root, "AutoSave-1", "09:15:00, 10.01.2026", ["q304_active=1"])
        write_slot(
            root,
            "OtherProfile",
            "09:16:00, 10.01.2026",
            finished="q304 q305",
            profile="example-B",
        )
        write_slot(
            root, "AutoSave-2", "09:30:00, 10.01.2026", ["q304_songbirds_path=1"]
        )
        write_slot(root, "ManualSave-11", "09:45:00, 10.01.2026", finished="q304 q306")

        def hashes():
            return {
                f.relative_to(root): sha256(f.read_bytes()).digest()
                for f in root.rglob("*")
                if f.is_file()
            }

        before = hashes()
        # The oldest two candidates are intentionally outside the main selector.
        app = CompanionApp(root, max_saves=3)
        handler = type(
            "LocalTest", (Handler,), {"app": app, "log_message": lambda *_: None}
        )
        with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(executable_path=opts.chromium)
                    try:
                        ctx = browser.new_context(locale="pl-PL")
                        foreign, errors, scans = [], [], []

                        def local_only(route):
                            url = urlsplit(route.request.url)
                            if url.netloc != urlsplit(base).netloc:
                                foreign.append(url.netloc)
                                return route.abort()
                            if url.path == "/api/decision-saves/firestarter":
                                scans.append(url.path)
                            return route.continue_()

                        ctx.route("**/*", local_only)
                        page = ctx.new_page()
                        page.on("pageerror", lambda e: errors.append(str(e)))
                        page.goto(base + "/?lang=pl")
                        tab = page.locator('[data-tab="quest-choices"]')
                        tab.click()
                        expect(page.locator("#fork-search")).to_have_text(
                            "Szukaj zapisów tej rozgrywki"
                        )
                        expect(page.locator("#fork-results")).to_be_hidden()
                        assert not scans, "the finder must not run on startup"
                        page.locator("#fork-search").click()
                        summary = page.locator("#fork-summary")
                        expect(summary).to_contain_text("AutoSave-1")
                        expect(summary).to_contain_text("AutoSave-2")
                        rows = page.locator("#fork-rows tr")
                        expect(rows).to_have_count(4)
                        expect(page.locator("#fork-rows")).not_to_contain_text(
                            "OtherProfile"
                        )
                        page.locator("#fork-kind").select_option("manual")
                        expect(summary).to_contain_text("ManualSave-10")
                        expect(summary).to_contain_text("ManualSave-11")
                        expect(rows).to_have_count(2)
                        page.locator("#fork-stage").select_option("candidate")
                        expect(rows).to_have_count(1)
                        page.locator("#fork-name").fill("does-not-exist")
                        expect(rows).to_have_count(0)
                        expect(page.locator("#fork-count")).to_have_text(
                            "Brak pasujących zapisów."
                        )
                        assert len(scans) == 1, "filters should not rescan the drive"
                        page.locator("#language").select_option("en")
                        expect(page.locator("#fork-search")).to_have_text(
                            "Search this playthrough"
                        )
                        page.locator("#fork-search").click()
                        expect(summary).to_contain_text("Latest candidate to load")
                        page.locator("#choice-search").fill("Chimera")
                        card = page.locator("#choice-list article")
                        expect(card).to_have_count(1)
                        details = card.locator(".choice-spoilers")
                        expect(details.locator(".choice-branch").first).to_be_hidden()
                        details.locator("summary").click()
                        expect(details).to_contain_text("Cynosure")
                        expect(details).to_contain_text("The Killing Moon")
                        expect(details).to_contain_text(
                            "Songbird route: helped her escape."
                        )
                        page.locator("#save-select").select_option("OtherProfile")
                        page.locator("#load-save").click()
                        expect(page.locator("#fork-results")).to_be_hidden()
                        page.locator("#fork-search").click()
                        expect(rows).to_have_count(1)
                        expect(summary).to_contain_text("No dated slot")
                        expect(summary).to_contain_text("OtherProfile")
                        expect(page.locator("#fork-rows")).not_to_contain_text(
                            "ManualSave-10"
                        )
                        assert not foreign and not errors, (foreign, errors)
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                worker.join()
        assert before == hashes(), "save files changed"
    print(
        "PASS: PL/EN finder, results beyond main list, filters, reset on profile change, guide, offline traffic and unchanged saves."
    )


if __name__ == "__main__":
    main()
