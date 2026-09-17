"""HARNESS-DIAGNOSTIC control 3: reconcile the harness against the LIVE ledger.

The live paper campaign (data/paper_days/*.json) books every round trip at
Robinhood prices, with ladder sweeps against displayed depth and an explicit
fill-realism note per fill.  That is the only ground truth this project has
about what a fill is worth.  If the harness, re-pricing the SAME entries and
exits off the Massive minute tape with the flat 10 bps/side ladder, comes out
SYSTEMATICALLY BELOW the live book, the harness is biased against us -- that
is hypothesis (A), and the size of the gap is the size of the bias.  If it
matches or comes out ABOVE, the harness is not what is losing the money.

Only 20 completed round trips exist (19 scored days, one ticket most days --
the cash account holds one position at a time).  The mandate asked for a
200-trade sample; 20 is the population, so every one of them is used and the
spread is reported with a bootstrap interval rather than a sample statistic.

HARNESS CONVENTION (copied from plan/cm_lib.trade_day)
  entry = the OPEN of the minute the live fill happened in,  x (1 + cost)
  exit  = the CLOSE of the minute the live exit happened in, x (1 - cost)
  cost  = 10 bps inside 09:30-16:00, 60 bps outside
Same share count as the live ticket, so the comparison is purely about price
and toll, never about sizing.

Usage:  python plan/hd_recon.py [--fetch]
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_lib as H                                            # noqa: E402

PAPER = H.ROOT / "data" / "paper_days"
HDBARS = H.ROOT / "data" / "massive" / "hd_bars"

SYM_K = ("sym", "symbol", "ticker")
SH_K = ("shares", "exit_shares", "filled_shares")
EIN_K = ("entry_px", "entry_price", "fill_vwap", "entry", "entry_fill",
         "assumed_fill")
ETM_K = ("entry_et", "entry_time_et", "entry_time")
XPX_K = ("exit_px", "exit_price", "exit_vwap_booked", "exit_px_vwap",
         "exit_vwap", "exit", "px")
XTM_K = ("exit_et", "exit_time_et", "exit_time", "time", "et")
PNL_K = ("pnl", "realized_pnl", "pnl_usd", "realized_pnl_usd")


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _hhmm(v):
    if not isinstance(v, str):
        return None
    m = re.search(r"\b([0-2]?\d):([0-5]\d)", v)
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


# blocks that describe how good a fill WAS, not what it was -- they carry
# their own `et` / `px` keys and must never answer a fill query
SKIP = ("realism", "quote", "check", "watch", "status", "peak", "max_",
        "min_", "adverse", "favourable", "settlement", "bracket", "alt",
        "optimistic", "pessimistic", "rules", "armed", "stop", "scale",
        "trail", "size", "spread", "depth", "gates", "modelling", "reduction")


def pick(d, keys, conv, depth=2):
    """First key in priority order whose value converts, searching the dict
    and then nested dicts / lists, skipping commentary blocks."""
    for k in keys:
        if k in d:
            x = conv(d[k])
            if x is not None:
                return x
    for k in keys:
        if isinstance(d.get(k), dict):
            y = pick(d[k], keys, conv, depth - 1)
            if y is not None:
                return y
    if depth <= 0:
        return None
    for k, v in d.items():
        if any(s in k.lower() for s in SKIP):
            continue
        if isinstance(v, dict):
            y = pick(v, keys, conv, depth - 1)
            if y is not None:
                return y
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            y = pick(v[0], keys, conv, depth - 1)
            if y is not None:
                return y
    return None


def extract():
    rows = []
    for p in sorted(PAPER.glob("????-??-??.json")):
        date = p.name[:10]
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        for t in (d.get("trades") or []):
            sym = None
            for k in SYM_K:
                if isinstance(t.get(k), str):
                    sym = t[k].strip().upper()
                    break
            sh = pick(t, SH_K, _num)
            ein = pick(t, EIN_K, _num)
            etm = pick(t, ETM_K, _hhmm)
            # the exit can be a scalar, an `exits` list, or a nested dict --
            # search the exit block FIRST so a fill-realism `et` cannot win
            blocks = []
            if isinstance(t.get("exit"), dict):
                blocks.append(t["exit"])
            if isinstance(t.get("exits"), list) and t["exits"]:
                blocks.append(t["exits"][0])
            blocks.append(t)
            xpx = xtm = pnl = None
            for b in blocks:
                xpx = xpx if xpx is not None else pick(b, XPX_K, _num)
                xtm = xtm if xtm is not None else pick(b, XTM_K, _hhmm)
                pnl = pnl if pnl is not None else pick(b, PNL_K, _num)
            src = t
            if pnl is None and None not in (sh, ein, xpx):
                pnl = sh * (xpx - ein)
            rows.append({"date": date, "sym": sym, "shares": sh,
                         "entry_px": ein, "entry_et": etm,
                         "exit_px": xpx, "exit_et": xtm, "live_pnl": pnl})
    return rows


def bars_for(sym, date, fetch=False):
    b = H.find_m1(sym, date, dirs=(H.M1W, H.M1, H.M1ETF, HDBARS))
    if b is not None or not fetch:
        return b
    sys.path.insert(0, str(H.ROOT.parent))
    from shared import massive
    HDBARS.mkdir(parents=True, exist_ok=True)
    f = HDBARS / f"{sym}_{date}.csv"
    try:
        df = massive.minute_bars(sym, date)
    except Exception as e:
        print(f"[recon] fetch FAIL {sym} {date}: {e}", flush=True)
        return None
    if df is None or len(df) == 0:
        f.write_text("EMPTY\n")
        return None
    with open(f, "w", newline="") as fh:
        fh.write("begins_at,Open,High,Low,Close,Volume\n")
        for ts, r in df.iterrows():
            fh.write(f"{ts.tz_convert('UTC').strftime('%Y-%m-%d %H:%M:%S+00:00')},"
                     f"{r['Open']},{r['High']},{r['Low']},{r['Close']},"
                     f"{r['Volume']}\n")
    print(f"[recon] fetched {sym} {date} ({len(df)} bars)", flush=True)
    return H.read_m1(f, date)


def main():
    fetch = "--fetch" in sys.argv
    rows = extract()
    print(f"[recon] {len(rows)} live round trips found", flush=True)
    out = []
    for r in rows:
        rec = dict(r)
        rec["status"] = "ok"
        if not all([r["sym"], r["shares"], r["entry_et"], r["exit_et"]]):
            rec["status"] = "incomplete-ledger"
            out.append(rec)
            continue
        b = bars_for(r["sym"], r["date"], fetch=fetch)
        if b is None:
            rec["status"] = "no-bars"
            out.append(rec)
            continue
        o, hi, lo, c, v = b
        ki, kx = H.idx(r["entry_et"]), H.idx(r["exit_et"])
        if not (0 <= ki < H.NMIN and 0 <= kx < H.NMIN) or kx <= ki:
            rec["status"] = "bad-minutes"
            out.append(rec)
            continue
        cf = H.ffill(c[None, :])[0]
        px_in = o[ki]
        if not np.isfinite(px_in):
            px_in = cf[ki]
        px_out = cf[kx]
        if not (np.isfinite(px_in) and np.isfinite(px_out)):
            rec["status"] = "bar-gap"
            out.append(rec)
            continue
        sh = r["shares"]
        ci, cx = H.cost_frac(ki), H.cost_frac(kx)
        gross = sh * (px_out - px_in)
        toll = sh * (px_in * ci + px_out * cx)
        rec.update({"k_in": ki, "k_out": kx,
                    "h_px_in": round(float(px_in), 4),
                    "h_px_out": round(float(px_out), 4),
                    "h_gross": round(float(gross), 2),
                    "h_toll": round(float(toll), 2),
                    "h_pnl": round(float(gross - toll), 2),
                    "live_gross": (round(sh * (r["exit_px"] - r["entry_px"]), 2)
                                   if None not in (r["entry_px"], r["exit_px"])
                                   else None),
                    "entry_slip": (round(sh * (r["entry_px"] - px_in), 2)
                                   if r["entry_px"] is not None else None),
                    "exit_slip": (round(sh * (r["exit_px"] - px_out), 2)
                                  if r["exit_px"] is not None else None)})
        if r["live_pnl"] is not None:
            rec["diff"] = round(rec["h_pnl"] - r["live_pnl"], 2)
            rec["diff_gross"] = (round(rec["h_gross"] - rec["live_gross"], 2)
                                 if rec["live_gross"] is not None else None)
        out.append(rec)

    ok = [r for r in out if r["status"] == "ok" and r.get("diff") is not None]
    print(f"[recon] usable {len(ok)} / {len(rows)}", flush=True)
    print(f"{'date':11s} {'sym':6s} {'sh':>6s} {'live':>10s} {'harness':>10s} "
          f"{'diff':>9s} {'gross_d':>9s} {'toll':>8s} {'e_slip':>8s} {'x_slip':>8s}",
          flush=True)
    for r in out:
        if r["status"] != "ok":
            print(f"{r['date']:11s} {str(r['sym']):6s} {'':>6s} "
                  f"{'':>10s} {'':>10s} -- {r['status']}", flush=True)
            continue
        print(f"{r['date']:11s} {str(r['sym']):6s} {r['shares']:6.0f} "
              f"{(r['live_pnl'] if r['live_pnl'] is not None else float('nan')):10.2f} "
              f"{r['h_pnl']:10.2f} "
              f"{(r.get('diff') if r.get('diff') is not None else float('nan')):9.2f} "
              f"{(r.get('diff_gross') if r.get('diff_gross') is not None else float('nan')):9.2f} "
              f"{r['h_toll']:8.2f} "
              f"{(r['entry_slip'] if r['entry_slip'] is not None else float('nan')):8.2f} "
              f"{(r['exit_slip'] if r['exit_slip'] is not None else float('nan')):8.2f}",
              flush=True)

    d = np.array([r["diff"] for r in ok], float)
    dg = np.array([r["diff_gross"] for r in ok if r.get("diff_gross")
                   is not None], float)
    toll = np.array([r["h_toll"] for r in ok], float)
    es = np.array([r["entry_slip"] for r in ok if r["entry_slip"] is not None],
                  float)
    xs = np.array([r["exit_slip"] for r in ok if r["exit_slip"] is not None],
                  float)
    rng = np.random.default_rng(0)
    boot = np.array([rng.choice(d, d.size, replace=True).mean()
                     for _ in range(20000)])
    summ = {
        "n_live": len(rows), "n_usable": len(ok),
        "diff_mean": round(float(d.mean()), 2),
        "diff_median": round(float(np.median(d)), 2),
        "diff_sd": round(float(d.std(ddof=1)), 2),
        "diff_ci95": [round(float(np.percentile(boot, 2.5)), 2),
                      round(float(np.percentile(boot, 97.5)), 2)],
        "frac_harness_worse": round(float((d < 0).mean()), 4),
        "diff_gross_mean": round(float(dg.mean()), 2) if dg.size else None,
        "harness_toll_mean": round(float(toll.mean()), 2),
        "entry_slip_mean": round(float(es.mean()), 2) if es.size else None,
        "exit_slip_mean": round(float(xs.mean()), 2) if xs.size else None,
        "live_pnl_mean": round(float(np.mean([r["live_pnl"] for r in ok])), 2),
        "harness_pnl_mean": round(float(np.mean([r["h_pnl"] for r in ok])), 2),
        "live_pnl_total": round(float(np.sum([r["live_pnl"] for r in ok])), 2),
        "harness_pnl_total": round(float(np.sum([r["h_pnl"] for r in ok])), 2),
    }
    print(json.dumps(summ, indent=1), flush=True)
    H.write("recon.json", {"summary": summ, "rows": out})


if __name__ == "__main__":
    main()
