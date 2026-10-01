"""PAPER-3BOOK RL book: RL-SCOUT v2 approach-4 seed-0 rule, live.

PAPER ONLY, OPEN-ENDED. Real orders never, unless the user explicitly
authorizes them in conversation.

THE RULE (plan/rl2/results/rules_holdout_s0.json, engine plan/rl2/sim.py)
  every 5-minute grid step m (04:00-based grid; 09:30 = 330) inside the
  entry window, among universe names whose bar m PRINTED, in universe
  (alphabetical) order:
    dist_vwap_day < -0.00006   log(mark / VWAP), VWAP = sum(c*v)/sum(v)
                               over bars 04:00..m
    xs_breadth    < -0.02379   mean over PRINTED universe names of
                               log(mark / close-of-the-09:30-bar)
    log_price     <  2.75367   mark < ~$15.70
  buy at the OPEN of bar m+1 (no print -> no fill, attempt spent);
  notional min(ticket, 20% of the last 5 minutes' share volume), >= $500.
  exits, evaluated at every later 5-minute step on the mark (last close
  <= m): +5% take, mark <= 0.97 x peak-of-marks (trail), 240 min (tmax);
  exit fills at the OPEN of bar m+1 (no print -> carry); anything still
  open is flattened at the session-end bar's close.

CONFIGS
  published  7 tickets ($15k x6, $10k), <= 2 new per step, concurrent,
             window 330..720, flatten = the day's last printed bar
             (extended hours; +50 bps outside 09:30-16:00)
  live       ONE position at a time, $10,000 whole-share tickets, <= 7
             entries/day, window 330..715 (09:30..15:55), forced RTH
             flatten at the 15:59 bar close (see PAPER-3BOOK-RULES.md for
             why; the parity test measures both)

The engine is INCREMENTAL and causal by construction: advance(src, now)
processes step m only once bar m is complete (wall >= m+1) and resolves a
fill at bar m+1 only once that bar is complete (wall >= m+2). The parity
test drives the same object minute by minute from the historical caches.

CLI (session agent)
  python plan/p3_rl.py --snapshot FILE --date D --at HH:MM
        ingest a saved run_scan result of the "P3 RL wide universe" scan as
        the snapshot of grid step HH:MM (the step whose bar just completed;
        run the scan at wall HH:MM+1 and pass --at HH:MM)
  python plan/p3_rl.py --date D --now HH:MM [--feed live|cache] [--reset]
        advance the persisted live state to wall clock HH:MM and print the
        decision line (P3 {...}); state: data/paper/rl/state_{D}.json
"""
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_lib as P                                            # noqa: E402

warnings.filterwarnings("ignore", message="Mean of empty slice")

_RULE = json.loads((HERE / "rl2" / "results" /
                    "rules_holdout_s0.json").read_text())["rule"]
_T = {n: float(v) for n, _op, v in _RULE["tests"]}
DV_T = np.float32(_T["dist_vwap_day"])
BR_T = np.float32(_T["xs_breadth"])
LP_T = np.float32(_T["log_price"])
_X = _RULE["exit"][1]
TAKE, TRAIL, TMAX = float(_X["take"]), float(_X["trail"]), int(_X["tmax"])
STEP = 5
LAST_STEP = 955                       # 19:55, the sim's last grid step
FEE_BPS, EXT_BPS = 10.0, 50.0

CFG_PUBLISHED = dict(name="published", tickets=[15000.0] * 6 + [10000.0],
                     max_new=2, max_conc=7, win=(330, 720), flat_bar=None,
                     min_notional=500.0, whole=False)
CFG_LIVE = dict(name="live", tickets=[P.TICKET] * 7, max_new=1, max_conc=1,
                win=(330, 715), flat_bar=719, min_notional=500.0, whole=True)


def cost_frac(minute, fee=FEE_BPS):
    ext = minute < P.M_OPEN or minute >= P.M_CLOSE
    return (fee + EXT_BPS * ext) / 1e4


# ------------------------------------------------------------- sources
class BarSrc:
    """Features from 1-minute bars (identical formulas to
    plan/rl2/features.py compute_day). Arrays may be truncated to `now`
    columns (strict mode): every read is at an index <= now-1."""

    def __init__(self, syms, o, h, l, c, v, vwap_from=0):
        f = lambda a: np.asarray(a, np.float32).astype(np.float64)  # noqa
        self.syms = list(syms)
        self.o, self.c, self.v = f(o), f(c), np.nan_to_num(f(v))
        if vwap_from:            # sensitivity tests only: VWAP window start
            vv = self.v.copy()
            vv[:, :vwap_from] = 0.0
        else:
            vv = self.v
        self.N = self.c.shape[1]
        self.printed = ~np.isnan(self.c)
        idx = np.where(self.printed, np.arange(self.N)[None, :], 0)
        np.maximum.accumulate(idx, axis=1, out=idx)
        self.cf = self.c[np.arange(len(self.syms))[:, None], idx]
        self.cdv = np.cumsum(np.nan_to_num(self.c) * vv, axis=1)
        self.cvol = np.cumsum(vv, axis=1)
        self.cvol5 = np.cumsum(self.v, axis=1)

    def view(self, m):
        mark = self.cf[:, m]
        prn = self.printed[:, m]
        op = self.cf[:, 330] if m >= 330 else self.cf[:, 0]
        with np.errstate(all="ignore"):
            r1 = np.log(np.maximum(mark, 1e-9) / np.maximum(op, 1e-9))
            vday = self.cvol[:, m]
            vw = self.cdv[:, m] / np.maximum(vday, 1.0)
            dv = np.where(vday > 0, np.log(np.maximum(mark, 1e-9) /
                                           np.maximum(vw, 1e-9)), 0.0)
            lp = np.log(np.maximum(mark, 1e-9))
            br = np.nanmean(np.where(prn, r1, np.nan))
        br = 0.0 if not np.isfinite(br) else br
        lo = m - STEP
        vc = 0.2 * (self.cvol5[:, m] - (self.cvol5[:, lo] if lo >= 0 else 0.0))
        c32 = lambda a: np.nan_to_num(a, nan=0.0, posinf=0.0,  # noqa
                                      neginf=0.0).astype(np.float32)
        return dict(mark=mark, printed=prn, dv=c32(dv), lp=c32(lp),
                    br=np.float32(br), volcap=vc, src="bars")

    def mark(self, i, m):
        return float(self.cf[i, m])

    def open_at(self, i, k):
        """Open of bar k; NaN = did not print; None = not known yet."""
        if k >= self.N:
            return None
        return float(self.o[i, k]) if self.printed[i, k] else float("nan")

    def last_close(self, i, k):
        k = min(k, self.N - 1)
        row = self.printed[i, :k + 1]
        if not row.any():
            return None, None
        kk = int(np.flatnonzero(row)[-1])
        return float(self.c[i, kk]), kk


class SnapSrc:
    """LIVE source: per-step scan snapshots of the whole universe, with
    1-minute bars (data/rh_bars, agent-fetched) overriding the snapshot
    for every name that has them."""

    def __init__(self, date, now, syms):
        self.date, self.now, self.syms = date, now, list(syms)
        self.feed = P.LiveFeed(date, now)
        self.snaps = load_snaps(date)
        self._bs = {}

    def _bars(self, i):
        if i not in self._bs:
            b = self.feed.bars(self.syms[i])
            self._bs[i] = None if b is None else BarSrc(
                [self.syms[i]], *[x[None, :self.now] for x in b])
        return self._bs[i]

    def ready(self, m, now):
        """Wait for step m's scan snapshot while it is fresh (<= 3 min old);
        an older missing snapshot is a GAP (entries skipped at that step)."""
        return m in self.snaps or m < now - 3 or not (330 <= m <= 720)

    def has_bars(self, i, m):
        b = self._bars(i)
        return b is not None and b.printed[0, :m + 1].any()

    def view(self, m):
        s = self.snaps.get(m)
        if s is None:
            return None
        op_s = self.snaps.get(330) or {}
        S = len(self.syms)
        mark = np.full(S, np.nan)
        prn = np.zeros(S, bool)
        dv = np.zeros(S)
        r1 = np.full(S, np.nan)
        vc = np.full(S, np.nan)
        src = []
        for i, sym in enumerate(self.syms):
            b = self._bars(i)
            if b is not None and b.printed[0, :m + 1].any():
                v = b.view(m)
                mark[i], prn[i], dv[i] = v["mark"][0], v["printed"][0], v["dv"][0]
                op = b.cf[0, 330] if b.printed[0, :331].any() else np.nan
                if not np.isfinite(op):
                    op = P.fnum((op_s.get(sym) or {}).get("px"))
                vc[i] = v["volcap"][0]
                src.append("b")
            else:
                r = s.get(sym)
                if not r:
                    continue
                mark[i] = P.fnum(r.get("px"))
                tt = r.get("tt")
                prn[i] = tt is not None and tt >= m and np.isfinite(mark[i])
                vw = P.fnum(r.get("vwap"))
                dv[i] = (math.log(mark[i] / vw) if np.isfinite(vw) and vw > 0
                         and np.isfinite(mark[i]) and mark[i] > 0 else 0.0)
                op = P.fnum((op_s.get(sym) or {}).get("px"))
                src.append("s")
            if np.isfinite(mark[i]) and np.isfinite(op) and op > 0:
                r1[i] = math.log(max(mark[i], 1e-9) / op)
        with np.errstate(all="ignore"):
            br = np.nanmean(np.where(prn, r1, np.nan))
            lp = np.log(np.maximum(mark, 1e-9))
        br = 0.0 if not np.isfinite(br) else br
        c32 = lambda a: np.nan_to_num(a, nan=0.0, posinf=0.0,  # noqa
                                      neginf=0.0).astype(np.float32)
        return dict(mark=mark, printed=prn, dv=c32(dv), lp=c32(lp),
                    br=np.float32(br), volcap=vc,
                    src=f"snap({src.count('s')})+bars({src.count('b')})")

    def mark(self, i, m):
        b = self._bars(i)
        if b is not None and b.printed[0, :m + 1].any():
            return b.mark(0, m)
        s = self.snaps.get(m) or {}
        return P.fnum((s.get(self.syms[i]) or {}).get("px"))

    def open_at(self, i, k):
        b = self._bars(i)
        if b is None or k >= b.N:
            return None
        # bars exist through now-1; an unprinted minute inside the fetched
        # range is a genuine no-print
        return b.open_at(0, k)

    def last_close(self, i, k):
        b = self._bars(i)
        if b is None:
            return None, None
        return b.last_close(0, k)


# ------------------------------------------------------------- engine
class Engine:
    def __init__(self, cfg, syms, state=None, fee=FEE_BPS):
        self.cfg, self.syms, self.fee = cfg, list(syms), fee
        self.st = state or dict(next_step=330, used=0, held={}, pend_in=[],
                                pend_out=[], trades=[], events=[],
                                done=False, asked={})
        self.new = []

    # -- helpers -----------------------------------------------------
    def _ev(self, now, kind, **kw):
        e = dict(now=P.hhmm(now) if now < P.NMIN else "EOD", type=kind, **kw)
        self.st["events"].append(e)
        self.new.append(e)

    def _close(self, now, i, p, px, m_out, reason, forced=False):
        c_in = cost_frac(p["m_in"], self.fee)
        c_out = cost_frac(m_out, self.fee)
        t = dict(sym=p["sym"], step_in=p["t_in"], m_in=p["m_in"],
                 px_in=p["px_in"], sh=p["sh"], m_out=int(m_out),
                 px_out=float(px), reason=reason, forced=forced,
                 gross=p["sh"] * (px - p["px_in"]),
                 pnl=p["sh"] * px * (1 - c_out) - p["sh"] * p["px_in"] * (1 + c_in),
                 ext_out=bool(m_out < P.M_OPEN or m_out >= P.M_CLOSE))
        self.st["trades"].append(t)
        self._ev(now, "EXIT-FILL", sym=p["sym"], px=float(px),
                 fill_min=P.hhmm(m_out), reason=reason,
                 pnl=round(t["pnl"], 2))

    # -- resolution of pending fills ----------------------------------
    def _resolve(self, src, now):
        held = self.st["held"]
        keep = []
        for q in self.st["pend_out"]:
            i, m = q["i"], q["m"]
            px = src.open_at(i, m + 1)
            if px is None:
                keep.append(q)
                continue
            p = held.get(str(i))
            if p is None:
                continue
            if np.isfinite(px) and px > 0:
                self._close(now, i, p, px, m + 1, q["reason"])
                del held[str(i)]
            else:
                p.pop("exiting", None)
                self._ev(now, "EXIT-CARRY", sym=p["sym"],
                         note=f"bar {P.hhmm(m + 1)} did not print")
        self.st["pend_out"] = keep
        keep = []
        tk = self.cfg["tickets"]
        for q in self.st["pend_in"]:
            i, m = q["i"], q["m"]
            px = src.open_at(i, m + 1)
            if px is None:
                keep.append(q)
                continue
            sym = self.syms[i]
            if not (np.isfinite(px) and px > 0):
                self._ev(now, "NO-FILL", sym=sym, note="bar m+1 unprinted")
                continue
            if self.st["used"] >= len(tk):
                continue
            sh = tk[self.st["used"]] / px
            cap = q.get("volcap")
            if cap is not None and np.isfinite(cap):
                sh = min(sh, cap)
            if self.cfg["whole"]:
                sh = float(math.floor(sh))
            if sh * px < self.cfg["min_notional"]:
                self._ev(now, "THIN", sym=sym, note=f"notional {sh * px:.0f}")
                continue
            held[str(i)] = dict(sym=sym, t_in=m, m_in=m + 1, px_in=float(px),
                                sh=sh, peak=float(px))
            self.st["used"] += 1
            self._ev(now, "ENTER-FILL", sym=sym, px=float(px),
                     fill_min=P.hhmm(m + 1), shares=sh)
        self.st["pend_in"] = keep

    # -- one grid step --------------------------------------------------
    def _step(self, src, now, m):
        held, cfg = self.st["held"], self.cfg
        fb = cfg["flat_bar"]
        if fb is None or m + 1 <= fb:
            for key, p in held.items():
                if m <= p["t_in"] or p.get("exiting") is not None:
                    continue
                i = int(key)
                mk = src.mark(i, m)
                want = None
                if mk is not None and np.isfinite(mk):
                    r = mk / p["px_in"] - 1.0
                    p["peak"] = max(p["peak"], mk)
                    if r >= TAKE:
                        want = "take"
                    if mk <= p["peak"] * (1.0 - TRAIL):
                        want = want or "trail"
                if m >= p["m_in"] + TMAX:
                    want = want or "tmax"
                if want:
                    p["exiting"] = m
                    self.st["pend_out"].append(dict(i=i, m=m, reason=want))
                    self._ev(now, "EXIT", sym=p["sym"], step=P.hhmm(m),
                             reason=want, mark=mk, px_in=p["px_in"])
        lo, hi = cfg["win"]
        if not (lo <= m <= hi) or self.st["used"] >= len(cfg["tickets"]):
            return
        live_held = [k for k, p in held.items() if p.get("exiting") is None]
        free = min(len(cfg["tickets"]) - self.st["used"], cfg["max_new"],
                   cfg["max_conc"] - len(live_held))
        if free <= 0:
            return
        v = src.view(m)
        if v is None:
            self._ev(now, "GAP", step=P.hhmm(m), note="no snapshot for step")
            return
        ok = (v["printed"] & (v["dv"] < DV_T) & (v["br"] < BR_T)
              & (v["lp"] < LP_T))
        # a name whose exit was decided at THIS step is re-enterable: in the
        # sim its exit and the new entry both fill at bar m+1's open (and
        # both fail together if m+1 does not print)
        cand = [int(i) for i in np.flatnonzero(ok)
                if str(int(i)) not in held
                or held[str(int(i))].get("exiting") == m]
        self.st.setdefault("feat", {})[P.hhmm(m)] = dict(
            br=round(float(v["br"]), 5), n_cand=len(cand), src=v["src"])
        for i in cand[:free]:
            self.st["pend_in"].append(dict(i=i, m=m, volcap=float(v["volcap"][i])
                                           if np.isfinite(v["volcap"][i]) else None))
            self._ev(now, "ENTER", sym=self.syms[i], step=P.hhmm(m),
                     features=dict(breadth=round(float(v["br"]), 5),
                                   dist_vwap=round(float(v["dv"][i]), 5),
                                   log_price=round(float(v["lp"][i]), 4),
                                   mark=float(v["mark"][i])))

    # -- public --------------------------------------------------------
    def advance(self, src, now, eod=False):
        """Process everything decidable at wall minute `now` (bars <= now-1).
        `eod` (published config) = the day's tape is complete: flatten."""
        self.new = []
        st, cfg = self.st, self.cfg
        if st["done"]:
            return self.new
        avail = now - 1
        last = LAST_STEP if cfg["flat_bar"] is None else cfg["flat_bar"] - 1
        while True:
            self._resolve(src, now)
            m = st["next_step"]
            if m > last or m > avail:
                break
            if any(q["m"] + 1 > avail for q in st["pend_in"] + st["pend_out"]):
                break
            if not getattr(src, "ready", lambda m, now: True)(m, now):
                self.waiting = m              # live: the step's scan is not in yet
                break
            self._step(src, now, m)
            st["next_step"] = m + STEP
        fb = cfg["flat_bar"]
        flat_now = (eod if fb is None else avail >= fb)
        if flat_now and st["next_step"] > last and not st["pend_in"] \
                and not st["pend_out"]:
            for key, p in list(st["held"].items()):
                px, kk = src.last_close(int(key), P.NMIN - 1 if fb is None
                                        else fb)
                if px is None:
                    px, kk = p["px_in"], p["m_in"]
                self._close(now, int(key), p, px, kk, "flatten", forced=True)
                del st["held"][key]
            st["done"] = True
            self._ev(now, "DONE")
        return self.new


# ------------------------------------------------------------- snapshots
def snap_path(date):
    return P.book_dir("rl") / f"snap_{date}.jsonl"


def _tt_min(x, date):
    """tradeAllDay.time -> grid minute (accepts epoch ms/s or ISO)."""
    if x in (None, ""):
        return None
    try:
        f = float(x)
        if f > 1e12:
            f /= 1000.0
        from datetime import datetime
        dt = datetime.fromtimestamp(f, P.ET)
    except (TypeError, ValueError):
        from datetime import datetime
        s = str(x).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s).astimezone(P.ET)
        except ValueError:
            return None
    if dt.date().isoformat() != date:
        return -1
    return dt.hour * 60 + dt.minute - P.BASE


COLS = dict(px=("P3 last", "Last", "Price"), tt=("P3 last time",),
            vwap=("P3 vwap all",), vwap_reg=("P3 vwap reg",),
            open_reg=("P3 open reg", "Open"))


def ingest_snapshot(path, date, at):
    rows = P.scan_rows(P.load_tool_json(path))
    m = P.parse_hhmm(at)
    out = {}
    for r in rows:
        c = r["cols"]
        g = lambda keys: next((c[k] for k in keys if k in c), None)  # noqa
        out[r["sym"]] = dict(px=P.fnum(g(COLS["px"])),
                             tt=_tt_min(g(COLS["tt"]), date),
                             vwap=P.fnum(g(COLS["vwap"])),
                             vwap_reg=P.fnum(g(COLS["vwap_reg"])),
                             open_reg=P.fnum(g(COLS["open_reg"])))
    with open(snap_path(date), "a") as f:
        f.write(json.dumps({"m": m, "at": at, "n": len(out), "rows": out},
                           default=float) + "\n")
    print(f"RL snapshot step {at}: {len(out)} rows -> {snap_path(date)}")
    return out


def load_snaps(date):
    out = {}
    p = snap_path(date)
    if p.exists():
        for ln in p.read_text().splitlines():
            if ln.strip():
                d = json.loads(ln)
                out.setdefault(d["m"], d["rows"])       # first write wins
    return out


# ------------------------------------------------------------- watcher hook
def watch_exit(date, st, bars, now):
    """Exit check for paper_watch.py EXIT_MODE rl. `bars` = (o,h,l,c,v) of
    st["sym"] from p3_lib.LiveFeed (completed bars <= now-1). Mutates st
    (model_entry, peak, rl_next_step, rl_exit). Returns None (hold) or
    {"decided_min", "min", "px" (None until bar m+1 completes), "reason"}."""
    if bars is None:
        return None
    o, h, l, c, v = bars
    b = BarSrc([st["sym"]], *[np.asarray(x)[None, :now] for x in bars])
    dm = int(st["decision_min"])
    if st.get("model_entry") is None:
        k = dm + 1
        if k <= now - 1:
            st["model_entry"] = (float(b.o[0, k]) if b.printed[0, k]
                                 else float(st["entry"]))
    px_in = float(st.get("model_entry") or st["entry"])
    pend = st.get("rl_exit")
    if pend:
        k = pend["decided_min"] + 1
        if k > now - 1:
            return dict(pend, px=None)
        if b.printed[0, k]:
            return dict(pend, min=k, px=float(b.o[0, k]))
        st["rl_exit"] = None                  # carry, as the sim does
    m_in = dm + 1
    peak = float(st.get("rl_peak") or px_in)
    m = int(st.get("rl_next_step") or dm + STEP)
    fb = CFG_LIVE["flat_bar"]
    while m <= now - 1 and m + 1 <= fb:
        mk = b.mark(0, m)
        want = None
        if np.isfinite(mk):
            peak = max(peak, mk)
            if mk / px_in - 1.0 >= TAKE:
                want = "take"
            if mk <= peak * (1.0 - TRAIL):
                want = want or "trail"
        if m >= m_in + TMAX:
            want = want or "tmax"
        m += STEP
        if want:
            st["rl_exit"] = dict(decided_min=m - STEP, min=m - STEP + 1,
                                 px=None, reason=want)
            break
    st["rl_peak"], st["rl_next_step"] = peak, m
    if st.get("rl_exit"):
        k = st["rl_exit"]["min"]
        if k <= now - 1 and b.printed[0, k]:
            return dict(st["rl_exit"], px=float(b.o[0, k]))
        return dict(st["rl_exit"])
    if now - 1 >= fb:
        px, kk = b.last_close(0, fb)
        return dict(decided_min=fb, min=kk, px=px, reason="flatten")
    return None


# ------------------------------------------------------------- live CLI
def state_path(date):
    return P.book_dir("rl") / f"state_{date}.json"


def universe_syms(hist_date=None):
    """The live universe (data/paper/universe_wide.json). `hist_date`
    (tests/replays only) = that day's published rl2 universe instead."""
    if hist_date:
        rows = json.loads((HERE / "rl2" / "out" / "universe" /
                           f"{hist_date}.json").read_text())
        return sorted(r["symbol"] for r in rows)
    u = P.read_json(P.DATA / "paper" / "universe_wide.json", {}) or {}
    return sorted(u.get("symbols") or [])


def live(date, now_s, feed="live", reset=False):
    now = P.parse_hhmm(now_s)
    syms = universe_syms(date if feed == "cache" else None)
    sp = state_path(date)
    st = None if reset else P.read_json(sp)
    if feed == "cache":
        bars = [P.CacheFeed(date, now).bars(s) for s in syms]
        nan = np.full(P.NMIN, np.nan)
        arr = [np.vstack([(b[k] if b is not None else
                           (np.zeros(P.NMIN) if k == 4 else nan))[:now]
                          for b in bars]) for k in range(5)]
        src = BarSrc(syms, *arr)
    else:
        src = SnapSrc(date, now, syms)
    eng = Engine(CFG_LIVE, syms, state=st)
    # two-phase confirmation: if the next step's breadth passes on the
    # snapshot, ask for 04:00->now bars of the first <=10 prescreened names
    need = []
    m_next = eng.st["next_step"]
    if feed != "cache" and m_next <= now - 1 and not eng.st["held"] \
            and str(m_next) not in eng.st.get("asked", {}):
        v = src.view(m_next)
        if v is not None and v["br"] < BR_T:
            snap = src.snaps.get(m_next) or {}
            for i, s in enumerate(syms):
                r = snap.get(s) or {}
                px, vw = P.fnum(r.get("px")), P.fnum(r.get("vwap"))
                if not (np.isfinite(px) and px > 0 and math.log(px) < LP_T):
                    continue
                if np.isfinite(vw) and vw > 0 and px > vw * 1.003:
                    continue
                if not src.has_bars(i, m_next):
                    need.append(s)
                if len(need) >= 10:
                    break
            if need:
                eng.st.setdefault("asked", {})[str(m_next)] = need
                P.write_atomic(sp, eng.st)
                P.emit(dict(book="rl", now=now_s, action="NEED_DATA",
                            reason=f"breadth {float(v['br']):+.4f} < "
                                   f"{float(BR_T)} at {P.hhmm(m_next)}: "
                                   f"confirm VWAP on bars",
                            need_bars=need))
                return
    eng.waiting = None
    new = eng.advance(src, now)
    P.write_atomic(sp, eng.st)
    held = list(eng.st["held"].values())
    held_syms = [p["sym"] for p in held]
    kinds = [e["type"] for e in new]
    if "ENTER" in kinds:
        e = [x for x in new if x["type"] == "ENTER"][-1]
        stale = P.parse_hhmm(e["step"]) < now - 2
        act = dict(action="ENTER-STALE" if stale else "ENTER", sym=e["sym"],
                   decision_min=e["step"],
                   reason=("STALE: decided at a step more than 2 minutes "
                           "ago (catch-up replay) -- do NOT trade; the model "
                           "holds it, the ledger records a MISSED entry"
                           if stale else
                           "dist_vwap<-0.00006 & breadth<-0.02379 & "
                           "log_price<2.7537"), features=e["features"],
                   model_entry=None)
    elif "EXIT" in kinds:
        e = [x for x in new if x["type"] == "EXIT"][-1]
        act = dict(action="EXIT", sym=e["sym"], decision_min=e["step"],
                   reason=e["reason"])
    elif "EXIT-FILL" in kinds and not eng.st["held"]:
        e = [x for x in new if x["type"] == "EXIT-FILL"][-1]
        act = dict(action="EXITED", sym=e["sym"], reason=e["reason"],
                   model_exit=e["px"], fill_min=e["fill_min"])
    elif eng.st["done"]:
        act = dict(action="DONE", reason="session flattened")
    elif held:
        p = held[0]
        act = dict(action="HOLD", sym=p["sym"], model_entry=p["px_in"],
                   decision_min=P.hhmm(p["t_in"]), reason=f"peak {p['peak']}")
    else:
        f = eng.st.get("feat", {})
        lastf = f[max(f)] if f else {}
        act = dict(action="NOTHING", reason=f"no qualifier; last step "
                   f"features {lastf}")
    if eng.waiting is not None:
        act["need_scan"] = P.hhmm(eng.waiting)
        if act["action"] in ("NOTHING", "HOLD"):
            act["action"] = "NEED_DATA"
            act["reason"] = (f"no scan snapshot for step {P.hhmm(eng.waiting)}"
                             f": run_scan the P3 RL scan, ingest it with "
                             f"--snapshot --at {P.hhmm(eng.waiting)}, re-run"
                             f" ({act['reason']})")
    pend = [P.hhmm(q["m"] + 1) for q in eng.st["pend_in"] + eng.st["pend_out"]]
    need = sorted(set(held_syms + [e["sym"] for e in new
                                   if e["type"] == "ENTER"]))
    P.emit(dict(book="rl", now=now_s, **act, held=held_syms,
                tickets_used=eng.st["used"], pending_fill_bars=pend,
                need_bars=need, new_events=new))


def main():
    a = sys.argv[1:]
    g = lambda k, d=None: a[a.index(k) + 1] if k in a else d  # noqa
    date = g("--date", P.now_et().date().isoformat())
    if "--snapshot" in a:
        ingest_snapshot(g("--snapshot"), date, g("--at"))
        return
    live(date, g("--now", P.now_et().strftime("%H:%M")),
         feed=g("--feed", "live"), reset="--reset" in a)


if __name__ == "__main__":
    main()
