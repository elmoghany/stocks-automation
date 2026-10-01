"""COST-RESCORE: build the summary + break-even tables of cost-rescore.md
from plan/crs_rescore.json + plan/crs_evid.json (+ PESSIMISM-AUDIT's R4
EVID row, pa_out/rescore_cp.json). Prints markdown to stdout."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "crs_rescore.json").read_text())
E = json.loads((HERE / "crs_evid.json").read_text())
try:
    pa = json.loads((HERE / "pa_out/rescore_cp.json").read_text())["CHAMPION-REPLAY R4"]["EVID"]
    E["CHAMPION-REPLAY R4"] = dict(pa, evid_bps_mean=pa["evid_bps_mean"])
except Exception:
    pass

# config -> (short label, universe/time bucket, generic central bps/side, legal?)
ORDER = [
    ("CHAMPION-REPLAY R4", "CP R4 coil, no stop", "gapper", 28.75),
    ("CATALYST-MINER R15 h60", "CAT R15 fresh-earn & green @09:35", "wide 09:35", 9),
    ("RL-SCOUT v2 approach-4 seed 0", "RL2 approach-4 s0", "wide all-day", 6),
    ("UNIVERSE-QUOTES rank-for-the-fill (limit, h30)", "UQ rank-for-the-fill (limit)", "wide all-day", 6),
    ("CLOSE-MOMENTUM REV 15:30->15:59 k7", "CM REV 15:30->15:59 k7", "wide 15:30", 6),
    ("VS2 W8RSd", "VS2 W8RSd green-on-red", "wide all-day", 6),
    ("OPEN-UNIVERSE top600 ovn_prev+L (CAP100k)", "OU top600 ovn_prev+L (CAP100k)", "open 09:30", 9),
    ("OPEN-UNIVERSE top600 ovn_prev+L (7x15k)", "OU top600 ovn_prev+L (7x15k)", "open 09:30", 9),
    ("WIDE-NET model single", "WN LightGBM 1/day @09:35", "wide 09:35", 9),
    ("LIMIT-EXEC bid-rest3-mkt/tick3 model", "LX rest-then-cross (model)", "wide all-day", 6),
    ("WIDE-NET model top3 @09:35 (account-legal)", "WN top-3 @09:35", "wide 09:35", 9),
    ("WIDE-NET model top5 @09:35 (account-legal)", "WN top-5 @09:35", "wide 09:35", 9),
    ("WIDE-NET model top7 @09:35 (account-legal)", "WN top-7 @09:35", "wide 09:35", 9),
    ("WIDE-NET model top3", "WN top-3 per slot (27/day, NOT legal)", "wide all-day", 6),
    ("WIDE-NET model top5", "WN top-5 per slot (45/day, NOT legal)", "wide all-day", 6),
    ("WIDE-NET model top7", "WN top-7 per slot (63/day, NOT legal)", "wide all-day", 6),
    ("CHAMPION-REPLAY R5", "CP R5 coil, 10:00, stop -2%", "gapper", 28.75),
    ("C37F-hf3", "C37F-hf3 (live rules)", "gapper", 28.75),
    ("HOLD1-hf3", "HOLD1-hf3", "gapper", 28.75),
]


def lin(r, b, key):
    """Exact linear value at cost b from the 0 and 10 rows (every line's
    net is affine in b; the only non-linearity is the +50 ext legs, which
    are constant in b)."""
    a, c = r["0"], r["10"]
    va, vc = _get(a, key), _get(c, key)
    if va is None or vc is None:
        return None
    return va + (vc - va) * b / 10.0


def _get(s, key):
    if key in ("y1", "y2", "half1", "half2"):
        v = s.get(key)
        return v.get("per_month") if isinstance(v, dict) else None
    if key == "ex_best":
        return s.get("ex_best_day", s.get("ex_best_ticket_interp", s.get("ex_best_day_interp")))
    return s.get(key)


def yrs(r, b):
    """(first, second) $/month: Y1/Y2 if the line has both, else its own
    calendar halves (held-out-year-only lines), else OOS halves per ticket."""
    s = r[b] if isinstance(b, str) else None
    if s is None:
        return None
    if isinstance(s.get("y1"), dict) and isinstance(s.get("y2"), dict) and s["y1"].get("per_month") is not None:
        return s["y1"]["per_month"], s["y2"]["per_month"], "Y1/Y2"
    if isinstance(s.get("half1"), dict):
        return s["half1"]["per_month"], s["half2"]["per_month"], "H1/H2"
    if "oos_h1_per_ticket" in s:
        tpd = s.get("tickets_per_day") or 0
        return (s["oos_h1_per_ticket"] * tpd * 21, s["oos_h2_per_ticket"] * tpd * 21, "H1/H2")
    return None


def f(v, d=0):
    return "—" if v is None else f"{v:+,.{d}f}"


def be(v0, v10):
    if v0 is None or v10 is None:
        return None
    if v0 <= 0:
        return -1.0
    k = (v0 - v10) / 10.0
    return v0 / k if k > 0 else 99.0


def fbe(x):
    if x is None:
        return "—"
    if x < 0:
        return "never (neg. at 0)"
    return f"{x:.1f}"


print("| config | tkts/day | $/mo @0 | $/mo @3 | $/mo @4 | $/mo @6 | $/mo @10 | both halves/years + @4? | pct vs random @4 | ex-best-day @4 | break-even bps/side (all · 1st · 2nd) | central cost (bps) → $/mo | fill-specific EVID bps → $/mo |")
print("|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|---|")
for key, short, uni, central in ORDER:
    r = R.get(key)
    if r is None:
        continue
    pm = {b: _get(r[b], "per_month") for b in ("0", "3", "4", "6", "10") if b in r}
    y4 = yrs(r, "4")
    both = "—" if y4 is None else (("yes" if y4[0] > 0 and y4[1] > 0 else "no") + f" ({y4[2]} {f(y4[0])} / {f(y4[1])})")
    pc = r["4"].get("pct_vs_random", r["4"].get("pct_vs_random_normal_approx"))
    y0, y10 = yrs(r, "0"), yrs(r, "10")
    b_all = be(_get(r["0"], "per_month"), _get(r["10"], "per_month"))
    b1 = be(y0[0], y10[0]) if y0 else None
    b2 = be(y0[1], y10[1]) if y0 else None
    cen = lin(r, central, "per_month")
    ev = E.get(key)
    evs = "—" if ev is None else f"{ev['evid_bps_mean']:.1f} → {f(ev['per_month'])}"
    print(f"| {short} | {r['0'].get('tickets_per_day')} | {f(pm.get('0'))} | {f(pm.get('3'))} | {f(pm.get('4'))} | "
          f"{f(pm.get('6'))} | {f(pm.get('10'))} | {both} | {pc if pc is not None else '—'} | {f(_get(r['4'], 'ex_best'))} | "
          f"{fbe(b_all)} · {fbe(b1)} · {fbe(b2)} | {central:g} ({uni}) → {f(cen)} | {evs} |")
