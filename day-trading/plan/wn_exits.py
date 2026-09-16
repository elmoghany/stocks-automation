"""WIDE-NET (2026-09-16) addendum: TA exits on the wide-net entry patterns.

The table in plan/wn_table.py only knows fixed horizons and the forced
flatten.  MEMORY.md's research line ("mean-reversion entry + TA exits") and
plan/rl2/rules.py's best held-out rule both use a stop / take-profit /
trailing-stop exit instead, so this file measures that lever directly on
the wide-net entries.

MECHANICS, identical to plan/rl2/sim.py's ("rule", d) exit
  entry   at the OPEN of the minute after the decision minute
  monitor `mark` = the last printed close at or before each later 5-minute
          decision step -- never an intrabar high or low, so the exit
          cannot be filled at a price the decision could not have seen
  exit    at the OPEN of the minute after the step that triggered; if the
          day ends first, at the forced-flatten price
  costs   10 bps a side, +50 bps outside 09:30-16:00, both legs

SELECTION HYGIENE.  The exit grid is scored on the TRAIN window, the single
best combination is carried to the held-out year ONCE, and the whole OOS
grid is printed underneath it so the reader can see how much of the
"winner" is just the best of 192 tries.

Usage: python plan/wn_exits.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wn_table as WT                                     # noqa: E402
from wn_lib import OUT, Table, summarize, write_json      # noqa: E402
from wn_oos import pick, rule_margin                      # noqa: E402
from wn_rules import RTH, apply_rule                      # noqa: E402

FEAT = Path(__file__).resolve().parent / "rl2" / "out" / "feat"
STOPS = [0.02, 0.03, 0.05, None]
TAKES = [0.03, 0.05, 0.08, None]
TRAILS = [0.03, 0.05, None]
TMAXS = [60, 120, 240, None]
_CACHE = {}


def day_arrays(date):
    if date not in _CACHE:
        if len(_CACHE) > 24:
            _CACHE.clear()
        z = np.load(FEAT / f"{date}.npz", allow_pickle=False)
        _CACHE[date] = ([str(s) for s in z["syms"]],
                        z["mark"].astype(np.float64),
                        z["fill_o"].astype(np.float64),
                        z["flat_px"].astype(np.float64),
                        z["flat_min"].astype(int))
    return _CACHE[date]


def run_exit(date, sym, ti, notional, stop, take, trail, tmax):
    """Net $ of one ticket entered at decision index ti under a TA exit."""
    syms, mark, fill_o, flat_px, flat_min = day_arrays(date)
    try:
        s = syms.index(sym)
    except ValueError:
        return None
    t0 = int(WT.DEC_T[ti])
    m0 = min(int(WT.STEPS[t0]) + 1, WT.NMIN - 1)
    px = fill_o[t0, s]
    if not np.isfinite(px) or px <= 0:
        return None
    sh = notional / px
    cost = sh * px * (1.0 + float(WT.cost_frac(np.array([m0]))[0]))
    peak = px
    for t in range(t0 + 1, len(WT.STEPS)):
        m = int(WT.STEPS[t])
        mk = mark[t, s]
        hit = False
        if np.isfinite(mk):
            r = mk / px - 1.0
            peak = max(peak, mk)
            if stop is not None and r <= -stop:
                hit = True
            if take is not None and r >= take:
                hit = True
            if trail is not None and mk <= peak * (1.0 - trail):
                hit = True
        if tmax is not None and m >= int(WT.STEPS[t0]) + tmax:
            hit = True
        if not hit:
            continue
        q = fill_o[t, s]
        if not np.isfinite(q) or q <= 0:
            continue                       # no print: carry to the next step
        mf = min(m + 1, WT.NMIN - 1)
        return sh * q * (1.0 - float(WT.cost_frac(np.array([mf]))[0])) - cost
    q, mf = flat_px[s], int(flat_min[s])
    if not np.isfinite(q) or q <= 0:
        q, mf = px, m0
    return sh * q * (1.0 - float(WT.cost_frac(np.array([mf]))[0])) - cost


def entries_for(t, rule, h, split):
    rows = pick(t, apply_rule(t, rule, h) & np.isin(t.split, split),
                np.where(apply_rule(t, rule, h), rule_margin(t, rule), -np.inf),
                per="day")
    return [(t.date_s[i], t.syms[t.sym_i[i]], int(t.dec_i[i]),
             float(t.notional[i])) for i in rows]


def grid(t, ents, ndays, label):
    out = []
    for st in STOPS:
        for tk in TAKES:
            for tr in TRAILS:
                for tm in TMAXS:
                    if st is None and tk is None and tr is None and tm is None:
                        continue
                    p, d = [], []
                    for (dt, sy, ti, no) in ents:
                        v = run_exit(dt, sy, ti, no, st, tk, tr, tm)
                        if v is not None:
                            p.append(v)
                            d.append(dt)
                    if len(p) < 15:
                        continue
                    s = summarize(np.array(p), d, ndays, label)
                    s.pop("monthly", None)
                    s.update(stop=st, take=tk, trail=tr, tmax=tm)
                    out.append(s)
    out.sort(key=lambda r: -r["per_ticket"])
    return out


def main():
    t = Table()
    rules = json.loads((OUT / "rules_search.json").read_text())
    seen, pats = set(), []
    for r in sorted(rules, key=lambda r: -r["train_mean"]):
        k = tuple(sorted(r["rule"]))
        if k in seen:
            continue
        seen.add(k)
        pats.append(r)
    pats = pats[:4]
    report = []
    for r in pats:
        rule, h = r["rule"], r["h"]
        nm = " AND ".join(rule)
        etr = entries_for(t, rule, h, 0)
        eoo = entries_for(t, rule, h, 1)
        if len(etr) < 25 or len(eoo) < 25:
            continue
        print(f"\n=== {nm}\n    entries: train {len(etr)}, OOS {len(eoo)} "
              f"(one ticket a day)", flush=True)
        gtr = grid(t, etr, t.ndays(0), "train")
        goo = grid(t, eoo, t.ndays(1), "oos")
        if not gtr or not goo:
            continue
        best = gtr[0]
        key = (best["stop"], best["take"], best["trail"], best["tmax"])
        sel = [g for g in goo if (g["stop"], g["take"], g["trail"],
                                  g["tmax"]) == key]
        sel = sel[0] if sel else None
        print(f"  best-on-TRAIN exit stop={best['stop']} take={best['take']} "
              f"trail={best['trail']} tmax={best['tmax']} -> train "
              f"${best['per_ticket']:+.2f}/tkt")
        if sel:
            print(f"  SAME EXIT out of sample: ${sel['per_ticket']:+.2f}/tkt, "
                  f"{sel['tickets']} tkt, ${sel['per_month']:+.0f}/month, "
                  f"months+ {sel['months_pos']}, maxDD ${sel['max_dd']:,.0f}")
        print(f"  for scale, the best of all {len(goo)} exits ON THE OOS "
              f"ITSELF (not a result, a ceiling): "
              f"${goo[0]['per_ticket']:+.2f}/tkt "
              f"(stop={goo[0]['stop']} take={goo[0]['take']} "
              f"trail={goo[0]['trail']} tmax={goo[0]['tmax']}), "
              f"median ${np.median([g['per_ticket'] for g in goo]):+.2f}")
        report.append({"rule": rule, "h": h, "n_train": len(etr),
                       "n_oos": len(eoo), "train_best": best,
                       "oos_same_exit": sel, "oos_grid_best": goo[0],
                       "oos_grid_median": round(float(np.median(
                           [g["per_ticket"] for g in goo])), 2),
                       "oos_grid_frac_positive": round(float(np.mean(
                           [g["per_ticket"] > 0 for g in goo])), 3)})
    write_json("exits_report.json", report)
    print("\nwritten data/massive/wn/exits_report.json")


if __name__ == "__main__":
    main()
