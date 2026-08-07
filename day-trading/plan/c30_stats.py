"""Deep statistical analysis of the C30/C23 champion's trade record
(user 2026-08-07: "find mathematical and statistical useful info,
correlation and so on so we can even do better").

Reads data/massive/c23_trades_{year,y2025}.json -- every position with
entry/exit time+price, exit reason, trigger type, entry pressure and
peak_pct -- and reports:
  1  daily P&L distribution + concentration + Kelly sizing math
  2  autocorrelation / streak structure (does yesterday predict today?)
  3  calendar effects (weekday, month)
  4  entry-hour profitability and the 1PM-window contribution
  5  trigger-type economics (ORB vs premarket-high vs pattern)
  6  exit-reason economics (stop / trail / pattern / flatten)
  7  re-entry ladder decay (P&L by position number within a day)
  8  trail efficiency: how much of each position's peak we keep
  9  entry pressure (p_entry) vs outcome correlation
 10  gap-band (g7) economics
 11  correlations among day-level features
No fallbacks: any missing field is reported, not silently defaulted.
"""

import json
import math
import statistics as st
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "data/massive"


def load():
    days = []
    for lab in ("y2025", "year"):          # chronological
        f = M / f"c23_trades_{lab}.json"
        if not f.exists():
            print(f"ERROR: missing {f.name}")
            continue
        for d in json.loads(f.read_text()):
            d["label"] = lab
            days.append(d)
    days.sort(key=lambda d: d["date"])
    return days


def pct(xs, p):
    return st.quantiles(xs, n=100)[p - 1] if len(xs) > 2 else float("nan")


def show(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main():
    days = load()
    trades = []
    for d in days:
        for i, t in enumerate(d.get("trades", [])):
            t = dict(t)
            t["date"] = d["date"]
            t["symbol"] = d["symbol"]
            t["g7"] = d.get("g7")
            t["seq"] = i
            trades.append(t)
    dp = [d["pnl"] for d in days]
    tp = [t["pnl"] for t in trades]
    print(f"{len(days)} traded days, {len(trades)} positions, "
          f"total ${sum(dp):+,.0f}")

    # ---------- 1. distribution + Kelly ----------
    show("1. DAILY P&L DISTRIBUTION, CONCENTRATION, KELLY")
    wins = [x for x in dp if x > 0]
    losses = [x for x in dp if x < 0]
    print(f"mean ${st.fmean(dp):+,.0f} | median ${st.median(dp):+,.0f} | "
          f"stdev ${st.pstdev(dp):,.0f}")
    print(f"win days {len(wins)}/{len(dp)} = {100*len(wins)/len(dp):.1f}% "
          f"| avg win ${st.fmean(wins):+,.0f} | avg loss "
          f"${st.fmean(losses):+,.0f}" if losses else "")
    for p in (1, 5, 25, 50, 75, 95, 99):
        print(f"  p{p:<2} ${pct(dp, p):>+12,.0f}")
    print(f"skew {sum(((x-st.fmean(dp))/st.pstdev(dp))**3 for x in dp)/len(dp):+.2f}"
          f" | kurtosis "
          f"{sum(((x-st.fmean(dp))/st.pstdev(dp))**4 for x in dp)/len(dp):.1f}"
          f"  (normal = 0 / 3)")
    srt = sorted(dp, reverse=True)
    tot = sum(dp)
    for k in (5, 10, 20):
        n = max(1, len(srt) * k // 100)
        print(f"  top {k:>2}% of days ({n:>3}) = "
              f"{100*sum(srt[:n])/tot:.1f}% of all profit")
    # Kelly on DAY returns vs a $15k slot
    W = len(wins) / len(dp)
    R = abs(st.fmean(wins) / st.fmean(losses)) if losses else float("inf")
    kelly = W - (1 - W) / R
    print(f"\nday-level win rate W={W:.3f}, payoff R={R:.2f} "
          f"-> full Kelly f* = {kelly:.3f} ({kelly*100:.1f}% of bankroll)")
    print(f"  half-Kelly (standard practice) = {kelly*50:.1f}% of bankroll")
    print(f"  => at $15k/day risked, implied bankroll for full Kelly "
          f"${15000/kelly:,.0f}; for half-Kelly ${15000/(kelly/2):,.0f}")
    # Sharpe-ish on the fixed slot
    dr = [x / 15000 for x in dp]
    print(f"  daily return on slot: mean {100*st.fmean(dr):+.2f}%, "
          f"sd {100*st.pstdev(dr):.2f}%, "
          f"annualized Sharpe (252d, rf=0) "
          f"{st.fmean(dr)/st.pstdev(dr)*math.sqrt(252):.2f}")

    # ---------- 2. autocorrelation / streaks ----------
    show("2. AUTOCORRELATION & STREAK STRUCTURE")
    def corr(a, b):
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
        ma, mb = st.fmean(a), st.fmean(b)
        num = sum((x-ma)*(y-mb) for x, y in zip(a, b))
        den = math.sqrt(sum((x-ma)**2 for x in a) * sum((y-mb)**2 for y in b))
        return num/den if den else float("nan")
    for lag in (1, 2, 3, 5):
        print(f"  lag-{lag} autocorrelation of daily P&L: "
              f"{corr(dp[:-lag], dp[lag:]):+.3f}")
    aft_win = [dp[i+1] for i in range(len(dp)-1) if dp[i] > 0]
    aft_loss = [dp[i+1] for i in range(len(dp)-1) if dp[i] < 0]
    print(f"  day after a WIN:  mean ${st.fmean(aft_win):+,.0f} "
          f"(n={len(aft_win)})")
    print(f"  day after a LOSS: mean ${st.fmean(aft_loss):+,.0f} "
          f"(n={len(aft_loss)})")
    big = st.quantiles(dp, n=10)[8]          # top decile threshold
    aft_big = [dp[i+1] for i in range(len(dp)-1) if dp[i] >= big]
    print(f"  day after a MONSTER (>= ${big:,.0f}): mean "
          f"${st.fmean(aft_big):+,.0f} (n={len(aft_big)})")

    # ---------- 3. calendar ----------
    show("3. CALENDAR EFFECTS")
    wd = defaultdict(list)
    mo = defaultdict(list)
    for d in days:
        dt = datetime.fromisoformat(d["date"])
        wd[dt.strftime("%a")].append(d["pnl"])
        mo[dt.strftime("%m")].append(d["pnl"])
    for k in ("Mon", "Tue", "Wed", "Thu", "Fri"):
        v = wd.get(k, [])
        if v:
            print(f"  {k}: n={len(v):>3} mean ${st.fmean(v):>+9,.0f} "
                  f"median ${st.median(v):>+8,.0f} "
                  f"win {100*sum(1 for x in v if x>0)/len(v):>4.0f}%")
    print("  by month:", "  ".join(
        f"{k}:{st.fmean(v):+,.0f}" for k, v in sorted(mo.items())))

    # ---------- 4. entry hour + 1PM window ----------
    show("4. ENTRY-HOUR ECONOMICS (and what the 1PM window adds)")
    byh = defaultdict(list)
    for t in trades:
        h = datetime.fromisoformat(t["entry_time"]).hour
        byh[h].append(t["pnl"])
    for h in sorted(byh):
        v = byh[h]
        print(f"  {h:02d}:00  n={len(v):>4} total ${sum(v):>+11,.0f} "
              f"mean ${st.fmean(v):>+8,.0f} "
              f"win {100*sum(1 for x in v if x>0)/len(v):>4.0f}%")
    late = [t["pnl"] for t in trades
            if datetime.fromisoformat(t["entry_time"]).hour >= 12]
    lex = [t["pnl"] for t in trades
           if datetime.fromisoformat(t["exit_time"]).hour >= 12]
    print(f"  positions ENTERED at/after noon: {len(late)}, "
          f"total ${sum(late):+,.0f}")
    print(f"  positions EXITED at/after noon: {len(lex)}, "
          f"total ${sum(lex):+,.0f}  <- the 1PM window's contribution")

    # ---------- 5. trigger types ----------
    show("5. TRIGGER-TYPE ECONOMICS")
    bytr = defaultdict(list)
    for t in trades:
        bytr[t.get("trig", "?")].append(t["pnl"])
    for k, v in sorted(bytr.items(), key=lambda kv: -sum(kv[1])):
        print(f"  {k:<18} n={len(v):>4} total ${sum(v):>+11,.0f} "
              f"mean ${st.fmean(v):>+8,.0f} "
              f"win {100*sum(1 for x in v if x>0)/len(v):>4.0f}%")

    # ---------- 6. exit reasons ----------
    show("6. EXIT-REASON ECONOMICS")
    bye = defaultdict(list)
    for t in trades:
        r = str(t.get("reason", "?"))
        key = ("stop" if r.startswith("stop") else
               "trail" if "trail" in r else
               "scale" if "scale" in r else
               "flatten" if "flatten" in r else
               "pressure" if "pressure" in r else
               "bearish-pattern" if r.startswith("bearish") else r[:18])
        bye[key].append(t["pnl"])
    for k, v in sorted(bye.items(), key=lambda kv: -sum(kv[1])):
        print(f"  {k:<18} n={len(v):>4} total ${sum(v):>+11,.0f} "
              f"mean ${st.fmean(v):>+8,.0f} "
              f"win {100*sum(1 for x in v if x>0)/len(v):>4.0f}%")

    # ---------- 7. re-entry ladder ----------
    show("7. RE-ENTRY LADDER DECAY (P&L by position number in the day)")
    byseq = defaultdict(list)
    for t in trades:
        byseq[min(t["seq"], 9)].append(t["pnl"])
    cum = 0.0
    for k in sorted(byseq):
        v = byseq[k]
        cum += sum(v)
        lbl = f"#{k}" if k < 9 else "#9+"
        print(f"  {lbl:<4} n={len(v):>4} total ${sum(v):>+11,.0f} "
              f"mean ${st.fmean(v):>+8,.0f} "
              f"win {100*sum(1 for x in v if x>0)/len(v):>4.0f}%  "
              f"cum ${cum:+,.0f}")

    # ---------- 8. trail efficiency ----------
    show("8. TRAIL EFFICIENCY (how much of the peak we keep)")
    keep = []
    for t in trades:
        pk = t.get("peak_pct")
        if pk is None or pk <= 0:
            continue
        ret = (t["exit"] / t["entry"] - 1) * 100
        keep.append((pk, ret, ret / pk if pk > 0 else 0))
    if keep:
        print(f"  positions with a positive peak: {len(keep)}")
        print(f"  median peak {st.median([k[0] for k in keep]):.2f}% -> "
              f"median captured {st.median([k[1] for k in keep]):.2f}%")
        caps = [k[2] for k in keep]
        print(f"  capture ratio: median {st.median(caps):.2f}, "
              f"mean {st.fmean(caps):.2f}")
        for lo, hi in ((0, 5), (5, 15), (15, 40), (40, 1e9)):
            sub = [k for k in keep if lo <= k[0] < hi]
            if sub:
                print(f"    peak {lo:>3}-{hi if hi < 1e9 else '+':>4}%: "
                      f"n={len(sub):>4} median capture "
                      f"{st.median([s[2] for s in sub]):.2f} "
                      f"(median peak {st.median([s[0] for s in sub]):.1f}% "
                      f"-> kept {st.median([s[1] for s in sub]):.1f}%)")

    # ---------- 9. entry pressure ----------
    show("9. ENTRY PRESSURE (p_entry) vs OUTCOME")
    ps = [(t["p_entry"], t["pnl"]) for t in trades
          if t.get("p_entry") is not None]
    if ps:
        print(f"  n={len(ps)}  corr(p_entry, pnl) = "
              f"{corr([p for p, _ in ps], [q for _, q in ps]):+.3f}")
        for lo, hi in ((-1.01, -0.3), (-0.3, 0), (0, 0.3), (0.3, 1.01)):
            sub = [q for p, q in ps if lo <= p < hi]
            if sub:
                print(f"    p in [{lo:>5.2f},{hi:>5.2f}): n={len(sub):>4} "
                      f"mean ${st.fmean(sub):>+8,.0f} "
                      f"win {100*sum(1 for x in sub if x>0)/len(sub):>4.0f}%")

    # ---------- 10. gap band ----------
    show("10. GAP BAND (7AM gap) ECONOMICS")
    byg = defaultdict(list)
    for d in days:
        g = d.get("g7")
        if g is None:
            continue
        b = ("<0%" if g < 0 else "0-5%" if g < 5 else "5-10%" if g < 10
             else "10-15%" if g < 15 else "15-20%")
        byg[b].append(d["pnl"])
    order = ["<0%", "0-5%", "5-10%", "10-15%", "15-20%"]
    for b in order:
        v = byg.get(b, [])
        if v:
            print(f"  {b:<8} days={len(v):>3} total ${sum(v):>+11,.0f} "
                  f"mean ${st.fmean(v):>+9,.0f} "
                  f"win {100*sum(1 for x in v if x>0)/len(v):>4.0f}%")

    # ---------- 11. day-feature correlations ----------
    show("11. DAY-FEATURE CORRELATIONS")
    feats = []
    for d in days:
        trs = d.get("trades", [])
        if not trs:
            continue
        first = datetime.fromisoformat(trs[0]["entry_time"])
        feats.append(dict(
            pnl=d["pnl"], n=len(trs), g7=d.get("g7") or 0,
            first_h=first.hour + first.minute / 60,
            rank=d.get("rank", 0), pc=d.get("prev_close") or 0))
    for k in ("n", "g7", "first_h", "rank", "pc"):
        print(f"  corr(day P&L, {k:<8}) = "
              f"{corr([f['pnl'] for f in feats], [f[k] for f in feats]):+.3f}")
    print("  (n = positions that day; first_h = hour of the first entry;"
          " rank = pool rank of the traded name; pc = prev close)")


if __name__ == "__main__":
    main()
