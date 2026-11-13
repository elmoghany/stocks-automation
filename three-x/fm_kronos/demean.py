"""POST-HOC add-on (written after seeing the test results, so treat with suspicion): subtract each variant's own trailing 120-day mean forecast
(causal: uses forecasts up to and including D only) to remove the level drift the zero-shot model shows in AMD's 2025-26 rally. Scored separately."""
from pathlib import Path
import pandas as pd
R = Path(__file__).parent.parent / "results"
f = pd.read_csv(R / "fm_kronos_forecasts.csv", parse_dates=["date"]).sort_values(["variant", "horizon", "date"])
f["pred_ret"] = f.pred_ret - f.groupby(["variant", "horizon"]).pred_ret.transform(lambda s: s.rolling(120, min_periods=20).mean())
f["variant"] = f.variant + "_demeaned"
f.dropna().to_csv(R / "fm_kronos_demeaned_forecasts.csv", index=False)
