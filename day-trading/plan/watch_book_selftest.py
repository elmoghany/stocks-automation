"""Self-test for plan/paper_watch.py --book (2026-09-01 rewrite).

Runs the watcher as a subprocess against a SCRATCH data root (copies of
data/rh_bars/*_2026-08-25.csv, never the live cache) and asserts the
audited defects are closed:

  1. six positions, ladder replay 14:49 -> 15:02 with --once ticks:
     rungs booked, VWAP computed, exit_parity per name, equity curve
     written, every state file unlinked (only the watcher unlinks);
     one name has its 14:50 rung UNFILLED and rolled; one name's 14:50
     bid comes from the agent quote file.
  2. dead feed (CSV truncated to <= 14:40) at 14:58: FLATTEN-NO-DATA
     still books, and 14:59 flattens + unlinks.
  3. stale state (dated 2026-08-24): exit code 2, file byte-identical,
     on both the --book and the legacy argv path.
  4. EXIT_MODE=ptrail on a synthetic +15%-then-sellers series: the 10%
     pressure trail books EXIT-TRAIL; EXIT_MODE=hold on the same series:
     no exit until the ladder. Plus: a -9% drift with buyers on the tape
     exits under c37 (hard stop) and NOT under ptrail (no hard stop).

Usage: python plan/watch_book_selftest.py [--keep]   (prints PASS/FAIL)

Only 2026-08-25 CRML has real afternoon bars in the cache (the other
CSVs end ~09:58 ET), so every copied symbol is EXTENDED with synthetic
14:30-14:59 bars (400 sh/min, so the 20%-of-10-bar size cap = 800 sh and
the ladder needs several rungs). Real bars are never overwritten.
"""
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WATCH = HERE / "paper_watch.py"
DATE = "2026-08-25"
UTC_OFF = 4                        # 2026-08-25 is EDT: ET = UTC-4
SCRATCH = Path(os.environ.get("WATCH_SELFTEST_DIR")
               or ROOT / "data" / "_selftest_tmp")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""),
          flush=True)
    return ok


def run(args, root, env_mode=None):
    env = dict(os.environ)
    env.pop("EXIT_MODE", None)
    if env_mode:
        env["EXIT_MODE"] = env_mode
    cmd = [sys.executable, str(WATCH), "--data-root", str(root),
           "--date", DATE] + args
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def fresh_root(name):
    root = SCRATCH / name
    if root.exists():
        shutil.rmtree(root)
    for d in ("rh_bars", "paper", "paper_days"):
        (root / d).mkdir(parents=True)
    return root


def utc_iso(hh_et, mm):
    return f"{DATE}T{hh_et + UTC_OFF:02d}:{mm:02d}:00Z"


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        f.write("begins_at,open,high,low,close,volume\n")
        for r in sorted(rows, key=lambda r: r["begins_at"]):
            f.write(",".join(str(r[k]) for k in
                             ("begins_at", "open", "high", "low", "close",
                              "volume")) + "\n")


def extend_afternoon(rows, dip_1450=False, vol=400):
    """Add synthetic 14:30-14:59 ET bars for minutes not in the file."""
    have = {r["begins_at"] for r in rows}
    base = float(rows[-1]["close"])
    prev = base
    out = list(rows)
    for j, m in enumerate(range(30, 60)):
        ts = utc_iso(14, m)
        if ts in have:
            prev = float([r for r in rows if r["begins_at"] == ts][0]["close"])
            continue
        c = round(base * (1 + 0.001 * math.sin(j)), 4)
        o = prev
        h = round(max(o, c) * 1.0005, 4)
        l = round(min(o, c) * 0.9995, 4)
        if dip_1450 and m == 50:
            l = round(c * 0.985, 4)         # prints below bid-0.5% limit
        out.append(dict(begins_at=ts, open=o, high=h, low=l, close=c,
                        volume=vol))
        prev = c
    return out


def pick_symbols():
    src = ROOT / "data" / "rh_bars"
    syms = []
    if (src / f"CRML_{DATE}.csv").exists():
        syms.append("CRML")
    for f in sorted(src.glob(f"*_{DATE}.csv")):
        s = f.name.split("_")[0]
        if s in syms or s == "CRML":
            continue
        if len(read_csv(f)) >= 30:
            syms.append(s)
        if len(syms) == 6:
            break
    return syms


def open_position(root, sym, entry, shares, ebu, ticket):
    rc, out = run(["--open", sym, "--entry", str(entry), "--shares",
                   str(shares), "--ticket", str(ticket),
                   "--entry-bar-utc", ebu, "--clock", "14:31"], root)
    assert rc == 0, out
    return out


# --------------------------------------------------------------- scenario 1
def scenario_ladder():
    print("\n[1] six-name ladder replay 14:49 -> 15:02")
    root = fresh_root("ladder")
    syms = pick_symbols()
    if len(syms) < 6:
        check("six symbols available", False, f"only {syms}")
        return
    src = ROOT / "data" / "rh_bars"
    entries = {}
    for i, s in enumerate(syms):
        rows = extend_afternoon(read_csv(src / f"{s}_{DATE}.csv"),
                                dip_1450=(i == 1))
        write_csv(root / "rh_bars" / f"{s}_{DATE}.csv", rows)
        bar1430 = [r for r in rows if r["begins_at"] == utc_iso(14, 30)][0]
        entry = float(bar1430["close"])
        shares = int(15000 // entry)
        entries[s] = (entry, shares)
        open_position(root, s, entry, shares, utc_iso(14, 30), i + 1)
    # agent quote for the first name, 30 s before the 14:50 rung
    qsym = syms[0]
    (root / "paper" / f"quotes_{DATE}.json").write_text(json.dumps({
        qsym: {"bid": round(entries[qsym][0] * 1.002, 4),
               "ask": round(entries[qsym][0] * 1.004, 4),
               "ts": f"{DATE}T14:49:30-04:00"}}))
    check("six state files created", len(list((root / "paper").glob(
        "position_*.json"))) == 6)

    logs = {}
    for clk in ("14:49", "14:50", "14:55", "14:58", "14:59", "15:02"):
        rc, out = run(["--book", "--clock", clk, "--once"], root)
        logs[clk] = out
        if rc != 0:
            print(out)
        check(f"tick {clk} rc=0", rc == 0)
        if clk == "14:49":
            sts = [json.loads(f.read_text()) for f in
                   (root / "paper").glob("position_*.json")]
            check("14:49: no rungs yet, all OPEN",
                  all(not s["rungs"] and s["status"] == "OPEN" for s in sts))
        if clk == "14:50":
            sts = {json.loads(f.read_text())["sym"]: json.loads(f.read_text())
                   for f in (root / "paper").glob("position_*.json")}
            check("14:50: rung 1 PENDING on every name",
                  all(s["rungs"] and s["rungs"][0]["status"] == "PENDING"
                      and s["status"] == "FLATTENING" for s in sts.values()))
            # cap = floor(0.20 x sum(vol of the 10 completed bars before
            # 14:50)) -- 800 on purely synthetic names, larger on CRML
            # whose 14:40-14:49 bars are real
            caps = {}
            for s in sts:
                rows = read_csv(root / "rh_bars" / f"{s}_{DATE}.csv")
                win = [r for r in rows if r["begins_at"] < utc_iso(14, 50)][-10:]
                caps[s] = min(entries[s][1],
                              int(0.20 * sum(float(r["volume"]) for r in win)))
            check("14:50: rung 1 size = min(remaining, 20% x trailing-10 vol)",
                  all(s["rungs"][0]["shares"] == caps[k]
                      for k, s in sts.items()),
                  str({k: (v["rungs"][0]["shares"], caps[k]) for k, v in sts.items()}))
            check("14:50: first name's bid came from the quote file",
                  sts[qsym]["rungs"][0]["bid_src"] == "quote",
                  sts[qsym]["rungs"][0]["bid_src"])
            check("14:50: other names used BID-PROXY (bar close)",
                  all(v["rungs"][0]["bid_src"].startswith("BID-PROXY")
                      for k, v in sts.items() if k != qsym))
        if clk == "14:55":
            check("14:55: dip name's 14:50 rung UNFILLED and rolled",
                  "UNFILLED (limit above market" in out
                  and f"LADDER-1 {syms[1]}" in out)

    left = list((root / "paper").glob("position_*.json"))
    check("15:02: all six state files unlinked", not left,
          str([f.name for f in left]))
    fl = json.loads((root / "paper_days" / f"{DATE}.flatten.json").read_text())
    recs = {r["sym"]: r for r in fl["records"]}
    check("flatten.json has six records", len(recs) == 6, str(sorted(recs)))
    ok_vwap = ok_par = ok_sh = ok_rungs = True
    for s, r in recs.items():
        fills = r["fills"]
        n = sum(f["shares"] for f in fills)
        vw = sum(f["shares"] * f["px"] for f in fills) / n if n else 0
        ok_vwap &= abs(vw - r["vwap"]) < 1e-3 and r["vwap"] > 0
        ok_sh &= n == entries[s][1] == r["shares_initial"]
        ok_rungs &= any(x["status"] == "FILLED" for x in r["rungs"])
        ep = r.get("exit_parity") or {}
        ok_par &= (ep.get("close_1459") is not None
                   and ep.get("backtest_exit") is not None
                   and ep.get("delta_bps") is not None and not ep.get("proxy"))
    check("VWAP = sum(px*sh)/sum(sh) of the filled rungs", ok_vwap)
    check("shares exited == shares opened for every name", ok_sh)
    check("every record has >= 1 FILLED rung", ok_rungs)
    check("exit_parity (14:59 close x 0.999) present for every name",
          ok_par, str({s: r.get("exit_parity") for s, r in recs.items()
                       if not (r.get("exit_parity") or {}).get("close_1459")}))
    check("dip name has an UNFILLED rung and still exited in full",
          any(x["status"] == "UNFILLED" for x in recs[syms[1]]["rungs"]),
          str([(x["k"], x["status"], x["shares"]) for x in recs[syms[1]]["rungs"]]))
    eq = json.loads((root / "paper_days" / f"{DATE}.equity.json").read_text())
    check("equity.json written with one point per tick", len(eq["points"]) == 6,
          str(len(eq["points"])))
    check("equity: deployed_notional ~ 6 x $15k",
          85000 < eq["points"][0]["deployed_notional"] < 90001,
          str(eq["points"][0]["deployed_notional"]))
    alive = json.loads((root / "paper_days" / f"WATCH_ALIVE_{DATE}.json").read_text())
    check("WATCH_ALIVE heartbeat written, book empty at the end",
          alive["open"] == [] and "book_pnl" in alive)
    check("EXIT-FLATTEN printed for every name",
          all(f"EXIT-FLATTEN {s} " in "".join(logs.values()) for s in syms))
    print("  sample:", [ln for ln in logs["14:59"].splitlines()
                       if "EXIT-FLATTEN" in ln][:1])
    return root


# --------------------------------------------------------------- scenario 2
def scenario_no_data():
    print("\n[2] dead feed at 14:58 -> FLATTEN-NO-DATA still books")
    root = fresh_root("nodata")
    sym = "CRML" if (ROOT / "data" / "rh_bars" / f"CRML_{DATE}.csv").exists() \
        else pick_symbols()[0]
    rows = read_csv(ROOT / "data" / "rh_bars" / f"{sym}_{DATE}.csv")
    rows = [r for r in rows if r["begins_at"] <= utc_iso(14, 40)]
    write_csv(root / "rh_bars" / f"{sym}_{DATE}.csv", rows)
    ebu = rows[-1]["begins_at"]
    entry = float(rows[-1]["close"])
    # 30,000 sh so the 20%-of-trailing-10 cap (from the stale 14:31-14:40
    # bars) forces three rungs instead of one
    open_position(root, sym, entry, 30000, ebu, 1)
    rc, out = run(["--book", "--clock", "14:58", "--once"], root)
    check("14:58 rc=0", rc == 0)
    check("FLATTEN-NO-DATA logged with last_known_close proxy",
          "FLATTEN-NO-DATA" in out and "proxy=last_known_close" in out)
    st = json.loads((root / "paper" / f"position_{sym}.json").read_text())
    check("rungs 14:50/14:55/14:58 all booked in one tick despite no data",
          [r["k"] for r in st["rungs"]] == [0, 1, 2]
          and sum(r["shares"] for r in st["rungs"]) == 30000
          and all(r["bid_src"].startswith("FLATTEN-NO-DATA") for r in st["rungs"]),
          str([(r["k"], r["shares"], r["status"]) for r in st["rungs"]]))
    rc, out = run(["--book", "--clock", "14:59", "--once"], root)
    rc2, out2 = run(["--book", "--clock", "15:02", "--once"], root)
    fl = json.loads((root / "paper_days" / f"{DATE}.flatten.json").read_text())
    check("14:59 FINAL rung flattens (EXIT-FLATTEN) with no data",
          "EXIT-FLATTEN" in out and len(fl["records"]) == 1)
    check("state file unlinked",
          not (root / "paper" / f"position_{sym}.json").exists())
    ep = fl["records"][0].get("exit_parity") or {}
    check("exit_parity falls back to a proxy bar at 15:02",
          ep.get("proxy") and ep.get("close_1459") is not None, str(ep))


# --------------------------------------------------------------- scenario 3
def scenario_stale():
    print("\n[3] stale state file (dated 2026-08-24) is refused")
    root = fresh_root("stale")
    f = root / "paper" / "position_STALE.json"
    body = json.dumps(dict(sym="STALE", date="2026-08-24", entry=5.0,
                           shares=100, peak=5.5, scaled=False, banked=0.0,
                           status="OPEN", rungs=[]))
    f.write_text(body)
    rc, out = run(["--book", "--clock", "12:00", "--once"], root)
    check("--book exits 2", rc == 2, f"rc={rc}")
    check("STALE-STATE ... REFUSING printed", "STALE-STATE STALE dated 2026-08-24" in out
          and "REFUSING" in out)
    check("stale file untouched (byte-identical)", f.read_text() == body)
    check("no equity/heartbeat written on refusal",
          not list((root / "paper_days").glob("*")))
    bars = root / "bars.json"
    bars.write_text(json.dumps({"date": DATE, "bars": []}))
    rc, out = run(["STALE", "5.0", "100", "4.0", str(bars), "--clock", "12:00",
                   "--once"], root)
    check("legacy argv path also exits 2 on the stale file", rc == 2, f"rc={rc}")
    check("legacy: file still untouched", f.read_text() == body)
    f2 = root / "paper" / "position_NODATE.json"
    f2.write_text(json.dumps(dict(sym="NODATE", entry=1, shares=1)))
    f.unlink()
    rc, out = run(["--book", "--clock", "12:00", "--once"], root)
    check("file with no `date` is treated as stale (exit 2)", rc == 2
          and "dated NONE" in out, f"rc={rc}")


# --------------------------------------------------------------- scenario 4
def synth_series(sym, kind):
    """entry 10.00 on the 10:00 ET bar; then either
    'ptrail': +15% run with buyers (close=high), then sellers (close=low)
              stepping down 0.20/bar -> pressure <= -0.3 on the 7th seller
              bar whose low 10.10 <= 10.35 (11.50 x 0.9)
    'drift':  -9% drift with buyers on the tape (close=high) -> hard stop
              9.20 touched on bar 7, pressure stays +1"""
    rows = [dict(begins_at=utc_iso(10, 0), open=10.0, high=10.02, low=9.99,
                 close=10.0, volume=5000)]
    if kind == "ptrail":
        px = 10.0
        for m in range(1, 16):                     # 10:01-10:15 climb
            o = px
            px = round(10.0 + 1.5 * m / 15, 4)
            rows.append(dict(begins_at=utc_iso(10, m), open=o, high=px,
                             low=o, close=px, volume=5000))
        for j in range(1, 10):                     # 10:16-10:24 sellers
            h = round(11.5 - 0.2 * (j - 1), 4)
            l = round(11.5 - 0.2 * j, 4)
            rows.append(dict(begins_at=utc_iso(10, 15 + j), open=h, high=h,
                             low=l, close=l, volume=5000))
    else:
        for j in range(1, 11):                     # 10:01-10:10 drift down
            l = round(9.85 - 0.1 * j, 4)
            h = round(10.0 - 0.1 * j, 4)
            rows.append(dict(begins_at=utc_iso(10, j), open=l, high=h,
                             low=l, close=h, volume=5000))
    return rows


def scenario_modes():
    print("\n[4] exit modes on synthetic series")
    for mode, expect in (("ptrail", "EXIT-TRAIL"), ("hold", None),
                         ("c37", "EXIT-TRAIL")):
        root = fresh_root(f"mode_{mode}")
        write_csv(root / "rh_bars" / f"PTST_{DATE}.csv",
                  synth_series("PTST", "ptrail"))
        open_position(root, "PTST", 10.0, 1500, utc_iso(10, 0), 1)
        rc, out = run(["--book", "--clock", "11:00", "--once"], root,
                      env_mode=mode)
        fl = json.loads((root / "paper_days" / f"{DATE}.flatten.json").read_text()) \
            if (root / "paper_days" / f"{DATE}.flatten.json").exists() else {"records": []}
        state_exists = (root / "paper" / "position_PTST.json").exists()
        if expect:
            r = fl["records"][0] if fl["records"] else {}
            check(f"EXIT_MODE={mode}: 10% trail books {expect} at 10.35 "
                  f"after +15% peak, pressure <= -0.3",
                  expect in out and not state_exists and r
                  and abs(r["fills"][0]["px"] - 10.35) < 1e-6
                  and r["fills"][0]["time"].endswith("10:22:00-04:00"),
                  str(r.get("fills")))
        else:
            check(f"EXIT_MODE={mode}: no exit at 11:00, position still open",
                  "EXIT-" not in out and state_exists and not fl["records"])
            for clk in ("14:50", "14:55", "14:58", "14:59"):
                rc, out2 = run(["--book", "--clock", clk, "--once"], root,
                               env_mode=mode)
                out += out2
            fl = json.loads((root / "paper_days" / f"{DATE}.flatten.json").read_text())
            check(f"EXIT_MODE={mode}: ladder still flattens (no-data proxy) "
                  f"and unlinks",
                  "EXIT-FLATTEN PTST" in out and len(fl["records"]) == 1
                  and not (root / "paper" / "position_PTST.json").exists()
                  and fl["records"][0]["exit_kind"] == "ladder")
    # hard stop present in c37, absent in ptrail
    for mode, expect_exit in (("c37", True), ("ptrail", False)):
        root = fresh_root(f"drift_{mode}")
        write_csv(root / "rh_bars" / f"DRFT_{DATE}.csv",
                  synth_series("DRFT", "drift"))
        open_position(root, "DRFT", 10.0, 1500, utc_iso(10, 0), 1)
        rc, out = run(["--book", "--clock", "11:00", "--once"], root,
                      env_mode=mode)
        exited = "EXIT-STOP DRFT" in out
        check(f"EXIT_MODE={mode}: -9% drift with buyers -> "
              f"{'EXIT-STOP at 9.20 (hard stop)' if expect_exit else 'NO exit (no hard stop)'}",
              exited == expect_exit and (not expect_exit or "9.2000" in out))
    # --exit-mode flag overrides the env
    root = fresh_root("flag")
    write_csv(root / "rh_bars" / f"DRFT_{DATE}.csv", synth_series("DRFT", "drift"))
    open_position(root, "DRFT", 10.0, 1500, utc_iso(10, 0), 1)
    rc, out = run(["--book", "--clock", "11:00", "--once", "--exit-mode",
                   "ptrail"], root, env_mode="c37")
    check("--exit-mode flag wins over EXIT_MODE env", "EXIT-STOP" not in out)


# --------------------------------------------------------------- scenario 5
def scenario_posn():
    print("\n[5] posn.py reports on the open book (read-only)")
    root = fresh_root("posn")
    write_csv(root / "rh_bars" / f"PTST_{DATE}.csv", synth_series("PTST", "ptrail"))
    open_position(root, "PTST", 10.0, 1500, utc_iso(10, 0), 1)
    cmd = [sys.executable, str(HERE / "posn.py"), "--data-root", str(root),
           "--date", DATE, "--clock", "10:18", "--exit-mode", "ptrail"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = p.stdout + p.stderr
    check("posn runs and prints the active leg / ladder / size cap",
          p.returncode == 0 and "exit leg" in out and "ladder" in out
          and "size cap" in out, out.strip().splitlines()[-1] if out else "")
    check("posn did not touch the state file",
          (root / "paper" / "position_PTST.json").exists())
    cmd[-1] = "hold"
    p = subprocess.run(cmd, capture_output=True, text=True)
    check("posn hold mode says no stop armed",
          "no stop armed" in p.stdout, "")


def main():
    keep = "--keep" in sys.argv
    print(f"watch_book_selftest: scratch {SCRATCH}")
    scenario_ladder()
    scenario_no_data()
    scenario_stale()
    scenario_modes()
    scenario_posn()
    n_ok = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{n_ok}/{len(RESULTS)} checks passed -- "
          f"{'ALL PASS' if n_ok == len(RESULTS) else 'FAILURES: ' + str([n for n, ok in RESULTS if not ok])}")
    if not keep and SCRATCH.exists():
        shutil.rmtree(SCRATCH, ignore_errors=True)
    sys.exit(0 if n_ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
