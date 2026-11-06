"""Paper-trade five AMD methods with Robinhood prices. Simulated fills only: this file places no orders and has no way to.

Each method is a separate $100,000 book. Decisions use completed daily bars after the close. Fills use the next open plus 5 bp, as in the backtests.
The books are replayed from stored bars on each run, so a rerun changes nothing and a missed day catches up. Bars and opens, once stored, are not rewritten.
Robinhood prices come from paper/rh_snapshot.json, written by a read-only headless session. Its interpolated bars are ignored, and yfinance fills any gaps.

Usage: amd_paper.py seed | run <open|close> | verify
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).parent
BOX = HERE / "paper"
START = "2026-11-05"  # first decision close; first possible fill is the 2026-11-06 open
WARM = "2023-08-01"  # signal history starts here, as in the backtests
CASH = 100_000.0
COST = 0.0005
SELL = {"sell_s": 90, "sell_r": 60, "sell_dn": 0.08, "min_days": 15}
BOOKS = {
    "day13": "Day 13 + AMD above 200-day",
    "month_end": "Month-end after report",
    "zone_qqq": "Zone + QQQ below 100-day",
    "second_low": "Second low",
    "day12_sell7": "Buy day 12, sell 7 before",
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rules = load("signal_template", HERE / "signal_template.py")
HOLIDAYS = load("market_calendar", HERE.parent / "day-trading" / "plan" / "market_calendar.py").HOLIDAYS


def trading_days(first, last):
    days = pd.bdate_range(first, last)
    return days[~days.strftime("%Y-%m-%d").isin(list(HOLIDAYS))]


def bar_file(code):
    return BOX / f"bars_{code}.csv"


def read_bars(code):
    return pd.read_csv(bar_file(code), index_col="date", parse_dates=["date"])


def yf_bars(code, start, end=None):
    raw = yf.download(code, start=start, end=end, auto_adjust=False, progress=False)
    out = pd.DataFrame({k.lower(): raw[k].squeeze() for k in ("Open", "High", "Low", "Close", "Volume")}).dropna()
    out.index = pd.DatetimeIndex(out.index).tz_localize(None).normalize()
    out.index.name = "date"
    return out


def thin(days):
    kept = []
    for i in sorted(days):
        if not kept or i - kept[-1] > 10:
            kept.append(i)
    return kept


def second_low(c, rsi, oversold, warm, bounce=0.03, tol=0.10, window=60, gain=5):
    """Oversold sets a first low. After a bounce, a return near it with higher RSI buys. Same as amd_buy_search.second_low with confirm 0."""
    out, state, low, low_rsi, low_i = [], 0, 0.0, 0.0, 0
    for i in range(warm, len(c)):
        x = c[i]
        if state and i - low_i > window:
            state = 0
        if state == 0:
            if oversold[i]:
                state, low, low_rsi, low_i = 1, x, rsi[i], i
        elif state == 1:
            if x < low:
                low, low_rsi, low_i = x, rsi[i], i
            elif x >= low * (1 + bounce):
                state = 2
        elif x <= low * (1 + tol):
            if rsi[i] >= low_rsi + gain:
                out.append(i)
                state = 0
            elif x < low:
                state, low, low_rsi, low_i = 1, x, rsi[i], i
    return out


def month_ends(days):
    """Positions of each month's last trading day, using the calendar for the newest bar so it is not assumed to end a month."""
    ahead = trading_days(days[-1] + pd.Timedelta(days=1), days[-1] + pd.Timedelta(days=10))
    following = list(days[1:]) + [ahead[0]]
    return np.array([i for i, (a, b) in enumerate(zip(days, following)) if a.month != b.month], dtype=int)


def positions(amd, qqq, reported, upcoming, start_date=START):
    """In or out at each close, for each book."""
    days = amd.index
    n = len(days)
    c, rsi, stoch, off, stretch = rules._zone_inputs(amd)
    start = int(days.searchsorted(pd.Timestamp(start_date)))
    warm = int(days.searchsorted(pd.Timestamp(WARM)))
    reports = sorted({int(days.searchsorted(pd.Timestamp(d))) for d in reported if pd.Timestamp(d) <= days[-1]})
    oversold = (stoch < 25) & (rsi < 40)
    above200 = (amd.close > amd.close.rolling(200).mean()).values
    q = qqq.close.reindex(days, method="ffill")
    qqq_low = (q < q.rolling(100).mean()).values

    def from_signals(raw):
        dates = [str(days[i].date()) for i in raw if i >= start]
        return rules._buydates_loop(c, rsi, stoch, off, stretch, days, {**SELL, "buy_dates": dates}, start) if dates else np.zeros(n)

    out = {
        "day13": from_signals(thin([r + 13 for r in reports if warm <= r + 1 and r + 13 < n and above200[r + 13]])),
        "zone_qqq": from_signals(thin([i for i in range(warm, n) if oversold[i] and qqq_low[i]])),
        "second_low": from_signals(thin(second_low(c, rsi, oversold, warm))),
    }

    dec = month_ends(days)
    flags = np.zeros(len(dec))
    for r in reports:
        after = int(np.searchsorted(dec, r, "right"))
        flags[after:after + 2] = 1.0
    state = pd.Series(np.nan, index=range(n))
    state.iloc[dec] = flags
    month = state.ffill().fillna(0.0).values
    month[:start] = 0.0
    ahead = dec[dec >= start]
    month[start:ahead[0] if len(ahead) else n] = 0.0
    out["month_end"] = month

    future = trading_days(days[-1] + pd.Timedelta(days=1), days[-1] + pd.Timedelta(days=200))
    every = days.append(future)
    quarter = np.zeros(n)
    for j, r in enumerate(reports):
        if j + 1 < len(reports):
            nxt = reports[j + 1]
        elif upcoming:
            nxt = int(every.searchsorted(pd.Timestamp(upcoming)))
        else:
            nxt = r + 63
        last, buy = nxt - 7, r + 12
        if buy < start or buy >= min(last, n):
            continue
        quarter[buy:min(last, n)] = 1.0
    out["day12_sell7"] = quarter
    return out


def read_opens():
    path = BOX / "opens.csv"
    return pd.read_csv(path, index_col="date", parse_dates=["date"]) if path.exists() else pd.DataFrame(columns=["open", "source"], index=pd.DatetimeIndex([], name="date"))


def open_of(date, amd, opens):
    if date in opens.index:
        return float(opens.loc[date, "open"])
    return float(amd.loc[date, "open"]) if date in amd.index else None


def next_trading(day):
    return trading_days(day + pd.Timedelta(days=1), day + pd.Timedelta(days=10))[0]


def replay(name, pos, amd, opens):
    """Trades for one book, with any decision still waiting on an open listed as pending."""
    days = amd.index
    start = int(days.searchsorted(pd.Timestamp(START)))
    cash, shares, rows = CASH, 0.0, []
    prev = 0.0
    for i in range(start, len(days)):
        if pos[i] == prev:
            continue
        prev = pos[i]
        side = "BUY" if pos[i] else "SELL"
        fill_day = next_trading(days[i])
        price = open_of(fill_day, amd, opens)
        row = {"book": name, "side": side, "decided": days[i].date(), "decided_close": round(float(amd.close.iloc[i]), 2), "fill_date": fill_day.date(), "fill_price": None, "shares": None, "cash_after": None, "status": "pending"}
        if price is not None:
            if side == "BUY":
                fill = price * (1 + COST)
                shares, cash = cash / fill, 0.0
                row["shares"] = round(shares, 4)
            else:
                fill = price * (1 - COST)
                row["shares"] = round(shares, 4)
                cash, shares = shares * fill, 0.0
            row.update(fill_price=round(fill, 2), cash_after=round(cash, 2), status="filled")
        rows.append(row)
        if price is None:
            break
    return rows, cash, shares


def ingest(mode):
    """Stores any newly completed bars and today's open. Prefers Robinhood, skips its interpolated bars, and falls back to yfinance. Returns warnings."""
    notes = []
    snap_path = BOX / "rh_snapshot.json"
    snap = {}
    if snap_path.exists():
        try:
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
        except ValueError as e:
            notes.append(f"Robinhood snapshot unreadable, using yfinance: {e}")
    else:
        notes.append("no Robinhood snapshot, using yfinance")
    now = pd.Timestamp.now("America/New_York").tz_localize(None)
    today = now.normalize()
    is_day = len(trading_days(today, today)) == 1
    done_today = is_day and mode == "close" and now.hour * 60 + now.minute >= 16 * 60 + 5
    last_done = today if done_today else trading_days(today - pd.Timedelta(days=10), today - pd.Timedelta(days=1))[-1]

    for code in ("AMD", "QQQ"):
        bars = read_bars(code)
        try:
            backup = yf_bars(code, str((today - pd.Timedelta(days=15)).date()))
        except Exception as e:  # network or parsing failure leaves Robinhood as the only source
            backup = bars.iloc[0:0]
            notes.append(f"yfinance {code} failed: {e}")
        rh = {}
        for b in snap.get("daily", {}).get(code, []):
            when = pd.Timestamp(b["begins_at"]).tz_localize(None).normalize()
            if not b.get("interpolated") and float(b.get("volume") or 0) > 0:
                rh[when] = b
        quote = snap.get("quotes", {}).get(code, {}).get("close") or {}
        for day in trading_days(bars.index[-1] + pd.Timedelta(days=1), last_done):
            row, source = None, ""
            if day in rh:
                b = rh[day]
                row, source = {"open": float(b["open_price"]), "high": float(b["high_price"]), "low": float(b["low_price"]), "close": float(b["close_price"]), "volume": float(b["volume"])}, "rh"
            elif day in backup.index:
                row, source = backup.loc[day].to_dict(), "yf"
            if row is None:
                notes.append(f"{code}: no bar yet for {day.date()}; decisions wait")
                break
            if quote.get("date") == str(day.date()) and not quote.get("interpolated"):
                row["close"], source = float(quote["price"]), source + "+rh_close"
            if day in backup.index and abs(row["close"] / backup.loc[day, "close"] - 1) > 0.01:
                notes.append(f"{code} {day.date()}: Robinhood close {row['close']:.2f} vs yfinance {backup.loc[day, 'close']:.2f}")
            row["source"] = source
            bars.loc[day] = row
        bars.to_csv(bar_file(code))

    if is_day:
        opens = read_opens()
        if today not in opens.index:
            rh_open = yf_open = None
            for b in snap.get("daily", {}).get("AMD", []):
                if pd.Timestamp(b["begins_at"]).tz_localize(None).normalize() == today and not b.get("interpolated") and float(b.get("volume") or 0) > 0:
                    rh_open = float(b["open_price"])
            first = snap.get("first_5min_open_AMD")
            if rh_open is None and first:
                rh_open = float(first)
            try:
                backup = yf_bars("AMD", str(today.date()))
                yf_open = float(backup.loc[today, "open"]) if today in backup.index else None
            except Exception:
                yf_open = None
            value, source = (rh_open, "rh") if rh_open is not None else (yf_open, "yf")
            if rh_open is not None and yf_open is not None and abs(rh_open / yf_open - 1) > 0.01:
                notes.append(f"open differs: Robinhood {rh_open:.2f} vs yfinance {yf_open:.2f}; using yfinance")
                value, source = yf_open, "yf"
            if value is not None and (now.hour, now.minute) >= (9, 30):
                opens.loc[today, ["open", "source"]] = [value, source]
                opens.to_csv(BOX / "opens.csv")
            elif (now.hour, now.minute) >= (9, 30):
                notes.append("no open price yet for today; fills wait")

    reports_path = BOX / "reports.json"
    known = json.loads(reports_path.read_text(encoding="utf-8"))
    for e in snap.get("earnings", []):
        date = e.get("date")
        if not date:
            continue
        if e.get("actual") is not None and date <= str(today.date()) and date not in known["reported"]:
            known["reported"] = sorted(known["reported"] + [date])
            notes.append(f"new AMD report recorded: {date}")
        elif e.get("actual") is None and date > str(today.date()):
            if known.get("upcoming") != date:
                notes.append(f"next AMD report now {date} (verified {e.get('verified')})")
            known["upcoming"], known["upcoming_verified"] = date, e.get("verified")
    reports_path.write_text(json.dumps(known, indent=1), encoding="utf-8")
    return notes


def run(mode):
    notes = ingest(mode)
    amd, qqq = read_bars("AMD"), read_bars("QQQ")
    known = json.loads((BOX / "reports.json").read_text(encoding="utf-8"))
    opens = read_opens()
    pos = positions(amd[["open", "high", "low", "close", "volume"]], qqq, known["reported"], known.get("upcoming"))
    seen_path = BOX / "seen.json"
    seen = set(json.loads(seen_path.read_text(encoding="utf-8"))) if seen_path.exists() else set()
    rows, table, alerts = [], [], []
    last = float(amd.close.iloc[-1])
    for name, label in BOOKS.items():
        trades, cash, shares = replay(name, pos[name], amd, opens)
        rows += trades
        value = cash + shares * last
        table.append((label, "in AMD" if shares else "cash", shares, value))
        for t in trades:
            key = f"{name}|{t['side']}|{t['decided']}|{t['status']}"
            if key in seen:
                continue
            seen.add(key)
            if t["status"] == "pending":
                alerts.append(f"AMD PAPER signal: {label} will {t['side']} at the {t['fill_date']} open (close ${t['decided_close']:.2f}). No real order.")
            else:
                verb = "BOUGHT" if t["side"] == "BUY" else "SOLD"
                alerts.append(f"AMD PAPER {verb}: {label}, {t['shares']:.2f} shares at ${t['fill_price']:.2f} on {t['fill_date']}. No real order.")
    pd.DataFrame(rows, columns=["book", "side", "decided", "decided_close", "fill_date", "fill_price", "shares", "cash_after", "status"]).to_csv(BOX / "ledger.csv", index=False)
    seen_path.write_text(json.dumps(sorted(seen), indent=0), encoding="utf-8")

    first = next_trading(pd.Timestamp(START))
    base = open_of(first, amd, opens)
    hold = CASH * last / (base * (1 + COST)) if base and amd.index[-1] >= first else CASH
    stamp = amd.index[-1].date()
    curve = BOX / "equity.csv"
    old = pd.read_csv(curve, dtype={"date": str}) if curve.exists() else pd.DataFrame()
    fresh = pd.DataFrame([{"date": str(stamp), **{n: round(t[3], 2) for n, t in zip(BOOKS, table)}, "hold": round(hold, 2)}])
    pd.concat([old[old.date != str(stamp)] if len(old) else old, fresh]).to_csv(curve, index=False)

    lines = [f"Last close {stamp}: ${last:.2f}. Updated {pd.Timestamp.now('America/New_York').strftime('%Y-%m-%d %H:%M')} ET, run {mode}. Paper only: simulated fills, no real orders.", "", "```", f"{'Book':<30}{'Position':<10}{'Shares':>10}{'Value':>13}{'Return':>9}"]
    for label, state, shares, value in table:
        lines.append(f"{label:<30}{state:<10}{shares:>10.2f}{value:>13,.0f}{value / CASH - 1:>9.1%}")
    lines.append(f"{'Hold AMD, bought at first open':<30}{'in AMD':<10}{'':>10}{hold:>13,.0f}{hold / CASH - 1:>9.1%}")
    lines += ["```", "", f"Next AMD report: {known.get('upcoming') or 'not known'} (verified: {known.get('upcoming_verified')}).", ""]
    waiting = [r for r in rows if r["status"] == "pending"]
    lines.append("Waiting to fill: " + ("; ".join(f"{BOOKS[r['book']]} {r['side']} at the {r['fill_date']} open" for r in waiting) if waiting else "none") + ".")
    if notes:
        lines += ["", "Notes: " + "; ".join(notes) + "."]
    (BOX / "status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(BOX / "notify_queue.txt", "a", encoding="utf-8") as f:
        for a in alerts:
            f.write(a + "\n")
    print("\n".join(lines))
    for a in alerts:
        print("ALERT", a)


def seed():
    BOX.mkdir(exist_ok=True)
    for code in ("AMD", "QQQ"):
        bars = yf_bars(code, "2022-01-01", "2026-11-06")
        bars["source"] = "yf_seed"
        bars.to_csv(bar_file(code))
    dates = json.loads((HERE / "results" / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"]
    (BOX / "reports.json").write_text(json.dumps({"reported": sorted(d for d in dates if d <= "2026-11-05"), "upcoming": "2027-02-02", "upcoming_verified": False}, indent=1), encoding="utf-8")
    print("seeded", read_bars("AMD").index[-1].date(), read_bars("QQQ").index[-1].date())


def verify():
    """Checks each book's history against the backtest code it came from, over the backtest windows."""
    import amd_buy_search as B
    import amd_cycle as A
    import amd_zone_search as Z
    amd, qqq = Z.frame.copy(), yf_bars("QQQ", "2022-01-01", Z.END)
    known = json.loads((HERE / "results" / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"]
    known = [d for d in known if d <= str(amd.index[-1].date())]
    ok = True
    ours = positions(amd, qqq, known, None, WARM)
    backtest = {
        "zone_qqq": B.replay(B.thin([i for i in B.zone(25, 40, 0, 0) if B.FILTERS["QQQ below 100d"][i]])),
        "second_low": B.replay(B.thin(B.second_low(0.03, 0.10, 60, 5, 0))),
        "day13": B.replay(B.thin([i for i in B.after_report("any", 0, "day 13") if B.FILTERS["AMD above 200d"][i]])),
    }
    for name, pos in backtest.items():
        off = np.nonzero(pos[:len(amd) - 1] != ours[name][:len(amd) - 1])[0]
        print(f"{name}: {'same as backtest' if not len(off) else f'{len(off)} days differ, first {amd.index[off[0]].date()}'}; buys {(np.diff(pos, prepend=0.0) > 0).sum()}")
        ok = ok and not len(off)
    for name, cfg, begin in (("month_end", {"rule": "after", "cadence": "M", "a": 0, "b": 2}, "2023-11-06"), ("day12_sell7", {"rule": "quarter", "cadence": "D", "buy_on": "day", "day": 12, "before_next": 7}, "2023-11-06")):
        theirs = rules._amdcycle(amd, {**A.BASE, **cfg, "reports": known, "trade_from": begin}).values
        mine = positions(amd, qqq, known, None, begin)[name]
        off = np.nonzero(theirs[:-1] != mine[:-1])[0]
        print(f"{name}: {'same as backtest' if not len(off) else f'{len(off)} days differ, first {amd.index[off[0]].date()}'}; buys {(np.diff(theirs, prepend=0.0) > 0).sum()}")
        ok = ok and not len(off)
    print("ALL MATCH" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "seed":
        seed()
    elif command == "run":
        run(sys.argv[2])
    elif command == "verify":
        verify()
