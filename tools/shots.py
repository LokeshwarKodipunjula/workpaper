"""Screenshot every page of the UI as a given actor and report console errors."""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:8000")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "shots")
ACTOR = sys.argv[1] if len(sys.argv) > 1 else "st-02"
PAGES = sys.argv[2].split(",") if len(sys.argv) > 2 else ["/", "/area/deductions_and_credits", "/area/investments_and_digital_assets", "/documents", "/checks", "/records/sales_detail", "/records/state_split", "/activity", "/versions", "/filing", "/firm", "/whatif", "/household", "/client"]


async def main():
    os.makedirs(OUT, exist_ok=True)
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1500, "height": 950})
        pg.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        await pg.goto(BASE + "/")
        await pg.evaluate(f"localStorage.setItem('wp.actor', '{ACTOR}')")
        for path in PAGES:
            await pg.goto(BASE + path)
            await pg.wait_for_timeout(1400)
            name = (path.strip("/").replace("/", "_") or "overview")
            await pg.screenshot(path=os.path.join(OUT, f"{ACTOR}_{name}.png"), full_page=False)
            print("shot", path)
        # open a trace drawer
        await pg.goto(BASE + "/area/deductions_and_credits")
        await pg.wait_for_timeout(1200)
        rows = pg.locator("tr.clickable")
        if await rows.count() > 0:
            await rows.nth(0).click()
            await pg.wait_for_timeout(1200)
            await pg.screenshot(path=os.path.join(OUT, f"{ACTOR}_trace.png"))
            # click first source to open document viewer
            src = pg.locator(".drawer table tr.clickable")
            if await src.count() > 0:
                await src.nth(0).click()
                await pg.wait_for_timeout(1200)
                await pg.screenshot(path=os.path.join(OUT, f"{ACTOR}_document.png"))
        await b.close()
    print("\n".join(errors) if errors else "no console errors")


asyncio.run(main())
