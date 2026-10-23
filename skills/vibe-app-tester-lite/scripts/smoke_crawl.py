#!/usr/bin/env python3
"""
Smoke crawl a web app on desktop and mobile and record functional problems.

Finds: JavaScript crashes, console errors, failed API calls (4xx/5xx), broken
internal links, broken images, mobile layouts wider than the screen, leftover
placeholder text ("undefined", "NaN", "lorem ipsum", "[object Object]"),
dead "#" links, missing page titles and slow pages. Saves screenshots.

Usage:
  python smoke_crawl.py http://localhost:3000 --out qa-results
  python smoke_crawl.py http://localhost:3000 --routes /pricing /dashboard --max-pages 80
  python smoke_crawl.py http://localhost:3000 --storage-state auth.json   # crawl as a logged-in user

Only crawl apps you own or are allowed to test. Links that look destructive
(logout, delete, remove, cancel subscription) are never followed.
"""
import argparse, json, os, re, sys, time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

from playwright.sync_api import sync_playwright

VIEWPORTS = {
    "desktop": {"viewport": {"width": 1366, "height": 900}},
    "mobile": {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True,
               "device_scale_factor": 2},
}
SKIP_LINK = re.compile(r"logout|log-out|signout|sign-out|delete|remove|destroy|unsubscribe|cancel", re.I)
PLACEHOLDERS = [
    (re.compile(r"\bundefined\b"), "the word 'undefined' is shown on the page"),
    (re.compile(r"\bNaN\b"), "'NaN' (not-a-number) is shown on the page"),
    (re.compile(r"\[object Object\]"), "'[object Object]' is shown on the page"),
    (re.compile(r"lorem ipsum", re.I), "placeholder 'lorem ipsum' text is still on the page"),
    (re.compile(r"\bTODO\b|\bFIXME\b"), "a TODO/FIXME note is visible on the page"),
    (re.compile(r"\{\{\s*\w+\s*\}\}"), "an unfilled template placeholder like {{name}} is visible"),
]
STATIC_EXT = re.compile(r"\.(png|jpe?g|gif|svg|webp|ico|pdf|zip|mp4|mp3|css|js|woff2?)$", re.I)

PAGE_CHECKS_JS = r"""
() => {
  const text = document.body ? document.body.innerText : "";
  const brokenImgs = [...document.images]
    .filter(i => i.complete && i.naturalWidth === 0 && (i.currentSrc || i.src))
    .map(i => i.currentSrc || i.src);
  const deadLinks = [...document.querySelectorAll('a')]
    .filter(a => { const h = (a.getAttribute('href') || '').trim();
                   return (h === '#' || h === '' || h.startsWith('javascript:')) && !a.onclick
                          && a.innerText.trim() && a.getAttribute('role') !== 'button'; })
    .map(a => a.innerText.trim().slice(0, 60));
  // on phones the browser zooms out to fit wide content, so compare with the device width, not innerWidth
  const screenW = Math.min(window.screen.width || 99999, document.documentElement.clientWidth || 99999);
  const overflow = document.documentElement.scrollWidth - screenW;
  let widest = null, contentOverflow = false;
  if (overflow > 2) {
    // find the widest element that is real page content (fixed overlays like toast containers
    // can widen the layout without anything visible being cut off)
    let maxRight = 0, maxRightAny = 0, widestAny = null;
    for (const el of document.body.querySelectorAll('*')) {
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') continue;
      const r = el.getBoundingClientRect();
      if (r.width <= 0) continue;
      let fixed = false;
      for (let n = el; n && n !== document.body; n = n.parentElement)
        if (getComputedStyle(n).position === 'fixed') { fixed = true; break; }
      if (!fixed && r.right > maxRight) { maxRight = r.right; widest = el; }
      if (r.right > maxRightAny) { maxRightAny = r.right; widestAny = el; }
    }
    contentOverflow = maxRight > screenW + 2;
    if (!contentOverflow) widest = widestAny;
  }
  const describe = el => el ? el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
     (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0,2).join('.') : '') : null;
  return {
    title: document.title,
    looksNotFound: /\b404\b|page not found|not found|doesn.t exist|does not exist/i.test(text.slice(0, 2000)),
    hasViewportMeta: !!document.querySelector('meta[name=viewport]'),
    text: text.slice(0, 200000),
    brokenImgs, deadLinks: [...new Set(deadLinks)].slice(0, 20),
    overflowPx: overflow, contentOverflow, widestEl: describe(widest),
    links: [...document.querySelectorAll('a[href]')].map(a => a.href),
  };
}
"""


def norm(url):
    url, _ = urldefrag(url)
    return url.rstrip("/") or url


def add(findings, severity, kind, page, viewport, detail, evidence=None):
    key = (kind, page, detail)
    for f in findings:
        if (f["kind"], f["page"], f["detail"]) == key:
            if viewport not in f["viewports"]:
                f["viewports"].append(viewport)
            return
    findings.append({"severity": severity, "kind": kind, "page": page, "viewports": [viewport],
                     "detail": detail, "evidence": evidence or {}})


def crawl(args):
    base = norm(args.url)
    origin = urlparse(base).netloc
    os.makedirs(os.path.join(args.out, "screens"), exist_ok=True)
    findings, visited, pages_info = [], [], []
    queue = deque([base] + [norm(urljoin(base + "/", r.lstrip("/"))) for r in args.routes])
    seen = set(queue)
    link_status = {}
    from_links = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        contexts = {}
        for name, opts in VIEWPORTS.items():
            if args.storage_state:
                opts = {**opts, "storage_state": args.storage_state}
            contexts[name] = browser.new_context(**opts)

        while queue and len(visited) < args.max_pages:
            url = queue.popleft()
            visited.append(url)
            path = urlparse(url).path or "/"
            info = {"url": url}
            for vname, ctx in contexts.items():
                page = ctx.new_page()
                console, crashes, bad_resp = [], [], []
                page.on("console", lambda m, c=console: c.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e, c=crashes: c.append(str(e)))
                page.on("response", lambda r, b=bad_resp: b.append((r.status, r.url, r.request.method, r.request.resource_type))
                        if r.status >= 400 and r.request.resource_type != "document" else None)
                page.on("requestfailed", lambda r, b=bad_resp: b.append((0, r.url, r.method, r.resource_type))
                        if r.resource_type != "document" else None)
                t0 = time.time()
                try:
                    resp = page.goto(url, wait_until="load", timeout=args.timeout * 1000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    page.wait_for_timeout(args.settle_ms)
                except Exception as ex:
                    add(findings, "high", "page-did-not-load", path, vname, f"Page failed to load: {str(ex)[:200]}")
                    page.close()
                    continue
                load_s = round(time.time() - t0, 1)
                status = resp.status if resp else 0
                link_status[url] = status
                if status >= 500:
                    add(findings, "high", "server-error", path, vname, f"Page returned HTTP {status}")
                elif status >= 400:
                    add(findings, "medium", "page-not-found", path, vname, f"Page returned HTTP {status}")

                data = page.evaluate(PAGE_CHECKS_JS)
                shot = os.path.join("screens", f"{re.sub(r'[^a-zA-Z0-9]+', '_', path).strip('_') or 'home'}_{vname}.png")
                try:
                    page.screenshot(path=os.path.join(args.out, shot), full_page=True)
                except Exception:
                    shot = None
                info[vname] = {"status": status, "load_s": load_s, "title": data["title"], "screenshot": shot}

                for c in crashes:
                    add(findings, "high", "javascript-crash", path, vname, f"Uncaught JavaScript error: {c[:300]}", {"screenshot": shot})
                spa_404 = data["looksNotFound"] or any(re.search(r"non-existent route|404", c, re.I) for c in console)
                if spa_404 and status < 400:
                    # app shows its own "not found" screen (single-page apps return 200)
                    if url in from_links:
                        add(findings, "medium", "broken-link", path, vname,
                            f"A link in the app leads to a 'page not found' screen (linked from {from_links[url]})")
                    elif url != base:
                        add(findings, "info", "route-not-found", path, vname,
                            "This URL shows the app's 'not found' page (it was requested manually, not linked)")
                for c in console:
                    # generic 'Failed to load resource' messages duplicate the network findings below;
                    # 'not found' logs on the app's own 404 screen are expected behaviour
                    if "favicon" in c.lower() or c.startswith("Failed to load resource"):
                        continue
                    if spa_404 and re.search(r"non-existent route|404", c, re.I):
                        continue
                    add(findings, "medium", "console-error", path, vname, f"Console error: {c[:300]}", {"screenshot": shot})
                for st, u, m, rtype in bad_resp:
                    if "favicon" in u.lower() or rtype == "image":   # images are covered by broken-image
                        continue
                    if rtype in ("script", "stylesheet", "font") and st != 0:
                        add(findings, "high" if rtype == "script" else "medium", "missing-resource", path, vname,
                            f"{rtype} file {u[:200]} returned HTTP {st}")
                    elif st == 0:
                        add(findings, "medium", "request-failed", path, vname, f"{m} {u[:200]} failed (network error / blocked)")
                    elif st >= 500:
                        add(findings, "high", "api-server-error", path, vname, f"{m} {u[:200]} returned HTTP {st}")
                    elif st not in (401, 403):
                        add(findings, "medium", "api-client-error", path, vname, f"{m} {u[:200]} returned HTTP {st}")
                if not data["title"].strip():
                    add(findings, "low", "missing-title", path, vname, "Page has no <title> (bad for browser tabs and search engines)")
                if vname == "mobile" and not data["hasViewportMeta"]:
                    add(findings, "medium", "not-mobile-friendly", path, vname,
                        "No mobile viewport tag, so phones show a tiny zoomed-out desktop page "
                        "(add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">)", {"screenshot": shot})
                elif vname == "mobile" and data["overflowPx"] > 2 and data["contentOverflow"]:
                    add(findings, "medium", "mobile-overflow", path, vname,
                        f"Content is {data['overflowPx']}px wider than a phone screen, so the page is cut off or shrunk"
                        + (f" (widest element: {data['widestEl']})" if data["widestEl"] else ""), {"screenshot": shot})
                elif vname == "mobile" and data["overflowPx"] > 2:
                    add(findings, "low", "mobile-overlay-overflow", path, vname,
                        f"An overlay element (not visible content) is {data['overflowPx']}px wider than the phone screen, "
                        f"which can make the page render slightly zoomed out"
                        + (f" ({data['widestEl']})" if data["widestEl"] else ""), {"screenshot": shot})
                for src in data["brokenImgs"][:10]:
                    add(findings, "low", "broken-image", path, vname, f"Image does not load: {src[:200]}")
                for label in data["deadLinks"]:
                    add(findings, "low", "dead-link", path, vname, f"Link '{label}' goes nowhere (href='#' or empty)")
                for rx, msg in PLACEHOLDERS:
                    m = rx.search(data["text"])
                    if m:
                        s = max(0, m.start() - 40)
                        add(findings, "medium", "placeholder-text", path, vname, msg,
                            {"context": data["text"][s:m.end() + 40].replace("\n", " "), "screenshot": shot})
                if load_s > args.slow_s:
                    add(findings, "low", "slow-page", path, vname, f"Page took {load_s}s to load on {vname}")

                if vname == "desktop":
                    for link in data["links"]:
                        l = norm(link)
                        pu = urlparse(l)
                        if pu.scheme not in ("http", "https") or pu.netloc != origin:
                            continue
                        if SKIP_LINK.search(l) or STATIC_EXT.search(pu.path):
                            continue
                        if l not in seen:
                            seen.add(l)
                            queue.append(l)
                            from_links[l] = path
                page.close()
            pages_info.append(info)
        browser.close()

    # group identical problems that appear on many pages into one site-wide finding
    grouped, by_key = [], {}
    for f in findings:
        by_key.setdefault((f["kind"], f["detail"]), []).append(f)
    for (kind, detail), items in by_key.items():
        if len(items) >= 3:
            pages = [i["page"] for i in items]
            g = dict(items[0])
            g["page"] = f"{len(pages)} pages: " + ", ".join(pages[:6]) + (" ..." if len(pages) > 6 else "")
            g["viewports"] = sorted({v for i in items for v in i["viewports"]})
            grouped.append(g)
        else:
            grouped.extend(items)
    findings = grouped
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: (order[f["severity"]], f["kind"], f["page"]))
    result = {"base_url": base, "pages_crawled": len(visited), "pages_not_crawled": len(queue),
              "pages": pages_info, "findings": findings}
    with open(os.path.join(args.out, "smoke_findings.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in order}
    lines = [f"# Smoke crawl: {base}", "",
             f"Pages crawled: {len(visited)} (not reached: {len(queue)}) · "
             f"High: {counts['high']} · Medium: {counts['medium']} · Low: {counts['low']} · Info: {counts['info']}", ""]
    for f in findings:
        lines.append(f"- **{f['severity'].upper()}** [{f['kind']}] `{f['page']}` ({'/'.join(f['viewports'])}): {f['detail']}")
    with open(os.path.join(args.out, "smoke_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:3]))
    print(f"Details: {os.path.join(args.out, 'smoke_findings.json')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--out", default="qa-results")
    ap.add_argument("--routes", nargs="*", default=[], help="Extra paths to visit that aren't linked")
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--storage-state", help="Playwright storage state JSON for a logged-in session")
    ap.add_argument("--timeout", type=int, default=30, help="Seconds to wait for each page")
    ap.add_argument("--settle-ms", type=int, default=800, help="Extra wait after load for client rendering")
    ap.add_argument("--slow-s", type=float, default=5.0)
    ap.add_argument("--headed", action="store_true")
    crawl(ap.parse_args())


if __name__ == "__main__":
    main()
