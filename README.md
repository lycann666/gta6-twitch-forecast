# gta6-twitch-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/lycann666/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/lycann666/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecast how many people watch Grand Theft Auto VI live on Twitch in each hour of its release day (19 November 2026, UTC), from the first hour's viewer count — as five quantiles an hour, scored by pinball loss on the log scale.

## How it forecasts

Launch-day Twitch audiences follow a recognisable shape: the first UTC hour is small (only the earliest timezones have unlocked), viewing dips, bumps when the US East Coast unlocks, stays soft through the UTC midday, then ramps hard into the evening peak (roughly 2× the first hour) before easing off late. A flat "every hour stays at hour 1" forecast misses all of that.

`main.py` fits that shape from the case's own `comparables` — past big launches' hourly curves — keeping only the launches shaped like this one: a complete 24-hour release day, a substantial first hour (≥ 10,000 viewers, i.e. already unlocked somewhere by 01:00 UTC), no single-global-unlock launches, no early-access contamination, no weak analogues, never the target game's own pre-release history. For each hour it takes the median across those launches of log(viewers / hour-1 viewers) and a spread of 0.8× the cross-launch standard deviation (floored at 0.20 log units), then forecasts `q = hour1 × exp(median + z × spread)`.

Practice results (4 past launches, answers verified against the historical source): pinball loss **0.250** vs **0.387** for the flat house baseline — better on every case; typical miss 47% vs 83%, 90% coverage 0.84 vs 0.78. If the case carries too few usable comparables it falls back to the same shape fitted offline (constants in `main.py`), so it still produces a valid forecast.

## Run it

```sh
python3 main.py
```

The grader runs `python3 /bot/main.py` (Python 3.13, standard library only, no network): it reads every `/input/<id>.in` and writes `/output/<id>.out` with 23 rows (hours 2–24), five quantiles each. Locally:

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=lycann&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
