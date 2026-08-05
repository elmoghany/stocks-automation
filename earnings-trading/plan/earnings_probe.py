"""Earnings-drift probe (SEPARATE BOOK -- holds OVERNIGHT through the
release, unlike the day-trading system). Hypothesis (user): stocks that
are strong over 5 years AND historically rise after earnings can be
bought at the close before earnings and sold after.

Gates per event (all point-in-time at the pre-earnings close):
  1. 5y total return >= +100% and price > 200-day SMA (strong + uptrend)
  2. the stock's PRIOR earnings reactions (close-before -> close-after):
     >= 6 known events, >= 60% positive, mean > 0
  3. halal (industry + ratio screen via day-trading.halal_check)
Trade: $15k at the close before the release; exit A = next session
close, exit B = next session open. Window: Oct 2024 - Jul 2026.
Data: yfinance daily history + earnings_dates. Output: JSON + stats.
"""

import importlib.util
import json
import sys
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location("dt", ROOT.parent / "day-trading" / "day-trading.py")
dt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dt)

UNIVERSE = """AAPL MSFT NVDA GOOGL AMZN META TSLA AVGO AMD QCOM TXN MU
ADBE CRM ORCL NOW INTU PANW CRWD FTNT ZS DDOG NET SNOW PLTR ANET SMCI
DELL HPQ CSCO IBM ACN LRCX AMAT KLAC ASML TSM ARM CDNS SNPS MRVL ON
NXPI ADI MCHP LLY UNH JNJ ABBV MRK PFE TMO ABT DHR ISRG SYK BSX MDT
REGN VRTX GILD AMGN BIIB MRNA ZTS DXCM EW HCA CI ELV CVS WMT COST PG
KO PEP MCD SBUX NKE LULU TJX HD LOW TGT DG DLTR ORLY AZO ROST YUM CMG
DPZ KHC GIS HSY CL KMB EL MNST CAT DE HON GE RTX LMT NOC GD BA UNP
CSX NSC UPS FDX EMR ETN PH ITW MMM ROK DOV XOM CVX COP EOG SLB PSX
VLO MPC OXY HES DVN FANG LIN APD SHW ECL FCX NEM NUE STLD VMC MLM
DIS NFLX CMCSA TMUS VZ T SPOT UBER ABNB BKNG MAR HLT RCL CCL DAL UAL
LUV AXP V MA PYPL""".split()

START = "2024-10-01"
END = "2026-08-01"


def probe(sym):
    t = yf.Ticker(sym)
    h = t.history(period="6y", auto_adjust=True)
    if len(h) < 1300:
        return []
    h.index = h.index.tz_localize(None)
    try:
        ed = t.get_earnings_dates(limit=40)
    except Exception:
        return []
    if ed is None or len(ed) == 0:
        return []
    dates = sorted({d.tz_localize(None).normalize() for d in ed.index})
    closes = h["Close"]
    opens = h["Open"]
    idx = closes.index
    events = []
    for d in dates:
        # pre = last session at-or-before the announcement date whose
        # close precedes the release; approximate: release after close
        # of day d (or before open of d) -> trade close of session
        # before the first post-release session. Use: pre = last idx
        # < d if release premarket-ambiguous; convention: pre = last
        # session STRICTLY before d, post = first session >= d ... to
        # avoid look-through ambiguity use close(d-1) -> close(d+0/1):
        pre_candidates = idx[idx < d]
        post_candidates = idx[idx >= d]
        if len(pre_candidates) == 0 or len(post_candidates) == 0:
            continue
        pre = pre_candidates[-1]
        post = post_candidates[0]
        p2 = idx[idx > post]
        react_c = (closes[post] / closes[pre] - 1) * 100
        react_o = (opens[post] / closes[pre] - 1) * 100
        # 5y momentum at pre date
        past = closes[closes.index <= pre]
        mom5 = None
        if len(past) >= 1250:
            mom5 = (past.iloc[-1] / past.iloc[-1250] - 1) * 100
        sma200 = past.tail(200).mean() if len(past) >= 200 else None
        events.append(dict(date=str(d.date()), pre=str(pre.date()),
                           react_c=round(react_c, 2),
                           react_o=round(react_o, 2),
                           mom5=round(mom5, 1) if mom5 is not None else None,
                           above200=bool(sma200 and past.iloc[-1] > sma200)))
    return events


def main():
    out = {}
    for n, sym in enumerate(UNIVERSE):
        try:
            ev = probe(sym)
        except Exception:
            ev = []
        if ev:
            out[sym] = ev
        if n % 20 == 0:
            print(f"  {n}/{len(UNIVERSE)}", flush=True)
    Path(ROOT / "data/earnings_events.json").write_text(json.dumps(out))
    print(f"saved {sum(len(v) for v in out.values())} events "
          f"across {len(out)} symbols", flush=True)


if __name__ == "__main__":
    main()
