"""Forecast GTA VI's launch-day Twitch viewers, hour by hour.

Reads one case file (/input/<id>.in) and writes /output/<id>.out: for each of
hours 2..24 of the release day (UTC), five quantiles (5%, 25%, 50%, 75%, 95%)
of that hour's concurrent viewers in the game's Twitch category.

Method
------
Launch-day Twitch audiences follow a recognisable shape: the first UTC hour
is small (only the earliest timezones have unlocked), viewing dips a little,
bumps when the US East Coast unlocks, stays soft through the UTC midday, then
ramps hard into the evening peak (roughly 2x the first hour) before easing
off late. A flat "every hour stays at hour 1" forecast misses all of that.

So this program fits that shape from the case's own `comparables`: past big
launches' hourly curves. It keeps only the launches that look like this one:

* a complete 24-hour release day with every hour positive;
* a substantial first hour (>= 10,000 viewers), i.e. the game had already
  unlocked somewhere by 01:00 UTC -- the rolling-midnight pattern, not a
  single global unlock later in the day (those start near zero and explode
  100x, which would wreck the fit);
* no early-access contamination, no free-to-play / weak analogue, and never
  the target game's own pre-release history.

For each hour h it takes the median across those launches of
log(viewers_h / viewers_1) as the log-ratio, and the spread as 0.8x the
cross-launch standard deviation of that log-ratio (floored at 0.20 log
units, so the bands stay honest where launches disagree). The forecast is
then q_tau(h) = p1 * exp(median_h + z_tau * spread_h), where p1 is the
case's hour-1 print and z_tau the standard normal quantile at each level.

If the case carries too few usable comparables, it falls back to the same
shape fitted offline from the kit's comparables (constants below), so the
program still produces a valid forecast instead of crashing.

Standard library only, no network, deterministic: the same case always
produces the same bytes.
"""

import json
import math
import os
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

# The grader's -P leaves the repo root off sys.path; put it back first, so a
# module shipped beside this file would import. (This entry is one file.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at the scored levels.
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817,
     1.6448536269514722]

MIN_FIRST_HOUR = 10000      # a launch already unlocked somewhere by 01:00 UTC
MIN_USABLE_LAUNCHES = 5     # below this, use the offline fallback shape
SPREAD_SCALE = 0.8          # shrink the cross-launch spread a little
SPREAD_FLOOR = 0.20         # log units; never claim more certainty than this
MAX_VIEWERS = 1_000_000_000

# Offline fallback shape: median log-ratio to hour 1 and log spread per hour,
# fitted from the kit's GTA-like comparables (see module docstring). Used
# only when the case itself has too few usable comparables.
FALLBACK_MEDIAN = {
    2: -0.1421, 3: -0.3248, 4: -0.2876, 5: -0.1971, 6: -0.0107,
    7: -0.0213, 8: -0.0596, 9: -0.0886, 10: -0.0632, 11: -0.0745,
    12: -0.0223, 13: 0.1093, 14: 0.2633, 15: 0.4176, 16: 0.5022,
    17: 0.5713, 18: 0.6681, 19: 0.8761, 20: 0.8635, 21: 0.8460,
    22: 0.8322, 23: 0.7803, 24: 0.7122,
}
FALLBACK_SPREAD = {
    2: 0.2000, 3: 0.2773, 4: 0.2297, 5: 0.2000, 6: 0.3846,
    7: 0.4265, 8: 0.4578, 9: 0.4873, 10: 0.5180, 11: 0.5174,
    12: 0.5440, 13: 0.6024, 14: 0.6264, 15: 0.6459, 16: 0.6260,
    17: 0.5889, 18: 0.5411, 19: 0.5823, 20: 0.6158, 21: 0.6019,
    22: 0.5833, 23: 0.5563, 24: 0.5514,
}


def parse_time(text):
    """ISO 8601 UTC timestamp -> aware datetime ('Z' suffix tolerated)."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def round2_half_up(x):
    """Round to 2 decimals, half up; whole numbers come back as ints."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def release_day_hours(comparable):
    """Hour -> viewers for the comparable's release UTC day, or {} if sparse.

    Only returns a mapping when all 24 hours of the release day are present
    and positive; anything less cannot anchor a shape ratio.
    """
    try:
        start = parse_time(comparable["day_start"])
    except (KeyError, TypeError, ValueError):
        return {}
    end = start + timedelta(days=1)
    hours = {}
    for point in comparable.get("hourly") or []:
        try:
            at = parse_time(point["from"])
            viewers = point["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        if start <= at < end and isinstance(viewers, (int, float)):
            hours[(at - start).seconds // 3600 + 1] = viewers
    if len(hours) < 24:
        return {}
    if any(hours[h] is None or hours[h] <= 0 for h in range(1, 25)):
        return {}
    return hours


def is_launch_like(comparable, day, target_name):
    """Is this comparable a launch shaped like the target's?

    Rolling-midnight console launches with a real first hour. Excludes
    single-global-unlock launches (near-zero first hour, 100x ramp), early
    access, weak analogues, and the target game's own pre-release history.
    """
    if not day or day.get(1, 0) < MIN_FIRST_HOUR:
        return False
    if target_name and comparable.get("name", "").startswith(target_name):
        return False
    unlock = (comparable.get("unlock") or "").lower()
    if "not a launch" in unlock or "target-history" in unlock:
        return False
    if ("single global" in unlock or "simultaneous global" in unlock
            or "single simultaneous" in unlock):
        return False
    if "tier: weak" in unlock or "tier: early-access" in unlock:
        return False
    return True


def fit_shape(case):
    """Median log-ratio and spread per hour from the case's comparables.

    Returns ({hour: median log-ratio}, {hour: spread}); falls back to the
    offline constants when too few launches survive the filter.
    """
    target_name = (case.get("game") or {}).get("name") or ""
    days = []
    for comparable in case.get("comparables") or []:
        day = release_day_hours(comparable)
        if day and is_launch_like(comparable, day, target_name):
            days.append(day)
    if len(days) < MIN_USABLE_LAUNCHES:
        return dict(FALLBACK_MEDIAN), dict(FALLBACK_SPREAD)
    median = {}
    spread = {}
    for hour in range(2, 25):
        ratios = [math.log(day[hour] / day[1]) for day in days]
        median[hour] = statistics.median(ratios)
        spread[hour] = max(SPREAD_FLOOR,
                            SPREAD_SCALE * statistics.pstdev(ratios))
    return median, spread


def first_hour_print(case):
    """Hour-1 print, with defensive fallbacks so we never emit no forecast."""
    for row in case.get("known") or []:
        if row.get("hour") == 1 and row.get("viewers"):
            return max(1.0, float(row["viewers"]))
    hourly = case.get("history_hourly") or []
    if hourly:
        last = hourly[-1].get("viewers")
        if last:
            return max(1.0, float(last))
    return 1.0


def forecast_case(case):
    """One case -> {"hours": [{"hour": h, "q": [q05, ..., q95]}, ...]}."""
    p1 = first_hour_print(case)
    median, spread = fit_shape(case)
    rows = []
    wanted = [row["hour"] for row in case.get("forecast") or []]
    if not wanted:  # a case that lists no hours still gets hours 2..24
        wanted = list(range(2, 25))
    for hour in wanted:
        med = median.get(hour)
        sd = spread.get(hour)
        if med is None or sd is None:
            med, sd = FALLBACK_MEDIAN[hour], FALLBACK_SPREAD[hour]
        quantiles = []
        previous = 0.0
        for z in Z:
            value = p1 * math.exp(med + z * sd)
            value = min(max(value, 1e-6), MAX_VIEWERS)
            value = round2_half_up(value)
            if value < previous:  # rounding must never break ordering
                value = previous
            if value <= 0:
                value = previous if previous > 0 else 1
            quantiles.append(value)
            previous = value
        rows.append({"hour": hour, "q": quantiles})
    rows.sort(key=lambda r: r["hour"])
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        text = json.dumps(forecast, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / f"{path.stem}.out").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
