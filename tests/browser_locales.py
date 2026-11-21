"""Optional real-browser regression. Run from the project root; see RELEASE_TESTS.md."""

import argparse
from pathlib import Path
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from companion.server import CompanionApp, Handler


def main():
    from playwright.sync_api import sync_playwright, expect

    p = argparse.ArgumentParser()
    p.add_argument("--save-root", required=True, type=Path)
    p.add_argument("--chromium", type=str)
    args = p.parse_args()
    app = CompanionApp(args.save_root)
    with tempfile.TemporaryDirectory() as tmp:
        app.hidden_encounters_status = Path(tmp) / "checks.sqlite3"
        handler = type(
            "QuietHandler", (Handler,), {"app": app, "log_message": lambda *_: None}
        )
        with ThreadingHTTPServer(("127.0.0.1", 0), handler) as srv:
            thread = threading.Thread(target=srv.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{srv.server_port}"
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(executable_path=args.chromium)
                    try:
                        ctx = browser.new_context(
                            locale="en-US", viewport={"width": 1100, "height": 800}
                        )
                        errors = []
                        foreign = []

                        def local_only(route):
                            if (
                                urlsplit(route.request.url).netloc
                                != urlsplit(base).netloc
                            ):
                                foreign.append(route.request.url)
                                route.abort()
                            else:
                                route.continue_()

                        ctx.route("**/*", local_only)
                        page = ctx.new_page()
                        page.on("pageerror", lambda e: errors.append(str(e)))
                        page.goto(base)
                        expect(page.locator("#hero")).to_contain_text("LEVEL")
                        expect(page.locator("html")).to_have_attribute("lang", "en")
                        page.locator('[data-tab="iconic"]').click()
                        page.locator("#iconic-search").fill("Gris-Gris")
                        expect(page.locator("#iconic-rows")).to_contain_text(
                            "storeroom key"
                        )
                        page.locator("#language").select_option("pl")
                        expect(page.locator("html")).to_have_attribute("lang", "pl")
                        expect(page.locator("#iconic")).to_be_visible()
                        page.locator("#iconic-search").fill("Gris-Gris")
                        expect(page.locator("#iconic-rows")).to_contain_text(
                            "klucz do magazynku"
                        )
                        page.goto(base)
                        expect(page.locator("html")).to_have_attribute("lang", "pl")
                        page.locator("#language").select_option("en")
                        expect(page.locator("#hero")).to_contain_text("LEVEL")
                        page.locator("#save-select").select_option("ManualSave-660")
                        page.locator("#load-save").click()
                        expect(page.locator("#save-current")).to_contain_text(
                            "ManualSave-660"
                        )
                        page.locator('[data-tab="hidden-encounters"]').click()
                        mark = page.locator("select.encounter-status-select").first
                        with page.expect_response(
                            lambda r: (
                                r.url.endswith("/api/hidden-encounters/status") and r.ok
                            )
                        ):
                            mark.select_option("completed")
                        page.reload()
                        page.locator('[data-tab="hidden-encounters"]').click()
                        expect(
                            page.locator("select.encounter-status-select").first
                        ).to_have_value("completed")
                        page.locator('[data-tab="quest-choices"]').click()
                        page.locator("#choice-search").fill("Anna")
                        card = page.locator("#choice-list article").first
                        expect(card).to_contain_text("Warn Anna first")
                        card.locator("details.choice-spoilers summary").click()
                        expect(card).to_contain_text("Leave the city")
                        for tab in page.locator("nav.tabs button").all():
                            tab.click()
                            assert page.locator(".tab-panel:visible").count() == 1
                        assert not errors, errors
                        assert not foreign, foreign
                        print(
                            "PASS: PL/EN assets, cookie, tab, guides, quest branches, save selection, persisted mark and no off-device requests."
                        )
                    finally:
                        browser.close()
            finally:
                srv.shutdown()
                thread.join()


if __name__ == "__main__":
    main()
