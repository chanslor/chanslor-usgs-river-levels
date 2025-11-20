#!/usr/bin/env python3
"""
streambeam_multi_scrape.py (v2.4)

Fix: previous build over-escaped regex patterns (\\s instead of \s), causing parse failures.
This version corrects all regex strings and keeps robustness features.

- Per-site zero offset + floor_at_zero
- Robust fetch (25s timeout, retries, identity encoding)
- Text normalization + permissive fallback
- --debug and --dump-dir for diagnostics
"""

import argparse
import concurrent.futures
import html as html_mod
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

DEFAULT_URL_TMPL = "https://www.streambeam.net/Home/Gauge?siteID={site_id}"

LAST_READING_REGEX = re.compile(
    r"Last\s*Reading\s*:?\s*([\-\d\.,]+)\s*\bft\b\s*(?:at|@)?\s*([^\n]+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

def fetch(url: str, timeout: int = 25, retries: int = 3, backoff_base: float = 0.9) -> str:
    last_exc = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Encoding": "identity",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Connection": "close",
                    "Referer": "https://www.streambeam.net/Gauges",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except Exception as e:
            last_exc = e
            if attempt < retries - 1:
                sleep_s = (backoff_base ** attempt) * 1.5 + 0.6
                time.sleep(sleep_s)
            else:
                raise

def html_to_text(html: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = html_mod.unescape(txt)
    txt = txt.replace("\xa0", " ")
    txt = re.sub(r"[ \t\r\f\v]+", " ", txt)
    txt = re.sub(r"\n\s+", "\n", txt)
    return txt

def _looks_like_interstitial(text: str) -> bool:
    t = text.lower()
    return any(needle in t for needle in [
        "just a moment", "checking your browser", "access denied", "rate limit", "robot check",
        "cloudflare", "ddos-guard", "attention required"
    ])

def _fallback_parse_raw_html(html: str):
    m = re.search(
        r"Last\s*Reading\s*:?.{0,40}?([\d\.-]+)\s*\bft\b.{0,160}?\b(?:at|@)\b\s*([^<\n]+)",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", ""))
    except Exception:
        return None
    ts = m.group(2).strip()
    return {"raw_value_ft": val, "observed_at_local": ts, "units": "ft"}

def parse_last_reading(html: str, *, debug=False):
    text = html_to_text(html)
    if _looks_like_interstitial(text):
        if debug:
            return None, text[:500]
        return None, None
    m = LAST_READING_REGEX.search(text)
    if not m:
        fallback = _fallback_parse_raw_html(html)
        if fallback:
            return fallback, None
        if debug:
            idx = text.lower().find("last reading")
            context = text[max(0, idx-200): idx+240] if idx != -1 else text[:360]
            return None, context
        return None, None
    num_str = m.group(1).replace(",", "").strip()
    try:
        value_ft = float(num_str)
    except ValueError:
        return None, None
    observed_at_local = m.group(2).strip()
    return {"raw_value_ft": value_ft, "observed_at_local": observed_at_local, "units": "ft"}, None

def read_conf(path: str):
    with open(path, "r") as f:
        data = json.load(f)
    timeout = int(data.get("timeout_seconds", 25))
    defaults = data.get("adjustment_defaults", {})
    sites = data.get("sites", [])
    def_zero = float(defaults.get("zero_offset_ft", 0.0))
    def_floor = bool(defaults.get("floor_at_zero", True))
    return timeout, def_zero, def_floor, sites

def build_url(entry):
    if "url" in entry and entry["url"]:
        return entry["url"]
    if "site_id" in entry and entry["site_id"]:
        return DEFAULT_URL_TMPL.format(site_id=entry["site_id"])
    return None

def apply_adjustment(raw_ft: float, zero_offset_ft: float, floor_at_zero: bool) -> float:
    adj = raw_ft - zero_offset_ft
    if floor_at_zero:
        adj = max(0.0, adj)
    return adj

def _safe_write_dump(dump_dir: Path, name: str, html: str):
    dump_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:80]
    p = dump_dir / f"{safe}.html"
    p.write_text(html, encoding="utf-8", errors="ignore")
    return str(p)

def scrape_one(entry, timeout, def_zero, def_floor, debug=False, dump_dir: Optional[Path] = None):
    name = entry.get("name") or entry.get("site_id") or entry.get("url") or "unknown"
    url = build_url(entry)
    zero_offset_ft = float(entry.get("zero_offset_ft", def_zero))
    floor_at_zero = bool(entry.get("floor_at_zero", def_floor))

    if not url:
        return {"name": name, "ok": False, "error": "No url or site_id provided."}

    try:
        html = fetch(url, timeout=timeout)
        parsed, context = parse_last_reading(html, debug=debug)
        if not parsed:
            err = "Could not parse Last Reading."
            if dump_dir is not None:
                dumped = _safe_write_dump(dump_dir, name, html)
                err += f" Dumped HTML to: {dumped}."
            if context and debug:
                err += f" Context: {context.strip()}"
            return {"name": name, "ok": False, "url": url, "error": err}
        raw_ft = parsed["raw_value_ft"]
        adjusted_ft = apply_adjustment(raw_ft, zero_offset_ft, floor_at_zero)
        return {
            "name": name,
            "ok": True,
            "url": url,
            "observed_at_local": parsed["observed_at_local"],
            "units": "ft",
            "raw_value_ft": raw_ft,
            "zero_offset_ft": zero_offset_ft,
            "floor_at_zero": floor_at_zero,
            "adjusted_ft": adjusted_ft
        }
    except Exception as e:
        return {"name": name, "ok": False, "url": url, "error": str(e)}

def print_table(rows):
    name_w = max(4, max(len(r["name"]) for r in rows))
    ft_w = 9
    time_w = max(4, max(len(r.get("observed_at_local","")) for r in rows))
    header = f'{"Name".ljust(name_w)}  {"Adj ft".rjust(ft_w)}  {"Observed (local time)".ljust(time_w)}'
    print(header)
    print("-" * len(header))
    for r in rows:
        if r.get("ok"):
            feet = f'{r["adjusted_ft"]:.2f}'
            tstr = r.get("observed_at_local","")
            print(f'{r["name"].ljust(name_w)}  {feet.rjust(ft_w)}  {tstr}')
        else:
            print(f'{r["name"].ljust(name_w)}  {"ERR".rjust(ft_w)}  {r.get("error","")}')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", default="streambeam_sites.conf.json", help="Path to JSON conf file")
    ap.add_argument("--json", action="store_true", help="Output JSON (includes raw & adjusted ft)")
    ap.add_argument("--workers", type=int, default=2, help="Concurrent workers")
    ap.add_argument("--debug", action="store_true", help="Include parse context on errors")
    ap.add_argument("--dump-dir", default="", help="Directory to save raw HTML on failures (e.g., /tmp/sb_dumps)")
    args = ap.parse_args()

    try:
        timeout, def_zero, def_floor, sites = read_conf(args.conf)
    except Exception as e:
        print(f"ERROR: Could not read conf: {e}", file=sys.stderr)
        sys.exit(2)

    if not sites:
        print("ERROR: No sites in conf.", file=sys.stderr)
        sys.exit(2)

    dump_dir = Path(args.dump_dir) if args.dump_dir else None

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(scrape_one, s, timeout, def_zero, def_floor, args.debug, dump_dir) for s in sites]
        for fut in concurrent.futures.as_completed(futs):
            results.append(fut.result())

    # Keep original order
    name_to_result = {r["name"]: r for r in results}
    ordered = [name_to_result.get(s.get("name") or s.get("site_id") or s.get("url") or "unknown") for s in sites]

    if args.json:
        print(json.dumps(ordered, indent=2))
    else:
        print_table(ordered)

if __name__ == "__main__":
    main()
