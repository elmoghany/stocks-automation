"""LEGACY-9 step 6: rank = CHEAPEST eligible name (max(CS,AR)/2 on bars
[t-29, t], decision minute t inclusive -- causal), $10k tickets, same R4 engine
(no stop, defer fill, bearish/trail/flatten exits). Also cheapest-with-coil-tiebreak:
rank by h_e bucket (<=5, <=10, rest) then coil."""
import json, sys, time
from pathlib import Path
import numpy as np
P = Path(r"C:\cornell\stocks-automation\day-trading\plan")
sys.path.insert(0, str(P))
import cp_run as R
import cp_sim as S
from lm9_feat import half_at
from lm9_sim import mk, REC
S.TICKETS = [10_000.0] * 7
CUR = {}
_rd, _rk = S.run_day, S.rank_key

def run_day(day, Fd, cfg, cost=None):
    CUR["day"] = day; CUR["cache"] = {}
    return _rd(day, Fd, cfg, cost)

def hv(gi, Fd):
    day = CUR["day"]; t = int(Fd["grid"][gi])
    if gi not in CUR["cache"]:
        CUR["cache"][gi] = {}
    c = CUR["cache"][gi]
    elig = np.where(Fd["elig_last"][:, gi])[0]
    out = np.full(day.n, 1e9)
    for i in elig:
        i = int(i)
        if i not in c:
            c[i] = half_at(day, i, t + 1)[0]
        out[i] = c[i]
    return out

def rank_key(Fd, gi, cfg):
    if cfg["rank"] == "cheap":
        return hv(gi, Fd)
    if cfg["rank"] == "cheap_coil":
        h = hv(gi, Fd); b = np.where(h <= 5, 0, np.where(h <= 10, 1, 2))
        return b * 10.0 - np.nan_to_num(Fd["coil"][:, gi], nan=0.0)
    return _rk(Fd, gi, cfg)

S.run_day, S.rank_key = run_day, rank_key
t0 = time.time()
ds = R.dates() + R.dates(oos=True)
jobs = {k: (S.default_cfg(rank=k, stop_pct=None), mk(k), None) for k in ("cheap", "cheap_coil")}
legs = S.run_many(ds, jobs, progress=False)
out = {}
for k, Lg in legs.items():
    rec = REC[k]; rows = []
    for j, v in enumerate(Lg):
        (he, ie, ne), (hx, ix, nx) = rec[2 * j], rec[2 * j + 1]
        rows.append(dict(date=v["date"], sym=v["sym"], N=ne, g=v["gross"], h_e=he,
                         c_c=(ne * (0.5 * he + ie) + nx * (0.5 * hx + ix)) / 1e4, c_u=(ne * (he + ie) + nx * (hx + ix)) / 1e4))
    out[k] = rows
(P / "lm9_out/cheap_legs.json").write_text(json.dumps(out, default=float))
for k, r in out.items():
    for nm, a, b in (("Y1", "0", "2025-08-01"), ("Y2", "2025-08-01", "2026-08-01"), ("OOS", "2026-08-01", "9")):
        s = [x for x in r if a <= x["date"] < b]
        print(k, nm, len(s), "gross/tkt %+.2f net_c %+.2f net_u %+.2f net@15 %+.2f entry h %.1f" % (np.mean([x["g"] for x in s]), np.mean([x["g"] - x["c_c"] for x in s]), np.mean([x["g"] - x["c_u"] for x in s]), np.mean([x["g"] - x["N"] * 30e-4 for x in s]), np.mean([x["h_e"] for x in s])))
print("secs", round(time.time() - t0))
