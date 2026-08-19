#!/usr/bin/env python3
"""check_stock.py -- resolve every buyable part to an MPN and price it live.

    python3 scripts/check_stock.py                 # query both APIs, rewrite resolved-mpns.json
    python3 scripts/check_stock.py --offline       # no network: value cross-check only
    python3 scripts/check_stock.py --check         # verify the committed file is current

WHAT IT JOINS

  scripts/mpn_overrides.json   HAND-MAINTAINED. Which part a refdes buys, and why. An
                               override beats a schematic link -- which is how ECO-8's
                               swaps survive the fact that the upstream schematic still
                               points at the parts they replaced.
  scripts/link_mpn.json        The upstream schematic's own per-symbol Digi-Key links,
                               resolved to MPNs once and frozen. For a generic value like
                               `1u` or `100k` this is the ONLY record of which part
                               MouseBiteLabs actually picked; the value alone matches
                               thousands.
  the board                    Which refs exist, what Value each carries, and -- through
                               scripts/bom_split.py -- whether it is bought at all.
  Digi-Key + Mouser            Everything VOLATILE: lifecycle status, stock, unit price,
                               the distributor's own part number.

WHY THE SPLIT. Frozen data and live data rot differently. A short-link's MPN does not
change; stock changes hourly. Freezing stock would produce a document that reads as
current and is not -- the failure SOLAR-GLOW's weekly canary exists to prevent, and the
reason its report says UNKNOWN rather than "current" when a probe cannot reach upstream.
This script does the same: a distributor that cannot be reached leaves its columns EMPTY
and says so, and never silently reports a part as unavailable because a socket timed out.

THE CROSS-CHECK IS THE POINT. A resolved MPN is only right if it buys the value the board
carries. The schematic's links are five years of edits deep and three of them buy a
different resistor than the PCB asks for -- see the report this prints. A distributor
ships what the NUMBER says, which is the same lesson as consistency check [6].

CREDENTIALS come from the environment: DIGIKEY_CLIENT_ID, DIGIKEY_CLIENT_SECRET,
MOUSER_PART_API_KEY. They are never written to any output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bom_split                                                 # noqa: E402
import kisexp                                                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDES = os.path.join(ROOT, "scripts", "mpn_overrides.json")
LINKMAP = os.path.join(ROOT, "scripts", "link_mpn.json")
OUT = os.path.join(ROOT, "pcbway-assembly", "resolved-mpns.json")
SCHEMATIC_ZIP = os.path.join(ROOT, "AGBM-01 (AA Batteries)", "AGBM-01_Design Files.zip")

DK_TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"
DK_SEARCH_URL = "https://api.digikey.com/products/v4/search/keyword"
MOUSER_URL = "https://api.mouser.com/api/v1/search/partnumber"


# --------------------------------------------------------------------------- schematic
def schematic_sources():
    """{refdes: short-link code} from the upstream schematic's Source property."""
    import zipfile
    out = {}
    try:
        z = zipfile.ZipFile(SCHEMATIC_ZIP)
    except OSError:
        return out
    for name in z.namelist():
        if not name.endswith(".kicad_sch"):
            continue
        t = z.read(name).decode("utf-8", "replace")
        for m in re.finditer(r"\(symbol\b", t):
            st = m.start()
            en = t.find("\n\t)\n", st)
            blk = t[st:en if en > 0 else st + 9000]
            ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
            src = re.search(r'\(property "Source" "([^"]*)"', blk)
            if ref and src and "/short/" in src.group(1):
                out.setdefault(ref.group(1), src.group(1).rsplit("/", 1)[-1])
    return out


# ------------------------------------------------------------------------------- APIs
class Distributors:
    """Both APIs, with one rule: an unreachable distributor reports NOTHING, never zero."""

    def __init__(self, offline=False):
        self.offline = offline
        self.dk_token = None
        self.dk_up = self.mo_up = not offline
        self.notes = []
        self.calls = 0
        if offline:
            return
        try:
            d = urllib.parse.urlencode({
                "client_id": os.environ["DIGIKEY_CLIENT_ID"],
                "client_secret": os.environ["DIGIKEY_CLIENT_SECRET"],
                "grant_type": "client_credentials"}).encode()
            r = urllib.request.urlopen(urllib.request.Request(
                DK_TOKEN_URL, data=d,
                headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=30)
            self.dk_token = json.load(r)["access_token"]
        except (KeyError, OSError, ValueError) as e:
            self.dk_up = False
            self.notes.append(f"Digi-Key UNREACHABLE ({type(e).__name__}) -- its columns "
                              f"are blank below, which means UNKNOWN, not unavailable")
        if not os.environ.get("MOUSER_PART_API_KEY"):
            self.mo_up = False
            self.notes.append("Mouser key not set -- its columns are blank, meaning UNKNOWN")

    def digikey(self, mpn):
        if not self.dk_up:
            return None
        body = json.dumps({"Keywords": mpn, "Limit": 5, "Offset": 0}).encode()
        req = urllib.request.Request(DK_SEARCH_URL, data=body, headers={
            "Authorization": f"Bearer {self.dk_token}",
            "X-DIGIKEY-Client-Id": os.environ["DIGIKEY_CLIENT_ID"],
            "Content-Type": "application/json",
            "X-DIGIKEY-Locale-Site": "US",
            "X-DIGIKEY-Locale-Language": "en",
            "X-DIGIKEY-Locale-Currency": "USD"})
        try:
            j = json.load(urllib.request.urlopen(req, timeout=45))
        except (OSError, ValueError) as e:
            self.notes.append(f"Digi-Key query for {mpn} failed: {type(e).__name__}")
            return None
        finally:
            self.calls += 1
        # EXACT match only. A keyword search happily returns a near-neighbour, and
        # accepting one is precisely how a BOM ends up naming a part nobody chose.
        for p in j.get("Products") or []:
            if (p.get("ManufacturerProductNumber") or "").upper() == mpn.upper():
                var = (p.get("ProductVariations") or [{}])[0]
                return {
                    "mfr": (p.get("Manufacturer") or {}).get("Name", ""),
                    "desc": (p.get("Description") or {}).get("DetailedDescription", ""),
                    "status": (p.get("ProductStatus") or {}).get("Status", ""),
                    "stock": p.get("QuantityAvailable"),
                    "price1": p.get("UnitPrice"),
                    "dkpn": var.get("DigiKeyProductNumber", ""),
                    "lead_weeks": p.get("ManufacturerLeadWeeks", ""),
                    "eol": bool(p.get("EndOfLife")),
                    "discontinued": bool(p.get("Discontinued")),
                    "datasheet": p.get("DatasheetUrl", ""),
                }
        return {"__nomatch__": True}

    def mouser(self, mpn):
        if not self.mo_up:
            return None
        body = json.dumps({"SearchByPartRequest": {
            "mouserPartNumber": mpn, "partSearchOptions": "Exact"}}).encode()
        key = urllib.parse.quote(os.environ["MOUSER_PART_API_KEY"], safe="")
        req = urllib.request.Request(f"{MOUSER_URL}?apiKey={key}", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Accept": "application/json"})
        # Mouser rate-limits, and a throttled request must not be read as "not stocked".
        # One retry with backoff, then an EXPLICIT unreachable marker -- never a silent
        # zero. This was not theoretical: the first live run reported R26's 33k resistor
        # as absent from Mouser while Mouser had 95,136 of them.
        j = None
        for attempt in (0, 1, 2):
            try:
                j = json.load(urllib.request.urlopen(req, timeout=45))
                break
            except (OSError, ValueError) as e:
                last = e
                time.sleep(1.5 * (attempt + 1))
            finally:
                self.calls += 1
        if j is None:
            self.notes.append(f"Mouser unreachable for {mpn}: {type(last).__name__}")
            return {"__unreachable__": True}
        if j.get("Errors"):
            self.notes.append(f"Mouser error for {mpn}: {j['Errors']}")
            return {"__unreachable__": True}
        for p in ((j.get("SearchResults") or {}).get("Parts") or []):
            if (p.get("ManufacturerPartNumber") or "").upper() == mpn.upper():
                pb = (p.get("PriceBreaks") or [{}])[0]
                return {
                    "mfr": p.get("Manufacturer", ""),
                    "stock": int(p["AvailabilityInStock"])
                    if (p.get("AvailabilityInStock") or "").isdigit() else None,
                    "price1": pb.get("Price", ""),
                    "mopn": p.get("MouserPartNumber", ""),
                    "lifecycle": p.get("LifecycleStatus") or "",
                }
        return {"__nomatch__": True}


# ------------------------------------------------------------------------------ verify
_UNIT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "": 1.0, "k": 1e3, "M": 1e6}


def as_number(v):
    """'4.7k' -> 4700.0, '3300p' -> 3.3e-09, '0.1u' -> 1e-07. None if not a value."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([pnumkM]?)(?:[FRΩ]|Ohm)?", (v or "").strip())
    if not m:
        return None
    return float(m.group(1)) * _UNIT[m.group(2)]


def mpn_value(mpn):
    """The value a YAGEO RC_L or KEMET C-series ordering code actually buys."""
    m = re.fullmatch(r"RC\d{4}[FJ]R-\d{2}(\d+[RKM]\d*)L", mpn or "")
    if m:
        code = m.group(1)
        for ch, mult in (("R", 1.0), ("K", 1e3), ("M", 1e6)):
            if ch in code:
                a, b = code.split(ch)
                return float(f"{a}.{b}" if b else a) * mult
        return float(code)
    m = re.fullmatch(r"C\d{4}C(\d)(\d)(\d)[JKM][15][GR]AC(?:TU|7186)", mpn or "")
    if m:
        return float(m.group(1) + m.group(2)) * (10 ** int(m.group(3))) * 1e-12
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true", help="skip both APIs")
    ap.add_argument("--check", action="store_true",
                    help="verify the committed file is current; write nothing")
    a = ap.parse_args()

    board = kisexp.load(f"{bom_split.ZIP}::{bom_split.MEMBER}")
    fps = kisexp.by_ref(board)
    asm, hand, _none, _cpl, _probs = bom_split.build()
    buyable = {r for line in asm + hand for r in line["refs"]}

    ov = json.load(open(OVERRIDES, encoding="utf-8"))["entries"]
    # THE LEDGER MAY NOT ASSERT AVAILABILITY. A hand-written "out of stock, 10,000 due in
    # December" is true for about a week and then quietly lies, and it sits right next to a
    # live block that says otherwise. Dated observations are fine -- "192,278 in stock,
    # verified 2026-08-19" carries its own expiry -- so the rule is: any availability claim
    # must name the day it was checked. This fired the first time it existed: a swapped
    # capacitor line kept the previous part's "OUT OF STOCK" flag and shipped it into the
    # assembly BOM beside the new part, which is in stock.
    stale = []
    for e in ov:
        for k in ("note", "flag", "eco", "alternate"):
            v = e.get(k) or ""
            if re.search(r"in stock|out of stock|due \d|expected \d|week lead|\bwk lead\b", v, re.I) \
                    and not re.search(r"verified 20\d\d-\d\d-\d\d|20\d\d-\d\d-\d\d\)", v):
                stale.append(f"{','.join(e['refs'])}.{k}")
    if stale:
        sys.exit("FAIL: scripts/mpn_overrides.json asserts availability without a date in "
                 + ", ".join(stale) + ". Availability is fetched live -- either delete the "
                 "claim or date it ('verified YYYY-MM-DD').")
    over = {r: e for e in ov for r in e["refs"]}
    links = json.load(open(LINKMAP, encoding="utf-8"))["links"]
    srcs = schematic_sources()

    # --- resolve every buyable ref to an MPN, and say where the answer came from -----
    chosen = {}
    for ref in sorted(buyable):
        if ref in over:
            # An override with an EMPTY mpn is a deliberate "there is no distributor part"
            # -- salvage, or an aftermarket item. That is an answer, not a gap, and it must
            # not read as unresolved.
            chosen[ref] = (over[ref]["mpn"] or None, "override", over[ref])
        elif ref in srcs and srcs[ref] in links:
            L = links[srcs[ref]]
            chosen[ref] = (L["mpn"], f"schematic link /short/{srcs[ref]}", L)
        else:
            chosen[ref] = (None, "unresolved", {})

    # --- the cross-check: does the MPN buy the value the BOARD carries? -------------
    conflicts = []
    for ref, (mpn, how, meta) in sorted(chosen.items()):
        # An override that carries a flag naming the conflict IS the record of it, so it
        # keeps being reported -- a resolved conflict that stops being visible is how the
        # decision gets forgotten and then re-made by whoever places the order.
        if how == "override" and "SCHEMATIC/PCB CONFLICT" in (meta.get("flag") or ""):
            sch = re.search(r"schematic SAYS? (\S+)", meta["flag"]) or \
                re.search(r"SCHEMATIC says (\S+)", meta["flag"])
            conflicts.append((ref, fps[ref].value if ref in fps else "?", mpn,
                              "follows the BOARD; the schematic disagrees (ledgered)"))
            continue
        if not mpn or how == "override":
            continue                       # any other override is a settled decision
        want = as_number(fps[ref].value) if ref in fps else None
        got = mpn_value(mpn)
        if want is not None and got is not None and abs(want - got) > max(want, got) * 1e-6:
            conflicts.append((ref, fps[ref].value, mpn, how))

    unresolved = sorted(r for r, (m, h, _x) in chosen.items() if not m and h != "override")
    no_part = sorted(r for r, (m, h, _x) in chosen.items() if not m and h == "override")
    print(f"{len(buyable)} buyable refs: "
          f"{len(buyable) - len(unresolved) - len(no_part)} resolved to an MPN, "
          f"{len(no_part)} with none by decision, {len(unresolved)} unresolved")
    if unresolved:
        print("  unresolved: " + ", ".join(unresolved))
    if no_part:
        print(f"  {len(no_part)} with no distributor part BY DECISION (salvage or "
              f"aftermarket): " + ", ".join(no_part))
    if conflicts:
        print(f"\n{len(conflicts)} ref(s) where the schematic and the PCB disagree about the "
              f"value.\nA distributor ships what the NUMBER says, so this has to be settled "
              f"before an order:\n")
        for ref, bv, mpn, how in conflicts:
            print(f"   {ref:5s} board Value {bv:9s} -> {mpn:20s} ({how})")

    dist = Distributors(offline=a.offline)
    for n in dist.notes:
        print("  NOTE: " + n)

    # --- group by MPN and price it once ---------------------------------------------
    by_mpn = {}
    for ref, (mpn, how, meta) in chosen.items():
        if mpn:
            by_mpn.setdefault(mpn, {"refs": [], "how": how, "meta": meta})["refs"].append(ref)

    entries = []
    for mpn in sorted(by_mpn):
        g = by_mpn[mpn]
        dk = dist.digikey(mpn)
        mo = dist.mouser(mpn)
        if not a.offline:
            time.sleep(0.35)               # be polite; both APIs are rate-limited
        e = {"refs": sorted(g["refs"]),
             "value": fps[g["refs"][0]].value if g["refs"][0] in fps else "",
             "mpn": mpn,
             "mfr": (g["meta"].get("mfr") or (dk or {}).get("mfr") or (mo or {}).get("mfr") or ""),
             "resolved_from": g["how"]}
        for k in ("eco", "flag", "note", "alternate"):
            if g["meta"].get(k):
                e[k] = g["meta"][k]
        if dk and not dk.get("__nomatch__"):
            e["digikey"] = {k: dk[k] for k in
                            ("dkpn", "status", "stock", "price1", "lead_weeks",
                             "eol", "discontinued")}
            e["desc"] = dk["desc"]
            e["datasheet"] = dk["datasheet"]
        elif dk:
            e["digikey"] = {"error": "no exact match at Digi-Key for this MPN"}
        if mo and not mo.get("__nomatch__") and not mo.get("__unreachable__"):
            e["mouser"] = {k: mo[k] for k in ("mopn", "stock", "price1", "lifecycle")}
        elif mo and mo.get("__unreachable__"):
            e["mouser"] = {"error": "UNKNOWN -- Mouser could not be reached for this MPN. "
                                    "This is not a stock figure of zero."}
        elif mo:
            e["mouser"] = {"error": "no exact match at Mouser for this MPN"}
        entries.append(e)

    doc = {
        "_comment": ("GENERATED by scripts/check_stock.py -- do not edit. Curated decisions "
                     "live in scripts/mpn_overrides.json; the upstream schematic's own "
                     "Digi-Key links live in scripts/link_mpn.json. Stock and price are a "
                     "SNAPSHOT and rot immediately; a distributor that could not be reached "
                     "leaves its block ABSENT, which means UNKNOWN, never zero."),
        "generated_utc": time.strftime("%Y-%m-%d", time.gmtime()) if not a.offline else "",
        "api_calls": dist.calls,
        "buyable_refs": len(buyable),
        "unresolved_refs": unresolved,
        "no_distributor_part": no_part,
        "value_conflicts": [{"ref": r, "board_value": v, "link_buys": m, "via": h}
                            for r, v, m, h in conflicts],
        "distributor_notes": dist.notes,
        "entries": entries,
    }
    if a.check:
        try:
            have = json.load(open(OUT, encoding="utf-8"))
        except (OSError, ValueError) as e:
            sys.exit(f"FAIL: cannot read {OUT}: {e}")
        drift = [k for k in ("entries", "unresolved_refs", "value_conflicts")
                 if json.dumps(have.get(k), sort_keys=True) != json.dumps(doc[k], sort_keys=True)]
        # stock and price move on their own; only the structural half is gated
        if drift:
            sys.exit(f"FAIL: {OUT} is stale in {drift} -- run scripts/check_stock.py")
        print("ok: the committed file matches a fresh resolution")
        return 0
    if a.offline:
        print("\n--offline: nothing written (no live data to write)")
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(f"\nwrote {os.path.relpath(OUT, ROOT)}: {len(entries)} lines, "
          f"{dist.calls} API calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
