"""CATALYST-MINER (2026-09-16): shared paths, symbol lists, the catalyst
taxonomy and the causal event clock.

THE ONE RULE.  An event may be used at decision minute m on date D only
if its PUBLIC timestamp is <= (D, m) in New York time.  Every feature in
this line is a function of events with ts <= decision ts, and the poison
test (plan/cat_poison.py) mutates every event strictly after the decision
minute and asserts not one feature moves.

Timestamps kept per source
  * Polygon news      `published_utc`               (publisher's clock)
  * EDGAR filings     `acceptanceDateTime` (UTC)    -- the SEC's clock.
    Filings accepted after 17:30 ET are disseminated at 06:00 ET the
    next business day; since no decision minute here lies between 17:30
    and 06:00 the acceptance time is exactly the causal time for every
    decision this line makes.
  * Earnings          report date + am/pm slot      -- an `am` report is
    usable from 09:35 of its date, a `pm` report from the NEXT session's
    open.  (Robinhood carries no clock, only the slot.)

Nothing in this module reads a bar or a label.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                              # day-trading/
sys.path.insert(0, str(ROOT.parent))            # for shared.*
ET = ZoneInfo("America/New_York")
UTC = timezone.utc

NEWS = ROOT / "data" / "news_hist"
FIL = ROOT / "data" / "filings_hist"
OUT = ROOT / "data" / "massive" / "cat"
for _p in (NEWS, FIL, OUT):
    _p.mkdir(parents=True, exist_ok=True)

WIN_LO = "2024-08-01"      # corpus start (10/30-day trailing windows need it)
WIN_HI = "2026-09-01"      # corpus end (exclusive)
STUDY_LO = "2024-10-22"    # first decision date (rl2 universe)
STUDY_HI = "2026-08-06"    # last decision date

SEC_UA = "cornell-stocks-automation research m.osama.elmoghany@gmail.com"


# ------------------------------------------------------------ symbols
def wide_syms():
    """The 191 names of the causal wide universe (plan/rl2, wn table)."""
    z = np.load(ROOT / "data" / "massive" / "wn" / "table.npz",
                allow_pickle=False)
    return sorted(str(s) for s in z["syms"])


def gap_syms():
    """The 2,836 names of the +10% gapper pool (plan/cm_rows.py rows_gap)."""
    z = np.load(ROOT / "data" / "massive" / "cm" / "rows_gap.npz",
                allow_pickle=False)
    return sorted(set(str(s) for s in z["syms"]))


def all_syms():
    w = wide_syms()
    return w + [s for s in gap_syms() if s not in set(w)]


def cik_map():
    ct = json.loads((ROOT / "data" / "edgar" / "company_tickers.json")
                    .read_text(encoding="utf-8"))
    return {v["ticker"]: int(v["cik_str"]) for v in ct.values()}


# ------------------------------------------------------------ clocks
def utc_to_et(s):
    """'2025-03-10T20:05:44.000Z' / '...Z' -> aware ET datetime."""
    s = s.rstrip("Z")
    if "." in s:
        s = s.split(".")[0]
    return datetime.fromisoformat(s).replace(tzinfo=UTC).astimezone(ET)


def et_minutes(dt):
    """Aware datetime -> float minutes since epoch in ET wall clock terms
    (a monotone key that compares like the real instant)."""
    return dt.timestamp() / 60.0


def decision_ts(date, hhmm):
    """(D, 'HH:MM') -> aware ET datetime of that decision minute."""
    y, m, d = (int(x) for x in date.split("-"))
    h, mi = (int(x) for x in hhmm.split(":"))
    return datetime(y, m, d, h, mi, tzinfo=ET)


# ------------------------------------------------------------ taxonomy
# Rule-based catalyst classes over headline + description.  Order matters
# only for the `primary` label; an article can carry several flags.
# Every pattern is lower-case and matched against lower-cased text.
TAXONOMY = {
    "offering": [
        "public offering", "registered direct", "private placement",
        "at-the-market", "at the market offering", "atm program",
        "pricing of", "prices $", "prices upsized", "prices public",
        "announces pricing", "underwritten offering", "secondary offering",
        "shelf registration", "convertible notes offering",
        "convertible senior notes", "warrant", "equity line",
        "dilut", "share issuance", "units offering", "pipe financing",
        "closing of", "closes $", "closes public offering",
        "reverse stock split", "reverse split", "stock split",
    ],
    "fda": [
        "fda", "pdufa", "breakthrough therapy", "orphan drug", "phase 3",
        "phase 2", "phase 1", "phase iii", "phase ii", "clinical trial",
        "topline", "top-line", "primary endpoint", "ema approval",
        "marketing authorization", "510(k)", "de novo", "ce mark",
        "nda ", "bla ", "ind ", "clinical hold", "complete response letter",
        "fast track", "approval", "approves",
    ],
    "contract": [
        "contract", "award", "awarded", "partnership", "collaboration",
        "agreement with", "selected by", "purchase order", "order from",
        "multi-year", "deploy", "wins ", "win ", "strategic alliance",
        "license agreement", "licensing agreement", "supply agreement",
        "master services agreement", "definitive agreement",
        "letter of intent", "memorandum of understanding", "mou ",
        "launches", "launch of", "unveils", "introduces",
    ],
    "earnings": [
        "earnings", "quarterly results", "financial results", "q1 ", "q2 ",
        "q3 ", "q4 ", "first quarter", "second quarter", "third quarter",
        "fourth quarter", "full year", "fiscal 20", "eps", "revenue",
        "guidance", "outlook", "beats", "misses", "tops estimates",
        "lags estimates", "surpass", "reports record", "reports results",
        "preliminary results", "preannounce",
    ],
    "guidance_up": ["raises guidance", "raises outlook", "raised guidance",
                    "raises full-year", "raises fy", "boosts guidance",
                    "increases guidance", "above guidance", "raises its"],
    "guidance_down": ["cuts guidance", "lowers guidance", "lowers outlook",
                      "cuts outlook", "reduces guidance", "withdraws guidance",
                      "below guidance", "slashes"],
    "mna": [
        "acquire", "acquisition", "to be acquired", "merger", "merge",
        "buyout", "takeover", "take-private", "go private", "definitive merger",
        "tender offer", "all-cash", "per share in cash", "combination with",
        "strategic alternatives", "exploring sale", "unsolicited",
    ],
    "analyst": [
        "upgrade", "downgrade", "initiat", "price target", "raises pt",
        "lowers pt", "reiterat", "overweight", "underweight", "outperform",
        "underperform", "buy rating", "sell rating", "neutral rating",
        "analyst", "zacks rank",
    ],
    "index": [
        "russell 2000", "russell 3000", "s&p 500", "s&p smallcap",
        "s&p midcap", "index inclusion", "added to", "joins the",
        "to join s&p", "set to join", "nasdaq-100", "index rebalanc",
    ],
    "halt": ["halt", "halted", "resume", "resumption of trading",
             "trading resumes", "circuit breaker"],
    "legal": [
        "lawsuit", "class action", "investigation", "investigat", "subpoena",
        "securities fraud", "shareholder alert", "deadline alert",
        "law firm", "llp", "pomerantz", "rosen law", "levi & korsinsky",
        "bragar eagel", "glancy", "schall law", "kessler topaz",
        "sec charges", "doj", "settlement", "verdict", "litigation",
        "short report", "hindenburg", "muddy waters", "citron", "fuzzy panda",
    ],
    "insider": ["insider buy", "insider purchase", "buys shares", "bought shares",
                "director buys", "ceo buys", "10% owner", "share repurchase",
                "buyback", "repurchase program", "insider selling",
                "sells shares", "sold shares"],
    "management": ["appoints", "names new", "resigns", "resignation",
                   "steps down", "chief executive officer", "chief financial officer",
                   "new ceo", "new cfo", "board of directors", "departure"],
    "delisting": ["delist", "non-compliance", "nasdaq notice", "minimum bid",
                  "deficiency", "going concern", "bankruptcy", "chapter 11",
                  "default", "forbearance", "restructuring support"],
    "crypto_ai": ["bitcoin", "crypto", "blockchain", "ai ", "artificial intelligence",
                  "data center", "gpu", "nvidia"],
    "macro_list": ["stocks that hit", "52-week", "top gainers", "top losers",
                   "biggest movers", "premarket movers", "midday movers",
                   "stocks moving", "why is", "why are", "what's going on with",
                   "shares are trading", "stock is skyrocketing", "stock is soaring",
                   "stock is plunging", "stock is sinking", "stock is falling",
                   "stock is jumping", "stock is rising", "shares jump", "shares fall",
                   "shares surge", "shares plunge", "soaring today", "plunging today",
                   "crashed today", "jumped today", "popped today", "dropped today"],
}
CLASSES = list(TAXONOMY)

# EDGAR forms and 8-K items of interest
FORM_CLASSES = {
    "8k_1.01": ("8-K", "1.01"),    # material definitive agreement
    "8k_1.02": ("8-K", "1.02"),    # termination of material agreement
    "8k_2.02": ("8-K", "2.02"),    # results of operations (earnings)
    "8k_3.02": ("8-K", "3.02"),    # unregistered sales of equity = dilution
    "8k_3.01": ("8-K", "3.01"),    # delisting notice
    "8k_4.02": ("8-K", "4.02"),    # non-reliance on prior financials
    "8k_5.02": ("8-K", "5.02"),    # officer/director changes
    "8k_7.01": ("8-K", "7.01"),    # Reg FD
    "8k_8.01": ("8-K", "8.01"),    # other events
    "8k_2.01": ("8-K", "2.01"),    # completion of acquisition/disposition
    "8k_1.03": ("8-K", "1.03"),    # bankruptcy
}
FORM_FAMILIES = {
    "424b": lambda f: f.startswith("424B"),
    "s3": lambda f: f.startswith("S-3") or f.startswith("F-3"),
    "s1": lambda f: f.startswith("S-1") or f.startswith("F-1"),
    "sc13d": lambda f: f.startswith("SC 13D") or f.startswith("SCHEDULE 13D"),
    "sc13g": lambda f: f.startswith("SC 13G") or f.startswith("SCHEDULE 13G"),
    "form4": lambda f: f in ("4", "4/A"),
    "form144": lambda f: f.startswith("144"),
    "10q": lambda f: f in ("10-Q", "10-Q/A", "10-K", "10-K/A", "20-F", "40-F", "6-K"),
    "nt": lambda f: f.startswith("NT 10"),
}


def classify_text(title, desc=""):
    """-> set of class names hit by the rule taxonomy."""
    t = " " + (title or "").lower() + " || " + (desc or "").lower() + " "
    hit = set()
    for c, pats in TAXONOMY.items():
        for p in pats:
            if p in t:
                hit.add(c)
                break
    return hit


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, default=str), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))
