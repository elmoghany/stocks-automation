"""CATALYST-MINER (2026-09-16): the timestamped event corpus and the
causal catalyst-feature function.

INPUT  data/news_hist/{SYM}/{YYYY-MM}.json      (plan/cat_news.py)
       data/filings_hist/{SYM}.json             (plan/cat_edgar.py)
       data/filings_hist/form4/{SYM}.json       (plan/cat_edgar.py --stage form4)
       data/filings_hist/earnings_rh.json       (Robinhood get_earnings_results,
                                                 191 wide names, 8 trailing qtrs)
       data/earnings_yf.json                    (older yfinance pull: ts + surprise%)
       data/earnings_dates.json                 (older pull: date + bmo/amc + beat)
OUTPUT data/massive/cat/events.pkl   {sym: {class: sorted float64 epoch-seconds}}
                                     + per-event payloads for earnings / form4 / sentiment
       data/massive/cat/corpus_report.json   coverage + class distribution

EVENT CLOCK (see cat_lib docstring): every event carries the public
timestamp of its source.  Earnings reports have only a slot: `am` ->
07:30 ET of the report date, `pm` -> 16:30 ET (after the close, so it
is usable from the NEXT session), unknown -> treated as `pm`
(conservative: later).

FEATURES `features_for(sym, dec_ts)` -> (names, matrix [n, NF]); every
value is a function of events with ts <= dec_ts ONLY.  Windows are
trailing 18h / 3d / 10d / 30d.  plan/cat_poison.py asserts nothing moves
when every event after dec_ts is mutated.
"""
import json
import pickle
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cat_lib as C                                           # noqa: E402

PR_PUBS = {"GlobeNewswire Inc.", "PR Newswire", "Business Wire", "ACCESSWIRE",
           "Accesswire", "Newsfile Corp.", "PRNewswire"}
NEWS_CLASSES = C.CLASSES                        # 16 taxonomy classes
FIL_CLASSES = ["8k_1.01", "8k_1.02", "8k_2.02", "8k_3.02", "8k_5.02",
               "8k_7.01", "8k_8.01", "8k_other", "424b", "s3", "s1",
               "sc13d", "sc13g", "f4_any", "f4_buy", "f4_sell", "f144",
               "10q", "nt10"]
META_CLASSES = ["news_all", "news_solo", "pr", "fil_all", "earn"]
ALL_CLASSES = NEWS_CLASSES + FIL_CLASSES + META_CLASSES

H = 3600.0
WIN = {"18h": 18 * H, "3d": 3 * 24 * H, "10d": 10 * 24 * H, "30d": 30 * 24 * H}
COUNT_CLASSES = NEWS_CLASSES + FIL_CLASSES + ["news_all", "news_solo", "pr", "fil_all"]
COUNT_WINS = ["18h", "3d", "10d"]
SENT_VAL = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}


def _ts(s):
    return C.utc_to_et(s).timestamp()


def _et(date, h, m):
    return C.decision_ts(date, f"{h:02d}:{m:02d}").timestamp()


# ------------------------------------------------------------ builders
def news_events(sym):
    d = C.NEWS / sym
    out = defaultdict(list)
    sent = []          # (ts, value)
    if not (d / "_done.json").exists():
        return out, sent, 0
    n = 0
    for f in sorted(d.glob("2*.json")):
        for a in C.read_json(f, []):
            if not a.get("ts"):
                continue
            t = _ts(a["ts"])
            n += 1
            out["news_all"].append(t)
            solo = (a.get("n_tickers") or 1) <= 3
            if solo:
                out["news_solo"].append(t)
            if a.get("pub") in PR_PUBS:
                out["pr"].append(t)
            for c in C.classify_text(a.get("title"), a.get("desc")):
                out[c].append(t)
            if a.get("sent") in SENT_VAL and solo:
                sent.append((t, SENT_VAL[a["sent"]]))
    return out, sent, n


def filing_events(sym):
    fi = C.read_json(C.FIL / f"{sym}.json")
    out = defaultdict(list)
    f4 = C.read_json(C.FIL / "form4" / f"{sym}.json", None)
    buys = []           # (ts, dollars)
    if not fi:
        return out, buys, 0
    for r in fi["filings"]:
        t = _ts(r["accepted"])
        form = r["form"]
        out["fil_all"].append(t)
        if form in ("8-K", "8-K/A"):
            items = [x.strip() for x in (r.get("items") or "").split(",") if x.strip()]
            hit = False
            for it in items:
                k = "8k_" + it
                if k in FIL_CLASSES:
                    out[k].append(t)
                    hit = True
            if not hit:
                out["8k_other"].append(t)
        for fam, fn in C.FORM_FAMILIES.items():
            if fn(form):
                key = {"424b": "424b", "s3": "s3", "s1": "s1", "sc13d": "sc13d",
                       "sc13g": "sc13g", "form4": "f4_any", "form144": "f144",
                       "10q": "10q", "nt": "nt10"}[fam]
                out[key].append(t)
                if key == "f4_any" and f4 is not None:
                    det = f4.get(r["acc"])
                    if det and not det.get("missing"):
                        b = sum(x["shares"] * x["px"] for x in det.get("txns", [])
                                if x["code"] == "P" and x["ad"] == "A")
                        s = sum(x["shares"] * x["px"] for x in det.get("txns", [])
                                if x["code"] == "S" and x["ad"] == "D")
                        if b > 0:
                            out["f4_buy"].append(t)
                            buys.append((t, b))
                        if s > 0:
                            out["f4_sell"].append(t)
    return out, buys, len(fi["filings"])


def earnings_events(sym, rh, yf, ed):
    """[(ts, surprise_pct or nan, sign or 0, src)] sorted, deduped by date."""
    ev = {}
    for r in rh.get(sym, []):
        if r.get("act") is None:
            continue
        est, act = r.get("est"), r["act"]
        if est is not None:
            pct = (act - est) / max(abs(est), 0.01) * 100.0
            sign = float(np.sign(act - est))
        else:
            pct, sign = np.nan, 0.0
        tim = r.get("timing") or "pm"
        ts = _et(r["date"], 7, 30) if tim == "am" else _et(r["date"], 16, 30)
        ev[r["date"]] = (ts, pct, sign, "rh")
    for r in yf.get(sym, []):
        d, clk = r["ts"][:10], r["ts"][11:]
        if d in ev or r.get("surprise") is None:
            continue
        am = clk < "09:30" and clk != "00:00"
        ts = _et(d, 7, 30) if am else _et(d, 16, 30)
        pct = float(r["surprise"])
        ev[d] = (ts, pct, float(np.sign(pct)), "yf")
    for r in ed.get(sym, []):
        d = r.get("date")
        if not d or d in ev or r.get("beat") is None:
            continue
        am = (r.get("hour") or "").lower() == "bmo"
        ts = _et(d, 7, 30) if am else _et(d, 16, 30)
        ev[d] = (ts, np.nan, 1.0 if r["beat"] else -1.0, "ed")
    return sorted(ev.values())


# ------------------------------------------------------------ corpus
def build(syms=None):
    syms = syms or C.all_syms()
    rh = C.read_json(C.FIL / "earnings_rh.json", {})
    yf = C.read_json(C.ROOT / "data" / "earnings_yf.json", {})
    ed = C.read_json(C.ROOT / "data" / "earnings_dates.json", {})
    corpus = {}
    rep = {"symbols": len(syms), "news_syms": 0, "news_articles": 0,
           "news_by_class": Counter(), "news_by_month": Counter(),
           "news_by_pub": Counter(), "fil_syms": 0, "fil_rows": 0,
           "fil_by_class": Counter(), "f4_detail_syms": 0,
           "earn_events": 0, "earn_src": Counter(), "earn_syms": 0}
    wide = set(C.wide_syms())
    for i, s in enumerate(syms):
        ne, sent, nn = news_events(s)
        fe, buys, nf = filing_events(s)
        ee = earnings_events(s, rh, yf, ed)
        ev = {}
        for c in ALL_CLASSES:
            arr = np.array(sorted(ne.get(c, []) + fe.get(c, [])), np.float64)
            ev[c] = arr
        ev["earn"] = np.array([e[0] for e in ee], np.float64)
        ev["_earn"] = np.array([[e[0], e[1], e[2]] for e in ee], np.float64).reshape(-1, 3)
        ev["_sent"] = np.array(sorted(sent), np.float64).reshape(-1, 2)
        ev["_buys"] = np.array(sorted(buys), np.float64).reshape(-1, 2)
        corpus[s] = ev
        if nn:
            rep["news_syms"] += 1
            rep["news_articles"] += nn
            for c in NEWS_CLASSES + ["news_solo", "pr"]:
                rep["news_by_class"][c] += len(ne.get(c, []))
        if nf:
            rep["fil_syms"] += 1
            rep["fil_rows"] += nf
            for c in FIL_CLASSES:
                rep["fil_by_class"][c] += len(fe.get(c, []))
        if (C.FIL / "form4" / f"{s}.json").exists():
            rep["f4_detail_syms"] += 1
        if ee:
            rep["earn_syms"] += 1
            rep["earn_events"] += len(ee)
            for e in ee:
                rep["earn_src"][e[3]] += 1
        if (i + 1) % 500 == 0:
            print(f"  corpus {i+1}/{len(syms)}", flush=True)
    # coverage by month, wide vs gap (news only)
    for s in syms:
        d = C.NEWS / s
        if not (d / "_done.json").exists():
            continue
        for f in d.glob("2*.json"):
            n = len(C.read_json(f, []))
            rep["news_by_month"][("wide:" if s in wide else "gap:") + f.stem] += n
        for a in (C.read_json(d / "2025-03.json", []) + C.read_json(d / "2026-03.json", [])):
            rep["news_by_pub"][a.get("pub")] += 1
    rep["news_by_class"] = dict(rep["news_by_class"].most_common())
    rep["fil_by_class"] = dict(rep["fil_by_class"].most_common())
    rep["news_by_month"] = dict(sorted(rep["news_by_month"].items()))
    rep["news_by_pub"] = dict(rep["news_by_pub"].most_common(15))
    rep["earn_src"] = dict(rep["earn_src"])
    with open(C.OUT / "events.pkl", "wb") as f:
        pickle.dump(corpus, f, protocol=4)
    C.write_json(C.OUT / "corpus_report.json", rep)
    print(json.dumps({k: v for k, v in rep.items()
                      if k not in ("news_by_month", "news_by_class", "fil_by_class")},
                     indent=1, default=str))
    return corpus, rep


_CORPUS = None


def corpus():
    global _CORPUS
    if _CORPUS is None:
        with open(C.OUT / "events.pkl", "rb") as f:
            _CORPUS = pickle.load(f)
    return _CORPUS


# ------------------------------------------------------------ features
def feature_names():
    names = []
    for c in COUNT_CLASSES:
        for w in COUNT_WINS:
            names.append(f"n_{c}_{w}")
    names += ["hrs_since_news", "hrs_since_pr", "hrs_since_fil", "hrs_since_earn",
              "sent_mean_3d", "sent_mean_10d", "sent_n_10d",
              "earn_fresh", "earn_surp_pct", "earn_surp_sign", "days_since_earn",
              "earn_surp_fresh_pct", "earn_surp_fresh_sign",
              "dilution_30d", "offer_news_30d", "insider_buy_30d", "insider_buy_usd_30d",
              "insider_sell_30d", "f13d_30d", "any_catalyst_18h"]
    return names


NF = len(feature_names())


def _count(arr, t, w):
    if arr.size == 0:
        return np.zeros(t.size, np.float32)
    hi = np.searchsorted(arr, t, "right")
    lo = np.searchsorted(arr, t - w, "right")
    return (hi - lo).astype(np.float32)


def _hrs_since(arr, t, cap=720.0):
    out = np.full(t.size, cap, np.float32)
    if arr.size == 0:
        return out
    i = np.searchsorted(arr, t, "right") - 1
    ok = i >= 0
    out[ok] = np.minimum(cap, (t[ok] - arr[i[ok]]) / H)
    return out


def features_for(sym, dec_ts):
    """dec_ts: float64 array of epoch seconds. -> float32 [n, NF]."""
    t = np.asarray(dec_ts, np.float64)
    ev = corpus().get(sym)
    X = np.zeros((t.size, NF), np.float32)
    if ev is None:
        X[:, feature_names().index("hrs_since_news")] = 720
        X[:, feature_names().index("hrs_since_pr")] = 720
        X[:, feature_names().index("hrs_since_fil")] = 720
        X[:, feature_names().index("hrs_since_earn")] = 720
        X[:, feature_names().index("days_since_earn")] = 90
        return X
    k = 0
    for c in COUNT_CLASSES:
        arr = ev[c]
        for w in COUNT_WINS:
            X[:, k] = _count(arr, t, WIN[w])
            k += 1
    X[:, k] = _hrs_since(ev["news_all"], t); k += 1
    X[:, k] = _hrs_since(ev["pr"], t); k += 1
    X[:, k] = _hrs_since(ev["fil_all"], t); k += 1
    X[:, k] = _hrs_since(ev["earn"], t); k += 1
    # sentiment means (solo articles only) over 3d / 10d
    st = ev["_sent"]
    for w in ("3d", "10d"):
        if st.shape[0]:
            hi = np.searchsorted(st[:, 0], t, "right")
            lo = np.searchsorted(st[:, 0], t - WIN[w], "right")
            cs = np.concatenate([[0.0], np.cumsum(st[:, 1])])
            n = hi - lo
            X[:, k] = np.where(n > 0, (cs[hi] - cs[lo]) / np.maximum(n, 1), 0.0)
            if w == "10d":
                X[:, k + 1] = n
        k += 1
    k += 1   # sent_n_10d written above
    # earnings
    ea = ev["_earn"]
    fresh = np.zeros(t.size, np.float32)
    surp = np.zeros(t.size, np.float32)
    sign = np.zeros(t.size, np.float32)
    dse = np.full(t.size, 90.0, np.float32)
    fsurp = np.zeros(t.size, np.float32)
    fsign = np.zeros(t.size, np.float32)
    if ea.shape[0]:
        i = np.searchsorted(ea[:, 0], t, "right") - 1
        ok = i >= 0
        ii = i[ok]
        age = (t[ok] - ea[ii, 0]) / (24 * H)
        dse[ok] = np.minimum(90.0, age)
        p = ea[ii, 1]
        p = np.where(np.isfinite(p), np.clip(p, -100, 100), 0.0)
        recent = age <= 10.0
        surp[ok] = np.where(recent, p, 0.0)
        sign[ok] = np.where(recent, ea[ii, 2], 0.0)
        fr = (t[ok] - ea[ii, 0]) <= WIN["18h"]
        fresh[ok] = fr
        fsurp[ok] = np.where(fr, p, 0.0)
        fsign[ok] = np.where(fr, ea[ii, 2], 0.0)
    X[:, k] = fresh; k += 1
    X[:, k] = surp; k += 1
    X[:, k] = sign; k += 1
    X[:, k] = dse; k += 1
    X[:, k] = fsurp; k += 1
    X[:, k] = fsign; k += 1
    dil = (_count(ev["424b"], t, WIN["30d"]) + _count(ev["s3"], t, WIN["30d"])
           + _count(ev["8k_3.02"], t, WIN["30d"]) + _count(ev["s1"], t, WIN["30d"]))
    X[:, k] = (dil > 0); k += 1
    X[:, k] = _count(ev["offering"], t, WIN["30d"]); k += 1
    X[:, k] = _count(ev["f4_buy"], t, WIN["30d"]); k += 1
    b = ev["_buys"]
    if b.shape[0]:
        hi = np.searchsorted(b[:, 0], t, "right")
        lo = np.searchsorted(b[:, 0], t - WIN["30d"], "right")
        cs = np.concatenate([[0.0], np.cumsum(b[:, 1])])
        X[:, k] = np.log1p(cs[hi] - cs[lo])
    k += 1
    X[:, k] = _count(ev["f4_sell"], t, WIN["30d"]); k += 1
    X[:, k] = _count(ev["sc13d"], t, WIN["30d"]); k += 1
    anyc = np.zeros(t.size, np.float32)
    for c in ("offering", "fda", "contract", "earnings", "mna", "analyst",
              "legal", "8k_1.01", "8k_2.02", "8k_3.02", "8k_8.01", "424b", "pr"):
        anyc += _count(ev[c], t, WIN["18h"])
    X[:, k] = (anyc > 0); k += 1
    assert k == NF, (k, NF)
    return X


if __name__ == "__main__":
    a = sys.argv
    which = a[a.index("--set") + 1] if "--set" in a else "all"
    syms = {"wide": C.wide_syms, "gap": C.gap_syms, "all": C.all_syms}[which]()
    build(syms)
