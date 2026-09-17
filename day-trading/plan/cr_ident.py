"""COST-REBASE: the ENGINE IDENTITY gate.

The only edit this line makes to a shared file is the flag-gated
`cost_model` / `cost_bps_fn` pair in day-trading.py::simulate_trades:
the scalar `slip` became `_slip(i)` at eight call sites. With the flag
off `_slip(i)` returns the same float, so the engine must be
byte-identical to the pre-COST-REBASE one.

This gate proves that DIRECTLY, by loading the pre-edit engine out of
git (commit acb2730, the last commit before this line) and running both
engines over the same symbol-days under the same kwargs -- the C37F
bracket, the HOLD1 no-exit bracket and the VS2 market_at_start bracket
-- asserting every trade matches field for field.

It also runs the third leg: the NEW engine with `cost_model="measured"`
and a cost function that returns the LEGACY ladder must equal both.

Why this and not a full C37F re-run: a rotation pass is hours on a
contended machine and would prove the same thing through 500 days of
bar loading. `plan/idgate.py --rot` still asserts the published shard
rows, and the rotation anchors' flat-10 numbers in this audit ARE the
published C37F-hf2 / HOLD1-hf2 rows, which this gate shows the edited
engine reproduces.

Usage: python plan/cr_ident.py [--n 400] [--pre PATH]
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT.parent))

OUT = HERE / "cr_out"
PRE_DEFAULT = Path(r"C:\Users\MYPC~1\AppData\Local\Temp"
                   r"\dt_pre_costrebase.py")

def brackets():
    """The REAL engine kwargs of the three configs this line re-prices,
    resolved by the harnesses themselves -- not retyped here, so an
    identity run cannot silently test a bracket nobody uses."""
    import os
    os.environ.setdefault("ROTSHARD", "cr_ident_scratch")
    RS = _load("rotation_sim", HERE / "rotation_sim.py")
    VW = _load("vs2_wide", HERE / "vs2_wide.py")
    out = {}
    for cid in ("C37F", "HOLD1"):
        kw = RS.build_simkw(cid, RS.CFGS[cid], echo=False)
        cfg = RS.CFGS[cid]
        if cfg.get("slip"):
            kw = dict(kw, slippage_bps=cfg["slip"] * 1e4)
        out[cid] = dict(kw, budget=15000.0)
    out["W8RSd"] = dict(VW.CFGS["W8RSd"]["sim"], budget=15000.0)
    return out

FIELDS = ("entry_time", "entry", "exit_time", "exit", "reason", "pnl",
          "shares", "peak_pct")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def same(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        for f in FIELDS:
            if x.get(f) != y.get(f):
                return False
    return True


def main():
    import pandas as pd
    a = sys.argv[1:]
    n = int(a[a.index("--n") + 1]) if "--n" in a else 400
    pre_p = Path(a[a.index("--pre") + 1]) if "--pre" in a else PRE_DEFAULT
    old = _load("dt_old", pre_p)
    new = _load("dt_new", ROOT / "day-trading.py")
    M1 = ROOT / "data" / "massive" / "m1"
    fs = sorted(M1.glob("*.csv"))
    step = max(1, len(fs) // n)
    fs = fs[::step][:n]
    rep = {"pre_engine": str(pre_p), "brackets": {}}
    from datetime import time as dtime
    for bname, kw in brackets().items():
        nd = ok = leg = 0
        ok3 = 0
        for f in fs:
            try:
                df = pd.read_csv(f, index_col=0, parse_dates=True)
                df.index = df.index.tz_convert("America/New_York")
            except Exception:
                continue
            if len(df) < 60:
                continue
            # make the day look like the gapper the rotation layer would
            # have handed the engine, so entries actually fire
            pc = float(df["Close"].iloc[0]) / 1.15
            es = dtime(9, 35)
            ta = old.simulate_trades(df, prev_close=pc, entry_start=es, **kw)
            tb = new.simulate_trades(df, prev_close=pc, entry_start=es, **kw)
            # leg 3 feeds the measured PATH this config's OWN legacy
            # ladder. NOTE it is not 10 bps for every config: C37F
            # carries no `slip` at all, so its incumbent per-side cost
            # is ZERO (rotation_sim.py:1477/1512 set slippage_bps only
            # when cfg["slip"] is present). See cost-rebase-audit.md.
            leg_bps = float(kw.get("slippage_bps") or 0.0)
            tc = new.simulate_trades(df, prev_close=pc, entry_start=es,
                                     cost_model="measured",
                                     cost_bps_fn=lambda ts: leg_bps, **kw)
            nd += 1
            leg += len(ta)
            ok += int(same(ta, tb))
            ok3 += int(same(ta, tc))
        rep["brackets"][bname] = dict(symbol_days=nd, legs=leg,
                                      legacy_slippage_bps=float(
                                          kw.get("slippage_bps") or 0.0),
                                      pm_spread_bps=float(
                                          kw.get("pm_spread_bps") or 0.0),
                                      identical_flag_off=ok,
                                      identical_measured_legacy_fn=ok3)
        print(f"{bname:>8}: legacy slip "
              f"{float(kw.get('slippage_bps') or 0.0):.0f} bps/side, "
              f"{nd} symbol-days, {leg} legs, "
              f"flag-off identical {ok}/{nd}, "
              f"measured-with-legacy-fn identical {ok3}/{nd}", flush=True)
    OUT.mkdir(exist_ok=True)
    (OUT / "engine_identity.json").write_text(json.dumps(rep, indent=1))
    bad = sum(v["symbol_days"] - v["identical_flag_off"]
              for v in rep["brackets"].values())
    bad3 = sum(v["symbol_days"] - v["identical_measured_legacy_fn"]
               for v in rep["brackets"].values())
    print(f"\nENGINE IDENTITY: {'PASS' if bad == 0 else 'FAIL'} "
          f"({bad} mismatched symbol-days flag-off, {bad3} with the "
          f"measured path fed the legacy ladder)")
    raise SystemExit(0 if bad == 0 and bad3 == 0 else 1)


if __name__ == "__main__":
    main()
