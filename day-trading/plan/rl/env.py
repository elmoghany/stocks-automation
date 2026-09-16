"""RL-SERIES (2026-09-16): causal intraday ticket env for the halal gapper pool.

ONE EPISODE = ONE TRADING DAY. Decisions every STEP minutes from 09:30 ET
to 19:55 ET; a decision taken after minute m is FILLED AT THE OPEN OF MINUTE
m+1. Nothing is carried overnight: every open ticket is force-flattened at
the end of the day.

TICKET RULES (the live cash-account rules, not a continuous-weight
portfolio): each entry is a flat $15,000 notional, the 7th and last is
$10,000, so at most 7 tickets and at most $100,000 deployed per day; at
most one open ticket per symbol; long only.

COSTS
  FEE_BPS     = 10 bps per side, always.
  EXT_BPS     = 50 bps ADDITIONAL on any fill whose minute is outside
                09:30-16:00 ET (the engine's premarket/extended spread
                haircut). In practice only exits and post-16:00 entries can
                pay it, because of the eligibility rule below.
  VOL_CAP     = a fill may not exceed 20% of the symbol's volume over the
                trailing STEP minutes ending at the decision minute. A
                capped fill is sized down; if it sizes below MIN_NOTIONAL
                the order is dropped.
  NO-PRINT MINUTES ARE UNTRADEABLE: if minute m+1 has no bar, the order
                simply does not happen.

ELIGIBILITY (leak-safe; NOTES "MX-SERIES RETRACTION #2", 2026-09-16)
  A name may be looked at, ranked, or bought at minute m only if a
  REGULAR-SESSION bar (>= 09:30) at or before m has printed >= +10% over
  prev_close. gappers_novol_* membership is itself conditioned on the
  regular-session high, so anything earlier is future-conditioned. There
  are therefore no premarket entries anywhere in this study.

CAUSALITY
  Every feature at step m is built from bars with index <= m only. The
  normalizer (per-feature mean/std) is fitted on TRAIN DAYS ONLY and never
  refitted. Realized returns are never an input. Reward at step i is the
  change in mark-to-market equity between step i and step i+1, which is
  only knowable at i+1 -- it is a consequence of the action, not an input
  to it. `DayData.poison` and `DayData.shuffle_returns` implement the two
  adversarial controls; see honesty.py.
"""
import json
import math
from pathlib import Path

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:                      # data side usable without gymnasium
    gym, spaces = None, None

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DAYS = OUT / "days"

NMIN = 960
BASE_MIN = 4 * 60
RTH_LO = 330          # 09:30 ET
RTH_HI = 720          # 16:00 ET
STEP = 5              # minutes between decisions
FIRST_STEP_MIN = RTH_LO
LAST_STEP_MIN = NMIN - 5          # 19:55 -> fill at 19:56

FEE_BPS = 10.0
EXT_BPS = 50.0
VOL_CAP_FRAC = 0.20
MIN_NOTIONAL = 500.0
TICKET_NOTIONALS = [15000.0] * 6 + [10000.0]
MAX_TICKETS = len(TICKET_NOTIONALS)
K_SLOTS = 10
P_SLOTS = MAX_TICKETS

NF = 15               # per-candidate features
NG = 6                # per-position features
NGLOB = 7

TRAIN_START, TRAIN_END = "2024-10-22", "2025-05-30"
VAL_START, VAL_END = "2025-06-02", "2025-07-31"
TEST_START, TEST_END = "2025-08-01", "2026-07-31"
EXTRA_START, EXTRA_END = "2026-08-01", "2026-12-31"

STEP_MINS = np.arange(FIRST_STEP_MIN, LAST_STEP_MIN + 1, STEP)
NSTEP = len(STEP_MINS)


# ---------------------------------------------------------------- day data
def _ffill_rows(a):
    """Forward-fill NaNs along axis 1 (per symbol)."""
    idx = np.where(~np.isnan(a), np.arange(a.shape[1])[None, :], 0)
    np.maximum.accumulate(idx, axis=1, out=idx)
    return a[np.arange(a.shape[0])[:, None], idx]


class DayData:
    """Everything the env needs for one trading day, precomputed causally."""

    __slots__ = ("date", "syms", "prev_close", "onset", "S", "feat", "mark",
                 "fill_o", "volcap", "elig", "slots", "flat_px", "flat_min",
                 "next_ret", "label", "printed_now")

    def __init__(self, path, label=""):
        z = np.load(path, allow_pickle=False)
        self.date = Path(path).stem
        self.label = label
        self.syms = [str(s) for s in z["syms"]]
        self.prev_close = z["prev_close"].astype(np.float64)
        self.onset = z["onset"].astype(np.int32)
        o, h, l, c, v = (z[k].astype(np.float64) for k in "ohlcv")
        self.S = len(self.syms)
        self._build(o, h, l, c, v)

    # -- construction ------------------------------------------------------
    def _build(self, o, h, l, c, v):
        S = self.S
        cf = _ffill_rows(c)                      # last printed close <= m
        hf = np.fmax.accumulate(np.where(np.isnan(h), -np.inf, h), axis=1)
        lf = np.fmin.accumulate(np.where(np.isnan(l), np.inf, l), axis=1)
        printed = ~np.isnan(c)
        dv = np.nan_to_num(c) * v
        cdv = np.cumsum(dv, axis=1)
        cvol = np.cumsum(v, axis=1)
        cprint = np.cumsum(printed, axis=1)
        lr = np.zeros_like(cf)
        lr[:, 1:] = np.log(np.maximum(cf[:, 1:], 1e-9) /
                           np.maximum(cf[:, :-1], 1e-9))
        lr = np.nan_to_num(lr)
        clr = np.cumsum(lr, axis=1)
        clr2 = np.cumsum(lr * lr, axis=1)
        rng = np.log(np.maximum(np.nan_to_num(h, nan=1.0), 1e-9) /
                     np.maximum(np.nan_to_num(l, nan=1.0), 1e-9))
        rng = np.where(printed, rng, 0.0)
        crng = np.cumsum(rng, axis=1)

        M = STEP_MINS
        T = len(M)
        mark = cf[:, M].T.copy()                            # [T,S]
        self.mark = mark
        nxt = np.minimum(M + 1, NMIN - 1)
        self.fill_o = o[:, nxt].T.copy()                    # [T,S] NaN=no print
        # printed_now is bar m itself. fill_o is bar m+1 and is therefore
        # FUTURE at decision time: it is used to price a fill, never to
        # decide one. Availability masks use printed_now, so the agent
        # cannot peek at whether the next minute will print.
        self.printed_now = printed[:, M].T.copy()           # [T,S] bool

        def win(cum, w):
            lo = np.maximum(M - w, -1)
            a = cum[:, M]
            b = np.where(lo >= 0, cum[:, np.maximum(lo, 0)], 0.0)
            return (a - b).T                                # [T,S]

        vol5 = win(cvol, STEP)
        self.volcap = VOL_CAP_FRAC * vol5

        pc = self.prev_close[None, :]
        with np.errstate(divide="ignore", invalid="ignore"):
            F = np.zeros((T, S, NF), np.float64)
            F[:, :, 0] = np.log(mark / pc)
            for j, w in enumerate((5, 15, 30), start=1):
                prev = cf[:, np.maximum(M - w, 0)].T
                F[:, :, j] = np.log(np.maximum(mark, 1e-9) /
                                    np.maximum(prev, 1e-9))
            F[:, :, 4] = np.log(np.maximum(mark, 1e-9) /
                                np.maximum(hf[:, M].T, 1e-9))
            F[:, :, 5] = np.log(np.maximum(mark, 1e-9) /
                                np.maximum(lf[:, M].T, 1e-9))
            dv30, vv30 = win(cdv, 30), win(cvol, 30)
            vwap30 = dv30 / np.maximum(vv30, 1.0)
            F[:, :, 6] = np.where(vv30 > 0,
                                  np.log(np.maximum(mark, 1e-9) /
                                         np.maximum(vwap30, 1e-9)), 0.0)
            dv5 = win(cdv, STEP)
            F[:, :, 7] = np.log1p(dv5)
            elapsed = np.maximum(M[:, None] + 1, 1).astype(np.float64)
            day_dv = cdv[:, M].T
            F[:, :, 8] = np.log((dv5 / STEP + 1.0) / (day_dv / elapsed + 1.0))
            m30, m230 = win(clr, 30) / 30.0, win(clr2, 30) / 30.0
            F[:, :, 9] = np.sqrt(np.maximum(m230 - m30 * m30, 0.0))
            n5 = np.maximum(win(cprint, STEP), 1.0)
            F[:, :, 10] = win(crng, STEP) / n5
            F[:, :, 11] = win(cprint, 30) / 30.0
            F[:, :, 12] = (M[:, None] - self.onset[None, :]) / 60.0
            F[:, :, 13] = np.log(np.maximum(mark, 1e-9))
            F[:, :, 14] = np.log(np.maximum(mark, 1e-9) / (pc * 1.10))
        self.feat = np.nan_to_num(F, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

        self.elig = (self.onset[None, :] >= 0) & (M[:, None] >= self.onset[None, :])

        # causal slot ranking: trailing-30-min dollar volume among eligible
        rank_key = np.where(self.elig, win(cdv, 30), -1.0)
        order = np.argsort(-rank_key, axis=1, kind="stable")[:, :K_SLOTS]
        keep = np.take_along_axis(rank_key, order, axis=1) >= 0
        sl = np.where(keep, order, -1).astype(np.int32)
        if sl.shape[1] < K_SLOTS:        # thin day: fewer names than slots
            sl = np.concatenate(
                [sl, np.full((sl.shape[0], K_SLOTS - sl.shape[1]), -1,
                             np.int32)], axis=1)
        self.slots = sl

        # forced flatten reference: last printed bar of the day per symbol
        last = np.where(printed.any(axis=1), printed.shape[1] - 1 -
                        np.argmax(printed[:, ::-1], axis=1), -1)
        self.flat_min = last.astype(np.int32)
        self.flat_px = np.where(last >= 0, c[np.arange(S), np.maximum(last, 0)],
                                np.nan)
        # clairvoyant control input only (never used unless leak=True)
        fo = self.fill_o
        nr = np.zeros_like(fo)
        nr[:-1] = np.log(np.maximum(fo[1:], 1e-9) / np.maximum(fo[:-1], 1e-9))
        self.next_ret = np.nan_to_num(nr).astype(np.float32)

    # -- adversarial transforms -------------------------------------------
    @staticmethod
    def _raw(path):
        z = np.load(path, allow_pickle=False)
        return [z[k].astype(np.float64) for k in "ohlcv"], z

    @classmethod
    def poisoned(cls, path, after_min, seed=0, label=""):
        """Copy of the day whose bars STRICTLY AFTER minute `after_min` are
        replaced by garbage. Any decision at a step <= after_min must be
        bit-identical to the clean day's."""
        (o, h, l, c, v), z = cls._raw(path)
        rng = np.random.default_rng(seed)
        sl = slice(after_min + 1, None)
        shape = o[:, sl].shape
        g = rng.uniform(0.5, 500.0, size=shape)
        o[:, sl] = g
        h[:, sl] = g * rng.uniform(1.0, 1.5, size=shape)
        l[:, sl] = g * rng.uniform(0.5, 1.0, size=shape)
        c[:, sl] = g * rng.uniform(0.7, 1.3, size=shape)
        v[:, sl] = rng.integers(1, 10 ** 7, size=shape)
        d = cls.__new__(cls)
        d.date, d.label = Path(path).stem, label
        d.syms = [str(s) for s in z["syms"]]
        d.prev_close = z["prev_close"].astype(np.float64)
        d.onset = z["onset"].astype(np.int32)
        d.S = len(d.syms)
        d._build(o, h, l, c, v)
        return d

    @classmethod
    def shuffled(cls, path, seed=0, label=""):
        """SHUFFLED-LABELS CONTROL. Within each symbol-day the sequence of
        1-minute log returns over the PRINTED minutes is randomly permuted
        and the price path rebuilt from the first printed price; volumes and
        the print mask are untouched. Level, drift and the marginal return
        distribution survive; all temporal structure (momentum, reversal,
        the shape of the +10% break) is destroyed. Features and P&L are then
        both computed from the same shuffled path, so nothing the agent sees
        can predict what it earns. An agent that still makes money out of
        sample here is reading a leak in the harness, not the market."""
        (o, h, l, c, v), z = cls._raw(path)
        rng = np.random.default_rng(seed)
        S, T = c.shape
        for i in range(S):
            idx = np.where(~np.isnan(c[i]))[0]
            if len(idx) < 3:
                continue
            px = c[i, idx]
            r = np.diff(np.log(np.maximum(px, 1e-9)))
            rng.shuffle(r)
            new = np.empty_like(px)
            new[0] = px[0]
            new[1:] = px[0] * np.exp(np.cumsum(r))
            scale = new / np.maximum(px, 1e-9)
            c[i, idx] = new
            for a in (o, h, l):
                a[i, idx] = a[i, idx] * scale
            hi = np.maximum.reduce([o[i, idx], c[i, idx], h[i, idx]])
            lo2 = np.minimum.reduce([o[i, idx], c[i, idx], l[i, idx]])
            h[i, idx], l[i, idx] = hi, lo2
        d = cls.__new__(cls)
        d.date, d.label = Path(path).stem, label
        d.syms = [str(s) for s in z["syms"]]
        d.prev_close = z["prev_close"].astype(np.float64)
        on = z["onset"].astype(np.int32)
        # the onset must be recomputed on the shuffled path, otherwise the
        # eligibility mask would still carry the real path's information
        gap = d.prev_close[:, None] * 1.0999
        hit = (h[:, RTH_LO:] >= gap)
        has = hit.any(axis=1)
        d.onset = np.where(has, np.argmax(hit, axis=1) + RTH_LO, -1).astype(np.int32)
        del on
        d.S = len(d.syms)
        d._build(o, h, l, c, v)
        return d


# ---------------------------------------------------------------- dataset
def day_files(label):
    p = DAYS / label
    return sorted(p.glob("*.npz")) if p.exists() else []


def split_files():
    """Date-strict splits. train/val come from the y2025 pool file, test from
    `year`, extra from `aug2026`; the pool files do not overlap in date."""
    y = day_files("y2025")
    yr = day_files("year")
    ex = day_files("aug2026")
    def between(fs, a, b):
        return [f for f in fs if a <= f.stem <= b]
    return {
        "train": between(y, TRAIN_START, TRAIN_END),
        "val": between(y, VAL_START, VAL_END),
        "test": between(yr, TEST_START, TEST_END),
        "extra": between(ex, EXTRA_START, EXTRA_END),
    }


class Dataset:
    """Holds DayData for a list of files, optionally transformed."""

    def __init__(self, files, transform=None, seed=0, label=""):
        self.days = []
        for f in files:
            if transform == "shuffle":
                self.days.append(DayData.shuffled(f, seed=seed, label=label))
            else:
                self.days.append(DayData(f, label=label))
        self.norm = None

    def fit_norm(self):
        xs = []
        for d in self.days:
            m = d.elig
            if m.any():
                xs.append(d.feat[m])
        X = np.concatenate(xs) if xs else np.zeros((1, NF), np.float32)
        mu = X.mean(0)
        sd = X.std(0) + 1e-6
        self.norm = (mu.astype(np.float32), sd.astype(np.float32))
        return self.norm

    def set_norm(self, norm):
        self.norm = norm
        return self


# ---------------------------------------------------------------- the env
class TicketEnv(gym.Env if gym else object):
    metadata = {"render_modes": []}

    def __init__(self, dataset, norm=None, leak=False, shuffle_days=True,
                 seed=0, fee_bps=FEE_BPS, ext_bps=EXT_BPS,
                 vol_cap=VOL_CAP_FRAC, record=False, leak_k=1):
        super().__init__()
        self.ds = dataset
        self.norm = norm if norm is not None else dataset.norm
        assert self.norm is not None, "fit or pass a TRAIN-fitted normalizer"
        self.leak = leak
        # POSITIVE CONTROL ONLY. leak_k is how many decision steps of
        # foresight the clairvoyant observation carries (1 = the next 5
        # minutes, 6 = the next 30). It exists to measure whether the
        # harness has the statistical power to see an edge at all; leak=False
        # is the only setting any reported result may use.
        self.leak_k = int(leak_k)
        self.shuffle_days = shuffle_days
        self.fee = fee_bps / 1e4
        self.ext = ext_bps / 1e4
        self.vol_cap = vol_cap
        self.record = record
        self._rng = np.random.default_rng(seed)
        self._order = np.arange(len(dataset.days))
        self._ptr = len(self._order)
        obs_dim = K_SLOTS * NF + K_SLOTS + P_SLOTS * NG + NGLOB + \
            (K_SLOTS if leak else 0)
        self.obs_dim = obs_dim
        self.n_actions = 1 + K_SLOTS + P_SLOTS
        if gym:
            self.observation_space = spaces.Box(-10.0, 10.0, (obs_dim,), np.float32)
            self.action_space = spaces.Discrete(self.n_actions)
        self.trades = []
        self.day_results = []
        self.reset(seed=seed)

    # -- helpers -----------------------------------------------------------
    def _next_day(self):
        if self._ptr >= len(self._order):
            if self.shuffle_days:
                self._rng.shuffle(self._order)
            self._ptr = 0
        d = self.ds.days[self._order[self._ptr]]
        self._ptr += 1
        return d

    def _cost_mult(self, minute, side):
        c = self.fee + (self.ext if (minute < RTH_LO or minute >= RTH_HI) else 0.0)
        return (1.0 + c) if side > 0 else (1.0 - c)

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self.d = self._next_day()
        self.i = 0                                  # step index
        self.pos_sym = np.full(P_SLOTS, -1, np.int32)
        self.pos_sh = np.zeros(P_SLOTS)
        self.pos_px = np.zeros(P_SLOTS)             # effective buy price
        self.pos_min = np.zeros(P_SLOTS, np.int32)
        self.tickets = 0
        self.deployed = 0.0
        self.realized = 0.0
        self.equity = 0.0
        self.n_invalid = 0
        self.ep = dict(entries=0, exits=0, cap_blocked=0, noprint_blocked=0,
                       ext_fills=0, rth_fills=0, forced=0, stale_forced=0)
        self._day_trades = []
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
        avail = np.zeros(K_SLOTS, np.float32)
        held = set(int(s) for s in self.pos_sym if s >= 0)
        for k in range(K_SLOTS):
            s = int(sl[k])
            if s < 0:
                continue
            if s in held or self.tickets >= MAX_TICKETS:
                continue
            if not d.printed_now[i, s]:
                continue
            avail[k] = 1.0
        g = np.zeros((P_SLOTS, NG), np.float32)
        m = STEP_MINS[i]
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
        glob = np.array([
            (RTH_HI - m) / 60.0,
            (LAST_STEP_MIN - m) / 60.0,
            1.0 if m >= RTH_HI else 0.0,
            self.tickets / MAX_TICKETS,
            float((self.pos_sym >= 0).sum()) / P_SLOTS,
            np.clip(self.equity / 1000.0, -10, 10),
            i / max(NSTEP - 1, 1),
        ], np.float32)
        parts = [f.reshape(-1), avail, g.reshape(-1), glob]
        if self.leak:
            nr = np.zeros(K_SLOTS, np.float32)
            if ok.any():
                j = min(i + self.leak_k, len(STEP_MINS) - 1)
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
            m[1 + k] = (s >= 0 and s not in held and
                        self.tickets < MAX_TICKETS and
                        bool(d.printed_now[i, s]))
        for p in range(P_SLOTS):
            s = int(self.pos_sym[p])
            m[1 + K_SLOTS + p] = s >= 0 and bool(d.printed_now[i, s])
        return m

    # -- dynamics ----------------------------------------------------------
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
        if s < 0 or self.tickets >= MAX_TICKETS:
            self.n_invalid += 1
            return
        if any(int(x) == s for x in self.pos_sym):
            self.n_invalid += 1
            return
        raw = d.fill_o[i, s]
        if not np.isfinite(raw) or raw <= 0:
            self.ep["noprint_blocked"] += 1
            return
        fm = STEP_MINS[i] + 1
        px = float(raw) * self._cost_mult(fm, +1)
        notional = TICKET_NOTIONALS[self.tickets]
        sh = math.floor(notional / px)
        cap = math.floor(max(d.volcap[i, s], 0.0))
        if sh > cap:
            sh = cap
            self.ep["cap_blocked"] += 1
        if sh <= 0 or sh * px < MIN_NOTIONAL:
            return
        p = int(np.where(self.pos_sym < 0)[0][0])
        self.pos_sym[p], self.pos_sh[p] = s, sh
        self.pos_px[p], self.pos_min[p] = px, fm
        self.tickets += 1
        self.deployed += sh * px
        self.ep["entries"] += 1
        self.ep["ext_fills" if (fm < RTH_LO or fm >= RTH_HI) else "rth_fills"] += 1
        if self.record:
            self._day_trades.append(dict(date=d.date, sym=d.syms[s], side="B",
                                         minute=int(fm), px=px, sh=int(sh)))

    def _sell(self, p, forced=False):
        d, i = self.d, self.i
        s = int(self.pos_sym[p])
        if s < 0:
            self.n_invalid += 1
            return
        if forced:
            raw, fm = d.flat_px[s], int(d.flat_min[s])
            if not np.isfinite(raw):
                raw, fm = d.mark[i, s], int(STEP_MINS[i])
            if fm < STEP_MINS[i]:
                self.ep["stale_forced"] += 1
            self.ep["forced"] += 1
        else:
            raw, fm = d.fill_o[i, s], STEP_MINS[i] + 1
            if not np.isfinite(raw) or raw <= 0:
                self.ep["noprint_blocked"] += 1
                return
        px = float(raw) * self._cost_mult(fm, -1)
        pnl = self.pos_sh[p] * (px - self.pos_px[p])
        self.realized += pnl
        self.ep["exits"] += 1
        self.ep["ext_fills" if (fm < RTH_LO or fm >= RTH_HI) else "rth_fills"] += 1
        if self.record:
            self._day_trades.append(dict(
                date=d.date, sym=d.syms[s], side="S", minute=int(fm), px=px,
                sh=int(self.pos_sh[p]), pnl=float(pnl), forced=bool(forced),
                hold_min=int(fm - self.pos_min[p]),
                ext=bool(fm < RTH_LO or fm >= RTH_HI)))
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
        reward = (self.equity - prev) / 1000.0
        info = {}
        if done:
            info = dict(date=self.d.date, pnl=float(self.equity),
                        tickets=int(self.tickets), deployed=float(self.deployed),
                        invalid=int(self.n_invalid), **self.ep)
            self.day_results.append(info)
            if self.record:
                self.trades.extend(self._day_trades)
        return self._obs(), float(reward), bool(done), False, info


# ---------------------------------------------------------------- rollouts
def run_epoch(env, policy, days=None, record=False):
    """One deterministic pass over every day in the dataset, in date order."""
    env.shuffle_days = False
    env._order = np.arange(len(env.ds.days))
    env._ptr = 0
    env.record = record
    env.day_results = []
    env.trades = []
    n = days if days is not None else len(env.ds.days)
    for _ in range(n):
        obs, _ = env.reset()
        done = False
        while not done:
            if hasattr(policy, "predict"):
                a, _ = policy.predict(obs, deterministic=True)
            else:
                a = policy(obs, env)
            obs, r, done, _, info = env.step(a)
    return summarize(env.day_results, env.trades)


def summarize(days, trades=None):
    if not days:
        return {"days": 0}
    pnl = np.array([d["pnl"] for d in days], float)
    tk = np.array([d["tickets"] for d in days], float)
    dep = np.array([d["deployed"] for d in days], float)
    eq = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))
    dd = float((np.concatenate([[0.0], eq]) - peak).min())
    n_t = float(tk.sum())
    out = {
        "days": len(days),
        "total_pnl": float(pnl.sum()),
        "pnl_per_day": float(pnl.mean()),
        "tickets": int(n_t),
        "tickets_per_day": float(tk.mean()),
        "pnl_per_ticket": float(pnl.sum() / n_t) if n_t else 0.0,
        "deployed": float(dep.sum()),
        "ret_on_deployed_pct": float(pnl.sum() / dep.sum() * 100) if dep.sum() else 0.0,
        "sharpe_daily_ann": float(pnl.mean() / (pnl.std() + 1e-9) * math.sqrt(252)),
        "max_dd": dd,
        "win_days_pct": float((pnl > 0).mean() * 100),
        "cap_blocked": int(sum(d["cap_blocked"] for d in days)),
        "noprint_blocked": int(sum(d["noprint_blocked"] for d in days)),
        "forced_flatten": int(sum(d["forced"] for d in days)),
        "stale_forced": int(sum(d["stale_forced"] for d in days)),
        "ext_fills": int(sum(d["ext_fills"] for d in days)),
        "rth_fills": int(sum(d["rth_fills"] for d in days)),
        "invalid_actions": int(sum(d["invalid"] for d in days)),
    }
    if trades:
        ex = [t for t in trades if t["side"] == "S"]
        if ex:
            e = [t for t in ex if t["ext"]]
            r = [t for t in ex if not t["ext"]]
            out["exit_ext_n"] = len(e)
            out["exit_ext_pnl"] = float(sum(t["pnl"] for t in e))
            out["exit_rth_n"] = len(r)
            out["exit_rth_pnl"] = float(sum(t["pnl"] for t in r))
            out["mean_hold_min"] = float(np.mean([t["hold_min"] for t in ex]))
    return out


# ---------------------------------------------------------------- policies
def random_policy(seed=0, p_trade=0.10):
    """Uniform over the LEGAL actions, with a tunable idle rate so the
    ticket budget is not spent in the first ten minutes. Uses exactly the
    same eligibility, slotting, fills and costs as the agents."""
    rng = np.random.default_rng(seed)

    def pol(obs, env):
        m = env.action_masks()
        legal = np.where(m)[0]
        legal = legal[legal != 0]
        if len(legal) == 0 or rng.random() > p_trade:
            return 0
        return int(rng.choice(legal))
    return pol


def hold_policy(obs, env):
    """Never trades. P&L is exactly zero; a sanity anchor for the harness."""
    return 0


def buy_first_policy(obs, env):
    """Non-learned reference: take the top liquidity slot as soon as legal,
    hold to the forced flatten. Not an alpha claim -- it measures what the
    eligible set does on its own, net of costs."""
    m = env.action_masks()
    for k in range(K_SLOTS):
        if m[1 + k]:
            return 1 + k
    return 0
