"""COST-REBASE: import-and-wrap adapters that put the MEASURED cost
model behind the existing harnesses WITHOUT rewriting any of them.

Three harnesses, three different shapes, one rule: nothing in
rotation_sim.py, vs2_wide.py, plan/rl2/*, plan/wn_*.py or plan/uq_*.py
is edited. The only engine change in the whole line is the flag-gated
`cost_model` / `cost_bps_fn` pair in day-trading.py::simulate_trades,
which is inert with the flag off.

  A. ROTATION (C37F / HOLD1 and their controls) -- rotation_sim calls
     `dt.simulate_trades(w, prev_close=..., budget=..., entry_start=...)`
     and never passes the symbol. The symbol IS in the memo key
     (`("sim", symbol, entry_start, budget) + mk`, rotation_sim.py:1483
     / :1519), so `_memo_sim` is wrapped to publish (symbol, budget)
     into a context, and `dt.simulate_trades` is wrapped to read it and
     inject `cost_model="measured", cost_bps_fn=...`. The date comes off
     the bars themselves. Neither wrapper changes any argument the
     harness computes.

  B. VS2 (vs2_wide.py) -- same engine call, but the symbol is not in a
     memo key; `vs2_wide.run_day` holds `pick["c"]["symbol"]`. The same
     `dt.simulate_trades` wrapper is used, with the symbol published by
     a wrapper around `vs2_wide.day_cands` that tags every candidate's
     DataFrame by identity (id(df) -> symbol). DataFrames are sliced
     before the call, so the slice is matched back through
     `vs2_wide._rows_at`... in practice the slice is taken inside
     run_day from `pick["df"]`, so the tag is carried on the PARENT and
     resolved by `_sym_for_df` walking the small per-day table.

  C. rl2 (plan/rl2/sim.py) -- its P&L is an independent vectorised
     harness whose PATH is provably cost-independent: exits compare
     `mark / px_in` (raw fill prices), sizing is `notional / px`, and
     the $500 minimum tests `sh * px` -- no cost enters any branch. So
     the ledger `run_day` returns can be RE-PRICED exactly. `reprice()`
     does that, and `assert_path_cost_free()` proves the premise by
     re-running with the flat fee doubled and asserting every entry and
     exit minute and price is unchanged.

Usage: imported by plan/cr_rerun.py. `python plan/cr_engine.py --check`
runs the two structural proofs (A's symbol resolution, C's path
independence) on a handful of days.
"""
import importlib.util
import sys
from datetime import time as dtime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT.parent))

import cr_cost as CC                                        # noqa: E402

RTH_LO, RTH_HI = dtime(9, 30), dtime(16, 0)


# ======================================================================
# the per-bar cost callable handed to day-trading.py
# ======================================================================

class EngineCost:
    """Builds `cost_bps_fn` closures for simulate_trades.

    One instance per run so the tier tally and the samples accumulate
    across every ticket of the run.
    """

    def __init__(self, cm=None, notional=15000.0, ext_floor_bps=10.0):
        self.cm = cm or CC.CostModel(ext_floor_bps=ext_floor_bps)
        self.notional = notional
        self.miss = 0
        self.hit = 0

    def fn(self, symbol, notional=None):
        n = float(notional if notional is not None else self.notional)

        def f(ts):
            return self.cm.cost_bps(symbol, str(ts.date()), ts.time(), n)
        return f


# ======================================================================
# A. rotation_sim
# ======================================================================

_ROT_CTX = {"sym": None, "bud": 15000.0}


def patch_rotation(rot, ec):
    """Wrap rotation_sim so every simulate_trades call is priced by the
    measured model. `rot` is the imported rotation_sim module."""
    orig_memo = rot._memo_sim
    orig_sim = rot.dt.simulate_trades

    def memo_sim(memo, key, fn):
        # key = ("sim", symbol, entry_start, budget) + mk
        prev = dict(_ROT_CTX)
        if isinstance(key, tuple) and len(key) >= 4 and key[0] == "sim":
            _ROT_CTX["sym"] = key[1]
            _ROT_CTX["bud"] = float(key[3])
        try:
            return orig_memo(memo, key, fn)
        finally:
            _ROT_CTX.update(prev)

    def sim(df1m, **kw):
        sym = _ROT_CTX["sym"]
        if sym is None:
            return orig_sim(df1m, **kw)
        bud = kw.get("budget") or _ROT_CTX["bud"]
        kw = dict(kw)
        kw["cost_model"] = "measured"
        kw["cost_bps_fn"] = ec.fn(sym, bud)
        return orig_sim(df1m, **kw)

    rot._memo_sim = memo_sim
    rot.dt.simulate_trades = sim
    return orig_memo, orig_sim


# ======================================================================
# B. vs2_wide
# ======================================================================

_VS2_TAG = {}          # id(sliced DataFrame) -> (symbol, df ref)


def patch_vs2(vw, ec):
    """Wrap vs2_wide so every simulate_trades call is priced measured.

    `vs2_wide.day_cands` is the one place the (symbol, sliced bars) pair
    exists together (vs2_wide.py:396-407); `run_day` hands exactly that
    slice object to the engine, so tagging by identity there is exact.
    The dict holds a reference to the frame so an id can never be
    recycled underneath the tag, and is cleared per day."""
    orig_cands = vw.day_cands
    orig_sim = vw.dt.simulate_trades

    def day_cands(date, sim_from):
        out = orig_cands(date, sim_from)
        _VS2_TAG.clear()
        for c in out:
            _VS2_TAG[id(c["df"])] = (c["sym"], c["df"])
        return out

    def sim(df1m, **kw):
        got = _VS2_TAG.get(id(df1m))
        if got is None:
            raise RuntimeError("cr_engine: could not resolve symbol for "
                               "a vs2_wide simulate_trades call")
        kw = dict(kw)
        kw["cost_model"] = "measured"
        kw["cost_bps_fn"] = ec.fn(got[0], kw.get("budget") or 15000.0)
        return orig_sim(df1m, **kw)

    vw.day_cands = day_cands
    vw.dt.simulate_trades = sim
    return orig_cands, orig_sim


# ======================================================================
# C. rl2 -- exact re-pricing of a cost-independent ledger
# ======================================================================

def reprice(trades, cm, flat_bps=None):
    """Re-price plan/rl2/sim.run_day trades under a new cost model.

    A trade dict carries date, sym, m_in, px_in, sh, m_out, px_out and
    `notional` = sh*px_in*(1+c_in_old). The GROSS is cost-free:
        gross = sh * (px_out - px_in)
    and the new P&L is
        sh*px_out*(1-c_out_new) - sh*px_in*(1+c_in_new).
    `flat_bps` reproduces the incumbent ladder instead (identity check).
    """
    out = []
    for t in trades:
        sh, pin, pout = t["sh"], t["px_in"], t["px_out"]
        notion = sh * pin
        if flat_bps is not None:
            ci = (flat_bps + 50.0 * t["ext_in"]) / 1e4
            co = (flat_bps + 50.0 * t["ext_out"]) / 1e4
        else:
            ci = cm.cost_bps(t["sym"], t["date"], _m2t(t["m_in"]),
                             notion) / 1e4
            co = cm.cost_bps(t["sym"], t["date"], _m2t(t["m_out"]),
                             sh * pout) / 1e4
        pnl = sh * pout * (1.0 - co) - sh * pin * (1.0 + ci)
        u = dict(t)
        u["pnl"] = float(pnl)
        u["gross"] = float(sh * (pout - pin))
        u["c_in_bps"] = ci * 1e4
        u["c_out_bps"] = co * 1e4
        out.append(u)
    return out


def _m2t(minute):
    """rl2's minute grid is minutes from 00:00 ET (RTH_LO = 330)."""
    m = int(minute)
    return dtime((m // 60) % 24, m % 60)


def assert_path_cost_free(sim_mod, days, n=6):
    """Prove rl2's simulated PATH does not depend on the cost ladder by
    re-running with the fee tripled and asserting every entry/exit
    minute and price is identical."""
    import numpy as np
    base_fee, base_ext = sim_mod.FEE_BPS, sim_mod.EXT_BPS
    checks = bad = 0
    try:
        for d in days[:n]:
            rng = np.random.default_rng(7)
            sc = rng.standard_normal((sim_mod.T, d.S))
            a, _ = sim_mod.run_day(d, sc, ("horizon", 60))
            sim_mod.FEE_BPS, sim_mod.EXT_BPS = base_fee * 3, base_ext * 3
            b, _ = sim_mod.run_day(d, sc, ("horizon", 60))
            sim_mod.FEE_BPS, sim_mod.EXT_BPS = base_fee, base_ext
            assert len(a) == len(b)
            for x, y in zip(a, b):
                checks += 1
                if not (x["m_in"] == y["m_in"] and x["m_out"] == y["m_out"]
                        and x["px_in"] == y["px_in"]
                        and x["px_out"] == y["px_out"]
                        and x["sh"] == y["sh"] and x["sym"] == y["sym"]):
                    bad += 1
    finally:
        sim_mod.FEE_BPS, sim_mod.EXT_BPS = base_fee, base_ext
    return checks, bad


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


if __name__ == "__main__":
    print(__doc__)
