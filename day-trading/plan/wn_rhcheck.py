"""WIDE-NET (2026-09-16): cross-check the Massive 1-minute cache against
Robinhood's own 1-minute bars.

A ~4x Massive-vs-Robinhood premarket volume gap has been seen before in
this project, and every dollar in this study is priced off a Massive bar,
so the disagreement is measured rather than assumed.  Robinhood keeps only
a short intraday history, so the check runs on the most recent date where
both caches hold the same names.

Usage: python plan/wn_rhcheck.py <rh_json_file> <YYYY-MM-DD>
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")


def massive(sym, date):
    for d in ("m1w", "m1"):
        f = ROOT / "data" / "massive" / d / f"{sym}_{date}.csv"
        if f.exists():
            break
    else:
        return None
    out = {}
    with open(f, newline="") as fh:
        rd = csv.reader(fh)
        h = next(rd, None)
        if not h or h[0].startswith("EMPTY"):
            return None
        for r in rd:
            if len(r) < 6 or r[0][:10] != date:
                continue
            out[r[0][11:16]] = (float(r[1]), float(r[4]), float(r[5]))
    return out


def main(path, date):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    res = raw["data"]["results"] if isinstance(raw.get("data"), dict) else raw
    rep = []
    for blk in res:
        sym = blk.get("symbol") or blk.get("Symbol")
        bars = blk.get("historicals") or blk.get("bars") or blk.get("results")
        if not sym or not bars:
            continue
        mv = massive(sym, date)
        if not mv:
            continue
        rh = {}
        for b in bars:
            ts = b.get("begins_at") or b.get("timestamp")
            if not ts:
                continue
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if b.get("interpolated"):
                continue
            rh[t.strftime("%H:%M")] = (
                float(b.get("open_price", b.get("open", 0)) or 0),
                float(b.get("close_price", b.get("close", 0)) or 0),
                float(b.get("volume", 0) or 0))
        # UTC minute keys on both sides; split premarket / RTH by ET
        off = int(datetime.strptime(date, "%Y-%m-%d").replace(
            hour=12, tzinfo=ET).utcoffset().total_seconds() // 60)
        def sess(k):
            m = int(k[:2]) * 60 + int(k[3:]) + off
            return "pre" if m < 570 else ("rth" if m < 960 else "post")
        row = {"sym": sym}
        for s in ("pre", "rth", "post"):
            mk = {k for k in mv if sess(k) == s}
            rk = {k for k in rh if sess(k) == s}
            mvv = sum(mv[k][2] for k in mk)
            rvv = sum(rh[k][2] for k in rk)
            row[s] = {"massive_bars": len(mk), "rh_bars": len(rk),
                      "massive_vol": int(mvv), "rh_vol": int(rvv),
                      "vol_ratio": round(mvv / rvv, 3) if rvv else None,
                      "common_bars": len(mk & rk)}
            both = sorted(mk & rk)
            if both:
                dp = [abs(mv[k][1] - rh[k][1]) / max(rh[k][1], 1e-9)
                      for k in both]
                row[s]["max_close_diff_bps"] = round(max(dp) * 1e4, 1)
                row[s]["med_close_diff_bps"] = round(
                    sorted(dp)[len(dp) // 2] * 1e4, 2)
                dv = [mv[k][2] / max(rh[k][2], 1) for k in both
                      if rh[k][2] > 0]
                if dv:
                    row[s]["per_bar_vol_ratio_med"] = round(
                        sorted(dv)[len(dv) // 2], 3)
        rep.append(row)
    out = ROOT / "data" / "massive" / "wn" / f"rhcheck_{date}.json"
    out.write_text(json.dumps(rep, indent=1))
    print(f"{'sym':>6} {'sess':>5} {'M bars':>7} {'RH bars':>8} "
          f"{'M vol':>10} {'RH vol':>10} {'vol M/RH':>9} {'px bps':>8}")
    for r in rep:
        for s in ("pre", "rth", "post"):
            d = r[s]
            print(f"{r['sym']:>6} {s:>5} {d['massive_bars']:>7} "
                  f"{d['rh_bars']:>8} {d['massive_vol']:>10,} "
                  f"{d['rh_vol']:>10,} "
                  f"{(d['vol_ratio'] if d['vol_ratio'] is not None else 0):>9.3f} "
                  f"{d.get('med_close_diff_bps', float('nan')):>8.2f}")
    print(f"\nwritten {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
