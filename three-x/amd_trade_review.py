"""Trade-by-trade review of the best time-only rule: buy day 12 after a report, sell 7 trading days before the next one, $100k.

Fills and account values come from the Vibe-Trading run. "Best during" is the highest close while holding, and "next buy" shows
what AMD did between this sale and the next purchase, which says whether being in cash helped. Writes results/amd_trade_review.csv.
"""
import pandas as pd
import yfinance as yf

import amd_cycle as A
import amd_quarters as Q
import sweep  # noqa: F401

NAME = "time_d12_before7"
Q.RULES[NAME] = {"rule": "quarter", "cadence": "D", "buy_on": "day", "day": 12, "before_next": 7}
raw = yf.download("AMD", start=A.BASE["start"], end=Q.END, auto_adjust=True, progress=False)
frame = pd.DataFrame({"close": raw["Close"].squeeze(), "open": raw["Open"].squeeze()}).dropna()
frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
reports = pd.to_datetime(A.REPORTS).sort_values()
eq = pd.read_csv(A.RES / "curves_amd" / f"AMD__amdcycle__Q_3y_{NAME}.csv", usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
eq = eq[~eq.index.duplicated()].loc[A.FROM:]
trades = pd.DataFrame(Q.trades_of(NAME, frame, reports))
rows, before = [], eq.iloc[0]
for i, t in enumerate(trades.itertuples()):
    bought, sold = pd.Timestamp(t.bought), pd.Timestamp(t.sold)
    after = eq.asof(sold)
    held = frame.close.loc[bought:sold]
    best = held.max()
    following = trades.iloc[i + 1].buy if i + 1 < len(trades) else frame.close.iloc[-1]
    rows.append({"bought": t.bought, "buy": t.buy, "sold": t.sold, "sell": t.sell, "gain": t.gain, "start_account": before, "profit": after - before, "account": after, "best_close": best, "best_date": held.idxmax().date(),
                 "best_gain": best / t.buy - 1, "days_held": len(held), "next_buy": following, "after_sale": following / t.sell - 1})
    before = after
r = pd.DataFrame(rows)
r.to_csv(A.RES / "amd_trade_review.csv", index=False)
pd.set_option("display.width", 220, "display.max_columns", 20)
print(r.to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
print(f"\ntotal profit {r.profit.sum():,.0f}; end {r.account.iloc[-1]:,.0f}; winners {(r.profit > 0).sum()} sum {r[r.profit > 0].profit.sum():,.0f}; losers {(r.profit < 0).sum()} sum {r[r.profit < 0].profit.sum():,.0f}")
print(f"average gain {r.gain.mean():+.1%}, median {r.gain.median():+.1%}; average winner {r[r.gain > 0].gain.mean():+.1%}, average loser {r[r.gain < 0].gain.mean():+.1%}")
print(f"cash period: AMD lower at next buy after {(r.after_sale < 0).sum()} of {len(r)} sales; higher after {(r.after_sale > 0).sum()}")
print(f"average days held {r.days_held.mean():.0f}; gave back from best close: median {((r.best_close / r.sell) - 1).median():.1%}")
print(f"today close {frame.close.iloc[-1]:.2f} on {frame.index[-1].date()}")
