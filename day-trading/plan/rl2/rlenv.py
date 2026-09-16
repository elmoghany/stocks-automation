"""RL-SERIES v2, APPROACHES 2 & 3 (2026-09-16): the wide-universe ticket env.

Structurally v1's `plan/rl/env.py` -- same ticket rules, same cost ladder,
same next-bar-open fills, same forced flatten, same reward (change in
mark-to-market equity in $1,000s so cost is in the learner's signal at
every step) -- with the two changes v2 is about:

  1. THE UNIVERSE. Day membership comes from plan/rl2/universe.py, which
     is causal by construction, so v1's `onset` eligibility gate is gone
     and PREMARKET decisions are legal. Everything the agent sees at step
     i comes from plan/rl2/features.py, which the poison test certifies.
  2. THE DECISION GRID runs 04:00-19:55 ET, 192 steps of 5 minutes.

The agent chooses among K_SLOTS names ranked by TRAILING-5-MINUTE DOLLAR
VOLUME (feature `log_dv5`) -- a liquidity proxy, not a return predictor,
identical for every policy and every control, so the slotting cannot
favour one of them.
"""
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import features as FT                                         # noqa: E402

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    gym, spaces = None, None

FEAT = HERE / "out" / "feat"
NF = FT.NF
NG = 6
NGLOB = 7
K_SLOTS = 20
P_SLOTS = 7
TICKETS = [15000.0] * 6 + [10000.0]
MAX_TICKETS = 7
MIN_NOTIONAL = 500.0
STEPS = FT.STEPS
NSTEP = FT.T
RTH_LO, RTH_HI = FT.RTH_LO, FT.RTH_HI

TRAIN_END = "2025-06-01"
VAL_END = "2025-08-01"
TEST_END = "2026-08-07"


class DayData:
    __slots__ = ("date", "syms", "S", "feat", "mark", "printed", "fill_o",
                 "volcap", "flat_px", "flat_min", "slots", "tgt", "tgt_ok")

    def __init__(self, path):
        z = np.load(path, allow_pickle=False)
        self.date = Path(path).stem
        self.syms = [str(s) for s in z["syms"]]
        self.S = len(self.syms)
        self.feat = z["F"]
        self.mark = z["mark"].astype(np.float64)
        self.printed = z["printed"]
        self.fill_o = z["fill_o"].astype(np.float64)
        self.volcap = z["volcap"].astype(np.float64)
        self.flat_px = z["flat_px"].astype(np.float64)
        self.flat_min = z["flat_min"]
        self.tgt = z["tgt"]
        self.tgt_ok = z["tgt_ok"]
        key = np.where(self.printed, self.feat[:, :, 9], -1.0)
        order = np.argsort(-key, axis=1, kind="stable")[:, :K_SLOTS]
        keep = np.take_along_axis(key, order, axis=1) >= 0
        sl = np.where(keep, order, -1).astype(np.int32)
        if sl.shape[1] < K_SLOTS:
            sl = np.concatenate([sl, np.full((sl.shape[0],
                                              K_SLOTS - sl.shape[1]), -1,
                                             np.int32)], axis=1)
        self.slots = sl


class Dataset:
    def __init__(self, dates):
        self.days = [DayData(FEAT / f"{d}.npz") for d in dates]
        self.norm = None

    def fit_norm(self):
        X = np.concatenate([d.feat[d.printed] for d in self.days
                            if d.printed.any()])
        self.norm = (X.mean(0).astype(np.float32),
                     (X.std(0) + 1e-6).astype(np.float32))
        return self.norm

    def set_norm(self, n):
        self.norm = n
        return self


def splits():
    dates = sorted(p.stem for p in FEAT.glob("*.npz"))
    return {"train": [d for d in dates if d < TRAIN_END],
            "val": [d for d in dates if TRAIN_END <= d < VAL_END],
            "test": [d for d in dates if VAL_END <= d < TEST_END]}


class TicketEnv(gym.Env if gym else object):
    metadata = {"render_modes": []}

    def __init__(self, dataset, norm=None, leak=False, leak_k=6,
                 shuffle_days=True, seed=0, fee_bps=FT.FEE_BPS,
                 ext_bps=FT.EXT_BPS, record=False):
        super().__init__()
        self.ds = dataset
        self.norm = norm if norm is not None else dataset.norm
        assert self.norm is not None, "fit or pass a TRAIN-fitted normalizer"
        self.leak, self.leak_k = leak, int(leak_k)
        self.shuffle_days = shuffle_days
        self.fee, self.ext = fee_bps / 1e4, ext_bps / 1e4
        self.record = record
        self._rng = np.random.default_rng(seed)
        self._order = np.arange(len(dataset.days))
        self._ptr = len(self._order)
        self.obs_dim = (K_SLOTS * NF + K_SLOTS + P_SLOTS * NG + NGLOB
                        + (K_SLOTS if leak else 0))
        self.n_actions = 1 + K_SLOTS + P_SLOTS
        if gym:
            self.observation_space = spaces.Box(-10.0, 10.0, (self.obs_dim,),
                                                np.float32)
            self.action_space = spaces.Discrete(self.n_actions)
        self.trades, self.day_results = [], []
        self.reset(seed=seed)

    def _next_day(self):
        if self._ptr >= len(self._order):
            if self.shuffle_days:
                self._rng.shuffle(self._order)
            self._ptr = 0
        d = self.ds.days[self._order[self._ptr]]
        self._ptr += 1
        return d

    def _cm(self, minute, side):
        c = self.fee + (self.ext if (minute < RTH_LO or minute >= RTH_HI)
                        else 0.0)
        return (1.0 + c) if side > 0 else (1.0 - c)

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self.d = self._next_day()
        self.i = 0
        self.pos_sym = np.full(P_SLOTS, -1, np.int32)
        self.pos_sh = np.zeros(P_SLOTS)
        self.pos_px = np.zeros(P_SLOTS)
        self.pos_min = np.zeros(P_SLOTS, np.int32)
        self.tickets = 0
        self.realized = self.equity = 0.0
        self.n_invalid = 0
        self.ep = dict(entries=0, exits=0, ext_fills=0, rth_fills=0, forced=0,
                       ext_pnl=0.0, rth_pnl=0.0)
        self._dt = []
        return self._obs(), {}

    def _obs(self):
        d, i = self.d, self.i
        mu, sd = self.norm
        sl = d.slots[i]
        ok = sl >= 0
        f = np.zeros((K_SLOTS, NF), np.float32)
        if ok.any():
            f[ok] = (d.feat[i, sl[ok]] - mu) / sd
        np.clip(f, -5.0, 5.0, out=f)
        held = set(int(s) for s in self.pos_sym if s >= 0)
        avail = np.zeros(K_SLOTS, np.float32)
        for k in range(K_SLOTS):
            s = int(sl[k])
            if s >= 0 and s not in held and self.tickets < MAX_TICKETS \
                    and d.printed[i, s]:
                avail[k] = 1.0
        g = np.zeros((P_SLOTS, NG), np.float32)
        m = STEPS[i]
        for p in range(P_SLOTS):
            s = int(self.pos_sym[p])
            if s < 0:
                continue
            mk = d.mark[i, s]
            ur = math.log(max(mk, 1e-9) / max(self.pos_px[p], 1e-9))
            g[p] = (1.0, np.clip(ur * 10.0, -5, 5),
                    (m - self.pos_min[p]) / 60.0,
                    np.clip((d.feat[i, s, 1] - mu[1]) / sd[1], -5, 5),
                    np.clip((d.feat[i, s, 4] - mu[4]) / sd[4], -5, 5),
                    np.clip((d.feat[i, s, 9] - mu[9]) / sd[9], -5, 5))
        glob = np.array([(RTH_HI - m) / 60.0,
                         (STEPS[-1] - m) / 60.0,
                         1.0 if (m >= RTH_HI or m < RTH_LO) else 0.0,
                         self.tickets / MAX_TICKETS,
                         float((self.pos_sym >= 0).sum()) / P_SLOTS,
                         np.clip(self.equity / 1000.0, -10, 10),
                         i / max(NSTEP - 1, 1)], np.float32)
        parts = [f.reshape(-1), avail, g.reshape(-1), glob]
        if self.leak:
            nr = np.zeros(K_SLOTS, np.float32)
            if ok.any():
                j = min(i + self.leak_k, NSTEP - 1)
                a = d.fill_o[i, sl[ok]]
                b = d.fill_o[j, sl[ok]]
                r = np.log(np.maximum(b, 1e-9) / np.maximum(a, 1e-9))
                nr[ok] = np.clip(np.nan_to_num(r) * 20.0, -5, 5)
            parts.append(nr)
        return np.concatenate(parts).astype(np.float32)

    def action_masks(self):
        d, i = self.d, self.i
        m = np.zeros(self.n_actions, bool)
        m[0] = True
        sl = d.slots[i]
        held = set(int(s) for s in self.pos_sym if s >= 0)
        for k in range(K_SLOTS):
            s = int(sl[k])
            m[1 + k] = (s >= 0 and s not in held
                        and self.tickets < MAX_TICKETS and bool(d.printed[i, s]))
        for p in range(P_SLOTS):
            s = int(self.pos_sym[p])
            m[1 + K_SLOTS + p] = s >= 0 and bool(d.printed[i, s])
        return m

    def _mtm(self):
        d, i = self.d, self.i
        u = 0.0
        for p in range(P_SLOTS):
            s = int(self.pos_sym[p])
            if s >= 0:
                u += self.pos_sh[p] * (d.mark[i, s] - self.pos_px[p])
        return self.realized + u

    def _buy(self, k):
        d, i = self.d, self.i
        s = int(d.slots[i, k])
        if s < 0 or self.tickets >= MAX_TICKETS or \
                any(int(x) == s for x in self.pos_sym):
            self.n_invalid += 1
            return
        raw = d.fill_o[i, s]
        if not np.isfinite(raw) or raw <= 0:
            return
        fm = int(STEPS[i]) + 1
        px = float(raw) * self._cm(fm, +1)
        sh = math.floor(TICKETS[self.tickets] / px)
        sh = min(sh, math.floor(max(d.volcap[i, s], 0.0)))
        if sh <= 0 or sh * px < MIN_NOTIONAL:
            return
        p = int(np.where(self.pos_sym < 0)[0][0])
        self.pos_sym[p], self.pos_sh[p] = s, sh
        self.pos_px[p], self.pos_min[p] = px, fm
        self.tickets += 1
        self.ep["entries"] += 1
        if self.record:
            self._dt.append(dict(date=d.date, sym=d.syms[s], side="B",
                                 minute=fm, px=px, sh=int(sh)))

    def _sell(self, p, forced=False):
        d, i = self.d, self.i
        s = int(self.pos_sym[p])
        if s < 0:
            self.n_invalid += 1
            return
        if forced:
            raw, fm = d.flat_px[s], int(d.flat_min[s])
            if not np.isfinite(raw):
                raw, fm = d.mark[i, s], int(STEPS[i])
            self.ep["forced"] += 1
        else:
            raw, fm = d.fill_o[i, s], int(STEPS[i]) + 1
            if not np.isfinite(raw) or raw <= 0:
                return
        px = float(raw) * self._cm(fm, -1)
        pnl = self.pos_sh[p] * (px - self.pos_px[p])
        self.realized += pnl
        self.ep["exits"] += 1
        ext = fm < RTH_LO or fm >= RTH_HI
        self.ep["ext_fills" if ext else "rth_fills"] += 1
        self.ep["ext_pnl" if ext else "rth_pnl"] += float(pnl)
        if self.record:
            self._dt.append(dict(date=d.date, sym=d.syms[s], side="S",
                                 minute=fm, px=px, sh=int(self.pos_sh[p]),
                                 pnl=float(pnl), forced=bool(forced),
                                 hold_min=int(fm - self.pos_min[p]),
                                 ext=bool(ext)))
        self.pos_sym[p] = -1
        self.pos_sh[p] = 0.0

    def step(self, action):
        a = int(action)
        if a == 0:
            pass
        elif a <= K_SLOTS:
            self._buy(a - 1)
        else:
            self._sell(a - 1 - K_SLOTS)
        prev = self.equity
        self.i += 1
        done = self.i >= NSTEP
        if done:
            self.i = NSTEP - 1
            for p in range(P_SLOTS):
                if self.pos_sym[p] >= 0:
                    self._sell(p, forced=True)
        self.equity = self._mtm()
        r = (self.equity - prev) / 1000.0
        info = {}
        if done:
            info = dict(date=self.d.date, pnl=float(self.equity),
                        tickets=int(self.tickets), invalid=int(self.n_invalid),
                        **self.ep)
            self.day_results.append(info)
            if self.record:
                self.trades.extend(self._dt)
        return self._obs(), float(r), bool(done), False, info


def run_epoch(env, policy, record=False):
    env.shuffle_days = False
    env._order = np.arange(len(env.ds.days))
    env._ptr = 0
    env.record = record
    env.day_results, env.trades = [], []
    for _ in range(len(env.ds.days)):
        obs, _ = env.reset()
        done = False
        while not done:
            if hasattr(policy, "predict"):
                if hasattr(env, "action_masks") and \
                        type(policy).__name__ == "MaskablePPO":
                    a, _ = policy.predict(obs, deterministic=True,
                                          action_masks=env.action_masks())
                else:
                    a, _ = policy.predict(obs, deterministic=True)
            else:
                a = policy(obs, env)
            obs, r, done, _, info = env.step(a)
    return summarize(env.day_results)


def summarize(days, label=""):
    if not days:
        return {"label": label, "days": 0}
    pnl = np.array([d["pnl"] for d in days], float)
    tk = np.array([d["tickets"] for d in days], float)
    eq = np.concatenate([[0.0], np.cumsum(pnl)])
    dd = float((eq - np.maximum.accumulate(eq)).min())
    sd = pnl.std(ddof=1) if len(pnl) > 1 else 0.0
    n_t = float(tk.sum())
    return {"label": label, "days": len(days),
            "total": round(float(pnl.sum()), 2),
            "tickets": int(n_t),
            "per_ticket": round(float(pnl.sum() / n_t), 3) if n_t else 0.0,
            "tickets_per_day": round(float(tk.mean()), 2),
            "sharpe": round(float(pnl.mean() / sd * np.sqrt(252)), 3)
            if sd else 0.0,
            "max_dd": round(dd, 2),
            "ext_pnl": round(float(sum(d["ext_pnl"] for d in days)), 2),
            "rth_pnl": round(float(sum(d["rth_pnl"] for d in days)), 2),
            "ext_fills": int(sum(d["ext_fills"] for d in days)),
            "rth_fills": int(sum(d["rth_fills"] for d in days)),
            "forced": int(sum(d["forced"] for d in days)),
            "invalid": int(sum(d["invalid"] for d in days))}
