"""LIMIT-EXEC: the ENGINE IDENTITY gate for the flag-gated limit hook.

day-trading.py::simulate_trades gained `exit_mode` / `limit_entry` /
`limit_exit` (and `entry_mode="limit_bid"` as sugar).  With the flags off
`pend_buy` / `pend_sell` / `_lim_fill_now` stay None and every new branch
is dead, so the engine must be byte-identical to the pre-edit one.

Proved the way COST-REBASE proved its hook (plan/cr_ident.py, reused by
import): the pre-edit engine is loaded from a saved copy and both engines
are run over the same symbol-days under the REAL kwargs of C37F, HOLD1
and W8RSd -- resolved by their own harnesses -- asserting every trade
matches field for field.  A fourth leg runs the NEW engine with the
flags ON so the report also shows the hook does something.

Usage: python plan/lx_ident.py [--n 300] [--pre PATH]
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import cr_ident as CI                                         # noqa: E402

OUT = HERE / "lx_out"
PRE_DEFAULT = Path(r"C:\Users\MYPC~1\AppData\Local\Temp\dt_pre_limitexec.py")


def main():
    import pandas as pd
    from datetime import time as dtime
    a = sys.argv[1:]
    n = int(a[a.index("--n") + 1]) if "--n" in a else 300
    pre_p = Path(a[a.index("--pre") + 1]) if "--pre" in a else PRE_DEFAULT
    old = CI._load("dt_old", pre_p)
    new = CI._load("dt_new", ROOT / "day-trading.py")
    M1 = ROOT / "data" / "massive" / "m1"
    fs = sorted(M1.glob("*.csv"))
    step = max(1, len(fs) // n)
    fs = fs[::step][:n]
    rep = {"pre_engine": str(pre_p), "brackets": {}}
    for bname, kw in CI.brackets().items():
        nd = ok = leg = 0
        on_legs = on_pass = on_diff = 0
        for f in fs:
            try:
                df = pd.read_csv(f, index_col=0, parse_dates=True)
                df.index = df.index.tz_convert("America/New_York")
            except Exception:
                continue
            if len(df) < 60:
                continue
            pc = float(df["Close"].iloc[0]) / 1.15
            es = dtime(9, 35)
            ta = old.simulate_trades(df, prev_close=pc, entry_start=es, **kw)
            tb = new.simulate_trades(df, prev_close=pc, entry_start=es, **kw)
            nd += 1
            leg += len(ta)
            ok += int(CI.same(ta, tb))
            # flags ON: the hook must run and change something somewhere
            kw_on = dict(kw)
            if kw_on.get("entry_mode", "triggers") == "market_at_start":
                kw_on["limit_entry"] = (0.0, 3, "cancel")
            else:
                kw_on["entry_mode"] = "limit_bid"
            kw_on["exit_mode"] = "limit_ask"
            tc = new.simulate_trades(df, prev_close=pc, entry_start=es, **kw_on)
            on_legs += len(tc)
            on_pass += sum(1 for t in tc if "|limit" in t.get("reason", ""))
            on_diff += int(not CI.same(ta, tc))
        rep["brackets"][bname] = dict(symbol_days=nd, legs=leg,
                                      identical_flag_off=ok,
                                      flags_on_legs=on_legs,
                                      flags_on_passive_exits=on_pass,
                                      flags_on_days_changed=on_diff)
        print(f"{bname:>8}: {nd} symbol-days, {leg} legs, flag-off identical "
              f"{ok}/{nd}; flags ON: {on_legs} legs, {on_pass} passive exits, "
              f"{on_diff} days changed", flush=True)
    OUT.mkdir(exist_ok=True)
    (OUT / "engine_identity.json").write_text(json.dumps(rep, indent=1))
    bad = sum(v["symbol_days"] - v["identical_flag_off"]
              for v in rep["brackets"].values())
    print("ENGINE IDENTITY:", "PASS" if bad == 0 else f"FAIL ({bad} days differ)")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
