"""PAPER-3BOOK watcher end-to-end test: historical legs replayed through
plan/paper_watch.py's EXIT_MODE r4 / r15 / rl, minute by minute.

For each case the historical minute bars are written into a throw-away
data root in Robinhood's CSV format (data/rh_bars), a quote file is
written every minute (bid = last completed close, ask = bid + 1 cent), the
position is opened through the real `--open` path, and Watcher.tick() is
called once per minute with the clock override. The booked record must
carry the backtest's model exit (minute + price) and an official fill at
the quote bid. Nothing here touches the live data/ tree.

    python plan/p3_watch_selftest.py
"""
import json
import shutil
import sys
from datetime import date as ddate
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_lib as P                                          # noqa: E402
import paper_watch as W                                     # noqa: E402

TMP = P.DATA / "_p3_watch_selftest"
FAILS = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
    if not ok:
        FAILS.append(name)


def to_rh_csv(sym, date, root, order=("m1", "m1c", "m1w")):
    src = None
    for d in order:
        f = P.MASSIVE / d / f"{sym}_{date}.csv"
        if f.exists():
            src = f
            break
    rows = src.read_text().splitlines()[1:]
    out = ["begins_at,open,high,low,close,volume"]
    for ln in rows:
        ts, rest = ln.split(",", 1)
        out.append(ts[:10] + "T" + ts[11:19] + "Z," + rest)
    p = root / "rh_bars" / f"{sym}_{date}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(out) + "\n")
    return P.read_bars_csv(p, date)


def run_case(book, sym, date, decision, entry_px, shares, want_min,
             want_px, want_reason, last_clock, order=("m1", "m1c", "m1w")):
    root = TMP / f"{book}_{sym}_{date}"
    shutil.rmtree(root, ignore_errors=True)
    bars = to_rh_csv(sym, date, root, order)
    paths = W.Paths(str(root), book=book)
    d = ddate.fromisoformat(date)
    dk = P.parse_hhmm(decision)
    open_clock = P.hhmm(dk + 1)
    args = W.build_parser().parse_args(
        ["--open", sym, "--entry", str(entry_px), "--shares", str(shares),
         "--decision-min", decision, "--entry-bid", str(entry_px - 0.01),
         "--entry-ask", str(entry_px), "--date", date, "--clock", open_clock,
         "--data-root", str(root), "--book", book])
    W.cmd_open(args, paths, W.Clock(d, open_clock))
    clock = W.Clock(d, open_clock)
    w = W.Watcher(paths, clock, book)
    rec = None
    for k in range(dk + 2, P.parse_hhmm(last_clock) + 1):
        hh = P.hhmm(k)
        c = bars[3][:k]
        import numpy as np
        ok = np.flatnonzero(~np.isnan(c))
        if ok.size:
            bid = float(c[ok[-1]])
            q = {sym: dict(bid=bid, ask=round(bid + 0.01, 4),
                           ts=P.utc_iso(date, k))}
            P.write_atomic(paths.quotes(d), q)
        clock.clock_override = hh
        w.tick()
        fl = P.read_json(paths.flatten(d)) or {}
        if fl.get("records"):
            rec = fl["records"][0]
            break
    check(f"{book} {sym} {date}: exit booked", rec is not None)
    if rec is None:
        return
    p3 = rec.get("p3") or {}
    check(f"{book} {sym}: model exit minute {want_min}",
          p3.get("model_exit_min") == want_min, str(p3.get("model_exit_min")))
    check(f"{book} {sym}: model exit px {want_px}",
          p3.get("model_exit") is not None
          and abs(p3["model_exit"] - want_px) < 1e-6, str(p3.get("model_exit")))
    check(f"{book} {sym}: reason {want_reason}",
          str(p3.get("reason", "")).startswith(want_reason), p3.get("reason"))
    check(f"{book} {sym}: official fill = quote bid",
          p3.get("official_src") == "quote-bid", p3.get("official_src"))
    check(f"{book} {sym}: state file removed",
          not paths.pos_file(sym).exists())
    print(f"    record: entry {rec['entry']} exit {rec['vwap']} pnl "
          f"{rec['pnl']} model_entry {p3.get('model_entry')} "
          f"model_pnl {p3.get('model_pnl')} decided {p3.get('decided_min')}")


def main():
    # R4 (published dump, LIVE next-open bearish): 2024-10-22 MLI decided
    # 09:35, model entry 09:36 open 40.25, bearish bar 10:01, next open
    # 10:02 = 41.15 (cp_sim + LEGACY-14 ground truth, plan/p3_parity_r4)
    run_case("r4", "MLI", "2024-10-22", "09:35", 40.30, 248,
             "10:02", 41.15, "bearish", "11:00")
    # R4 trail leg: RITR decided 10:05 (t=365), trail 0.10 exit at 11:27
    run_case("r4", "RITR", "2024-10-22", "10:05", 8.21, 1218,
             "11:27", 6.82, "trail", "12:30")
    # R15: the first backtest tickets (plan/p3_parity_r15 matched list):
    # decided 09:35, model entry 09:36 open, h60 exit = open of the first
    # printed bar >= 10:36
    r15 = json.loads((P.DATA / "paper" / "parity" / "r15.json").read_text())
    for x in r15["matched_list"][:2]:
        run_case("r15", x["sym"], x["date"], "09:35", x["entry_live"] + 0.01,
                 int(10000 // x["entry_live"]), P.hhmm(x["exit_min_live"]),
                 x["exit_live"], "h60", "11:00", order=("m1w", "m1", "m1c"))
    # RL: live-config trades from plan/p3_parity_rl (one per exit reason)
    rl = json.loads((P.DATA / "paper" / "parity" / "rl.json").read_text())
    seen = set()
    for x in rl["live_trades"]:
        if x["reason"] in seen:
            continue
        seen.add(x["reason"])
        run_case("rl", x["sym"], x["date"], P.hhmm(x["m_in"] - 1),
                 x["px_in"] + 0.01, int(x["sh"]), P.hhmm(x["m_out"]),
                 x["px_out"], x["reason"], "16:05", order=("m1w", "m1", "m1c"))
    print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + str(FAILS)}")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
