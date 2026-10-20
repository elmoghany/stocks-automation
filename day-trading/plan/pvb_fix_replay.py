"""PVB-FIX (2026-10-19): what the four fixes would have changed on paper,
2026-10-09 .. 10-19 (the R4 LIVE-track days) plus RL 10-16.

R4: the fixed live code (p3_r4.fd_from_snaps premarket high + coil > 1
handling, capped DEPTH re-judged on the logged quotes) replayed end-of-day
on the session's OWN saved inputs (p3_r4_live.oct_replay, as PAPER-VS-BT's
pvb_r4_saved.py did with the old code -> data/pvb/r4_saved.json).
Bars: the full-day Robinhood bars PAPER-VS-BT fetched after the close
(data/pvb/rhx), truncated at each wall minute (what a fresh NEED_DATA fetch
returns). The session's own bars cannot be used for a counterfactual pick:
it only fetched the names its (old) ranking asked for. To separate the fix
from that data switch, the OLD code (git HEAD~ p3_r4.py / p3_r4_live.py,
run from a temp copy via PVB_OLD_DIR) is replayed on the same rhx bars.
Book checks: the session's logged checks (same name, same grid; a DEPTH
veto re-judged at the capped shares in the new run); names never checked
live use the bar proxies (LEGACY-9 spread, no print in 5 min = HALT).

P&L: a leg paper actually traded (same name, same grid) keeps paper's
OFFICIAL P&L; a new leg is priced at model fills (open of the first print
after t; R4 exits) with the live size floor(min($10k, cap x px) / px), no
cost charge (paper's quote fills ran $1.23/trade worse than model fills);
the 15 bps/side figure is shown alongside. Writes data/pvb/fix_replay.json.

    python plan/pvb_fix_replay.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if len(sys.argv) > 2 and sys.argv[1] == "--old":      # old code first
    import importlib.util as _iu
    for _m in ("p3_r4", "p3_r4_live"):
        _sp = _iu.spec_from_file_location(_m, str(Path(sys.argv[2]) /
                                                  f"{_m}.py"))
        _mod = _iu.module_from_spec(_sp)
        sys.modules[_m] = _mod
        _sp.loader.exec_module(_mod)
import p3_lib as P                                          # noqa: E402
import p3_r4 as R                                           # noqa: E402
import p3_r4_live as V                                      # noqa: E402
import pvb_compare as C                                     # noqa: E402

DAYS = ("2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14",
        "2026-10-15", "2026-10-16", "2026-10-19")
RHX = P.DATA / "pvb" / "rhx"


def legs_of(events):
    out, cur = [], None
    for e in events:
        if e[1] == "ENTER":
            cur = dict(sym=e[2], grid=e[3],
                       cap=e[6] if len(e) > 6 else None)
        elif e[1] == "EXIT" and cur is not None:
            me, xp = e[6], e[4]
            sh = e[11] if len(e) > 11 else (int(P.TICKET // me) if me else 0)
            cur.update(reason=e[3], entry=me, exit=xp, shares=sh,
                       exit_wall=e[0],
                       gross=round((xp - me) * sh, 2) if me else None,
                       net15=round(C.n15(me, xp, sh), 2) if me else None)
            out.append(cur)
            cur = None
        elif e[1].startswith("NO-EXIT") and cur is not None:
            cur.update(reason="no exit (bars end)")
            out.append(cur)
            cur = None
    return out


def main():
    import subprocess
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    for f in ("p3_r4.py", "p3_r4_live.py"):
        (tmp / f).write_text(subprocess.run(
            ["git", "show", f"{OLD_REV}:day-trading/plan/{f}"],
            capture_output=True, text=True, check=True,
            cwd=str(P.PLAN)).stdout)
    oldf = P.DATA / "pvb" / "fix_replay_old.json"
    subprocess.run([sys.executable, __file__, "--old", str(tmp), str(oldf)],
                   check=True, stdout=subprocess.DEVNULL)
    old = json.loads(oldf.read_text())
    new = V.oct_replay(DAYS, bars_dir=RHX, proxy=True)
    paper = C.paper_r4()
    res = dict(days={}, totals={})
    tp = tn = tn15 = 0.0
    print("\n=== R4 LIVE track, paper vs fixed-code replay ===")
    for d in DAYS:
        pl = [x for x in paper if x["date"] == d]
        ol = legs_of(old[d]["events"])
        nl = legs_of(new[d]["events"])
        pkey = {(x["sym"], x["grid"]): x for x in pl}
        rows = []
        for x in nl:
            p = pkey.get((x["sym"], x["grid"]))
            if p is not None:
                x.update(pnl=p["pnl"], src="paper official (unchanged leg)",
                         shares=p["shares"])
            else:
                x.update(pnl=x.get("gross"),
                         src="model fills, capped shares (new leg)")
            rows.append(x)
        pp = round(sum(x["pnl"] for x in pl), 2)
        npnl = round(sum((x.get("pnl") or 0) for x in rows), 2)
        n15 = round(sum((x["net15"] if x["src"].startswith("model")
                         else x["pnl"]) or 0 for x in rows), 2)
        changed = [(x["sym"], x["grid"]) for x in rows] != \
            [(x["sym"], x["grid"]) for x in pl]
        res["days"][d] = dict(
            paper=[dict(sym=x["sym"], grid=x["grid"], shares=x["shares"],
                        pnl=x["pnl"]) for x in pl],
            old_code_rhx=[(x["sym"], x["grid"], x.get("reason"),
                           x.get("gross")) for x in ol],
            new_replay=rows, paper_pnl=pp, fixed_pnl=npnl,
            fixed_pnl_new_legs_at_15bps=n15, change=round(npnl - pp, 2),
            changed=changed,
            refusals=[e for e in new[d]["events"] if e[1] in
                      ("REFUSED", "NO-BARS")][:20])
        tp += pp
        tn += npnl
        tn15 += n15
        print(f"{d}: paper {[(x['sym'], x['grid'], x['pnl']) for x in pl]} "
              f"= {pp:+.2f}")
        print(f"      old code {[(x['sym'], x['grid']) for x in ol]}")
        print(f"      fixed {[(x['sym'], x['grid'], x.get('shares'), x.get('reason'), x.get('pnl')) for x in rows]}"
              f" = {npnl:+.2f}  (change {npnl - pp:+.2f})"
              + ("" if changed else "  [same trades]"))
    res["totals"] = dict(paper=round(tp, 2), fixed=round(tn, 2),
                         change=round(tn - tp, 2),
                         fixed_new_legs_15bps=round(tn15, 2))
    print("TOTAL R4 10-09..10-19: paper", round(tp, 2), "fixed", round(tn, 2),
          "change", round(tn - tp, 2), "(new legs at 15 bps:",
          round(tn15, 2), ")")
    # ---- MODEL track on 10-19 (the frozen day): fixed EOD replay
    legs, st = R.live_decision("2026-10-19", P.M_CLOSE + 1)
    res["model_1019"] = dict(state=st["state"], legs=[
        dict(sym=x["sym"], t=P.hhmm(x["t"]), entry=x["entry"],
             exit=x["exit"], reason=x["reason"], shares=x["shares"])
        for x in legs])
    print("MODEL 10-19 (fixed):", res["model_1019"])
    (P.DATA / "pvb" / "fix_replay.json").write_text(
        json.dumps(res, indent=1, default=str))


OLD_REV = "5c7ccc8"          # the commit before PVB-FIX (PAPER-VS-BT)

if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[1] == "--old":
        assert "def snap_coil" not in Path(V.R.__file__).read_text()
        assert "exit_bars_dir" not in Path(V.__file__).read_text()
        res = V.oct_replay(DAYS, bars_dir=RHX, proxy=True)
        Path(sys.argv[3]).write_text(json.dumps(res, default=str))
    else:
        main()
