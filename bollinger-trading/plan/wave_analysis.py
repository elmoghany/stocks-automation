"""Analyze actual price waves for 21 PASS stocks over 1 year.
Find peaks and troughs, measure wave amplitude, duration, and frequency."""

import json
import numpy as np
import pandas as pd
import yfinance as yf

SYMBOLS = [
    "LRCX", "TSM", "VRT", "AMSC", "AMD", "LLY", "ANET", "FIX",
    "TDW", "TJX", "MLI", "RMD", "HUBB", "ETN", "CDNS", "DECK",
    "AWI", "ISRG", "CTAS", "BMI", "FICO",
]


def find_peaks_troughs(closes, window=5):
    """Find local peaks and troughs using a rolling window.
    A peak is a point higher than `window` days on each side.
    A trough is a point lower than `window` days on each side.
    """
    peaks = []
    troughs = []
    values = closes.values
    dates = closes.index

    for i in range(window, len(values) - window):
        left = values[i - window:i]
        right = values[i + 1:i + window + 1]

        # Peak: higher than all neighbors in window
        if values[i] >= max(left) and values[i] >= max(right):
            peaks.append({"date": str(dates[i].date()), "price": round(float(values[i]), 2), "idx": i})

        # Trough: lower than all neighbors in window
        if values[i] <= min(left) and values[i] <= min(right):
            troughs.append({"date": str(dates[i].date()), "price": round(float(values[i]), 2), "idx": i})

    return peaks, troughs


def analyze_waves(symbol, df):
    """Analyze wave patterns for a stock."""
    if df is None or len(df) < 60:
        return None

    closes = df["Close"]
    current_price = float(closes.iloc[-1])

    # Find peaks and troughs with 5-day window
    peaks, troughs = find_peaks_troughs(closes, window=5)

    if len(peaks) < 2 or len(troughs) < 2:
        return None

    # Build wave cycles: trough -> peak -> trough
    # Merge peaks and troughs into chronological order
    all_points = []
    for p in peaks:
        all_points.append({"type": "peak", **p})
    for t in troughs:
        all_points.append({"type": "trough", **t})
    all_points.sort(key=lambda x: x["idx"])

    # Remove consecutive same-type points (keep the most extreme)
    cleaned = [all_points[0]]
    for i in range(1, len(all_points)):
        if all_points[i]["type"] == cleaned[-1]["type"]:
            # Same type: keep the more extreme one
            if all_points[i]["type"] == "peak":
                if all_points[i]["price"] > cleaned[-1]["price"]:
                    cleaned[-1] = all_points[i]
            else:
                if all_points[i]["price"] < cleaned[-1]["price"]:
                    cleaned[-1] = all_points[i]
        else:
            cleaned.append(all_points[i])

    # Calculate wave statistics
    up_waves = []    # trough to peak
    down_waves = []  # peak to trough

    for i in range(1, len(cleaned)):
        prev = cleaned[i - 1]
        curr = cleaned[i]
        days = curr["idx"] - prev["idx"]

        if prev["type"] == "trough" and curr["type"] == "peak":
            pct = (curr["price"] - prev["price"]) / prev["price"] * 100
            up_waves.append({
                "from_date": prev["date"], "to_date": curr["date"],
                "from_price": prev["price"], "to_price": curr["price"],
                "pct": round(pct, 2), "days": days,
            })
        elif prev["type"] == "peak" and curr["type"] == "trough":
            pct = (prev["price"] - curr["price"]) / prev["price"] * 100
            down_waves.append({
                "from_date": prev["date"], "to_date": curr["date"],
                "from_price": prev["price"], "to_price": curr["price"],
                "pct": round(pct, 2), "days": days,
            })

    if not up_waves or not down_waves:
        return None

    # Statistics
    up_pcts = [w["pct"] for w in up_waves]
    down_pcts = [w["pct"] for w in down_waves]
    up_days = [w["days"] for w in up_waves]
    down_days = [w["days"] for w in down_waves]

    # Recent waves (last 3 months)
    recent_up = [w for w in up_waves if w["from_date"] >= "2025-12-01"]
    recent_down = [w for w in down_waves if w["from_date"] >= "2025-12-01"]

    # Where is current price relative to recent range?
    recent_high = max(p["price"] for p in peaks[-5:])
    recent_low = min(t["price"] for t in troughs[-5:])
    position_in_range = (current_price - recent_low) / (recent_high - recent_low) * 100 if recent_high != recent_low else 50

    # Typical buy/sell targets based on wave stats
    avg_down_pct = np.mean(down_pcts)
    avg_up_pct = np.mean(up_pcts)
    median_down_pct = np.median(down_pcts)
    median_up_pct = np.median(up_pcts)

    # Estimated buy price: current price * (1 - median_down_pct/100)
    # Estimated sell price: buy_price * (1 + median_up_pct/100)
    est_buy = round(current_price * (1 - median_down_pct / 100), 2)
    est_sell = round(est_buy * (1 + median_up_pct / 100), 2)
    est_gain_pct = round((est_sell - est_buy) / est_buy * 100, 2)

    return {
        "symbol": symbol,
        "current_price": current_price,
        "recent_high": recent_high,
        "recent_low": recent_low,
        "position_in_range": round(position_in_range, 1),
        "total_waves_up": len(up_waves),
        "total_waves_down": len(down_waves),
        "avg_up_wave_pct": round(np.mean(up_pcts), 2),
        "median_up_wave_pct": round(np.median(up_pcts), 2),
        "max_up_wave_pct": round(max(up_pcts), 2),
        "min_up_wave_pct": round(min(up_pcts), 2),
        "avg_up_wave_days": round(np.mean(up_days), 1),
        "avg_down_wave_pct": round(np.mean(down_pcts), 2),
        "median_down_wave_pct": round(np.median(down_pcts), 2),
        "max_down_wave_pct": round(max(down_pcts), 2),
        "min_down_wave_pct": round(min(down_pcts), 2),
        "avg_down_wave_days": round(np.mean(down_days), 1),
        "avg_full_cycle_days": round(np.mean(up_days) + np.mean(down_days), 1),
        "est_buy_price": est_buy,
        "est_sell_price": est_sell,
        "est_gain_pct": est_gain_pct,
        "recent_peaks": peaks[-5:],
        "recent_troughs": troughs[-5:],
        "up_waves": up_waves,
        "down_waves": down_waves,
    }


def main():
    results = []
    for sym in SYMBOLS:
        print(f"Analyzing {sym}...", end=" ", flush=True)
        try:
            t = yf.Ticker(sym)
            df = t.history(period="1y")
            if df.empty:
                print("NO DATA")
                continue
            result = analyze_waves(sym, df)
            if result:
                results.append(result)
                print(f"Waves: {result['total_waves_up']}up/{result['total_waves_down']}down "
                      f"AvgUp={result['avg_up_wave_pct']}% AvgDown={result['avg_down_wave_pct']}% "
                      f"Cycle={result['avg_full_cycle_days']}d "
                      f"BuyAt=${result['est_buy_price']} SellAt=${result['est_sell_price']} "
                      f"Gain={result['est_gain_pct']}%")
            else:
                print("INSUFFICIENT DATA")
        except Exception as e:
            print(f"ERROR: {e}")

    # Save full results
    with open("plan/wave_stock_stats.json", "w") as f:
        json.dump(results, f, indent=2)

    # Print summary table
    print("\n" + "=" * 140)
    print(f"{'Stock':<6} {'Price':>8} {'Pos%':>5} {'Waves':>6} "
          f"{'AvgUp%':>7} {'MedUp%':>7} {'AvgDn%':>7} {'MedDn%':>7} "
          f"{'UpDays':>7} {'DnDays':>7} {'Cycle':>6} "
          f"{'BuyAt':>8} {'SellAt':>8} {'Gain%':>6}")
    print("-" * 140)
    for r in sorted(results, key=lambda x: x["est_gain_pct"], reverse=True):
        print(f"{r['symbol']:<6} ${r['current_price']:>7.2f} {r['position_in_range']:>4.0f}% "
              f"{r['total_waves_up']:>2}u/{r['total_waves_down']:<2}d "
              f"{r['avg_up_wave_pct']:>6.2f}% {r['median_up_wave_pct']:>6.2f}% "
              f"{r['avg_down_wave_pct']:>6.2f}% {r['median_down_wave_pct']:>6.2f}% "
              f"{r['avg_up_wave_days']:>6.1f}d {r['avg_down_wave_days']:>6.1f}d "
              f"{r['avg_full_cycle_days']:>5.1f}d "
              f"${r['est_buy_price']:>7.2f} ${r['est_sell_price']:>7.2f} "
              f"{r['est_gain_pct']:>5.2f}%")


if __name__ == "__main__":
    main()
