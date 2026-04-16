"""
Project 1: Fleet Rebalancing & Station Availability Analysis
=============================================================
Business Question: Which stations underperform, why, and how should we rebalance?

This script:
1. Computes station-level utilization metrics
2. Identifies stations with MoM utilization drops
3. Segments drops by bike type, time-of-day, and ward
4. Detects the October downtown anomaly
5. Generates rebalancing recommendations with expected impact
6. Outputs charts and a CSV summary
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

DATA = "/home/claude/portfolio/_shared_data"
OUT = "/home/claude/portfolio/project1_fleet_rebalancing/outputs"
os.makedirs(OUT, exist_ok=True)

# ============================================================
# 1. LOAD DATA
# ============================================================
print("Loading data...")
trips = pd.read_csv(f"{DATA}/trips.csv", parse_dates=["trip_start_time", "trip_end_time"])
stations = pd.read_csv(f"{DATA}/stations.csv")
weather = pd.read_csv(f"{DATA}/weather.csv", parse_dates=["weather_date"])

trips["trip_date"] = trips["trip_start_time"].dt.date
trips["trip_month"] = trips["trip_start_time"].dt.to_period("M")
trips["trip_hour"] = trips["trip_start_time"].dt.hour
trips["weekday"] = trips["trip_start_time"].dt.day_name()

print(f"  {len(trips):,} trips across {len(stations)} stations")

# ============================================================
# 2. STATION UTILIZATION METRICS
# ============================================================
print("\nComputing station utilization...")

# Trips per station per month (as start station)
station_month = (
    trips.groupby(["start_station_id", "trip_month"])
    .size().reset_index(name="trips")
    .rename(columns={"start_station_id": "station_id"})
)
station_month = station_month.merge(stations, on="station_id")
station_month["trips_per_dock"] = station_month["trips"] / station_month["capacity"]

# Save per-station monthly summary
station_month.to_csv(f"{OUT}/01_station_monthly_utilization.csv", index=False)

# ============================================================
# 3. MONTH-OVER-MONTH DROP DETECTION
# ============================================================
print("Detecting MoM drops...")

pivot = station_month.pivot_table(
    index=["station_id", "station_name", "ward", "area_type", "has_charging", "capacity"],
    columns="trip_month", values="trips", fill_value=0
).reset_index()

# Sep -> Oct comparison (where our injected anomaly lives)
sep_col = pd.Period("2025-09", freq="M")
oct_col = pd.Period("2025-10", freq="M")

pivot["sep_trips"] = pivot[sep_col]
pivot["oct_trips"] = pivot[oct_col]
pivot["mom_change_pct"] = 100 * (pivot["oct_trips"] - pivot["sep_trips"]) / pivot["sep_trips"].replace(0, np.nan)

# Seasonal baseline: Sep -> Oct drop is normal ~23% (seasonal). Flag stations dropping >35%.
SEASONAL_BASELINE = -23
ANOMALY_THRESHOLD = -35

pivot["is_anomalous"] = pivot["mom_change_pct"] < ANOMALY_THRESHOLD

anomalous = pivot[pivot["is_anomalous"]].sort_values("mom_change_pct")
anomalous[["station_id", "station_name", "ward", "area_type", "has_charging",
           "sep_trips", "oct_trips", "mom_change_pct"]].to_csv(
    f"{OUT}/02_anomalous_stations.csv", index=False
)
print(f"  Flagged {len(anomalous)} stations with abnormal drops")

# ============================================================
# 4. SEGMENTATION — IS IT BIKE-TYPE SPECIFIC?
# ============================================================
print("Segmenting by bike type and ward...")

bike_type_monthly = (
    trips.groupby(["start_station_id", "trip_month", "bike_type"])
    .size().reset_index(name="trips")
    .rename(columns={"start_station_id": "station_id"})
)
bike_type_monthly = bike_type_monthly.merge(stations[["station_id", "ward", "has_charging"]], on="station_id")

# Aggregate by ward and bike type for Sep vs Oct
ward_bike = (
    bike_type_monthly[bike_type_monthly["trip_month"].isin([sep_col, oct_col])]
    .groupby(["ward", "trip_month", "bike_type"])["trips"].sum()
    .reset_index()
)
ward_bike_pivot = ward_bike.pivot_table(
    index=["ward", "bike_type"], columns="trip_month", values="trips", fill_value=0
).reset_index()
ward_bike_pivot["mom_change_pct"] = 100 * (ward_bike_pivot[oct_col] - ward_bike_pivot[sep_col]) / ward_bike_pivot[sep_col].replace(0, np.nan)
ward_bike_pivot.columns = [str(c) for c in ward_bike_pivot.columns]
ward_bike_pivot.to_csv(f"{OUT}/03_ward_bike_type_change.csv", index=False)

# ============================================================
# 5. ROOT-CAUSE: DOWNTOWN E-BIKE CHARGING OUTAGE
# ============================================================
print("\nRoot-cause analysis...")

downtown_wards = ["Toronto Centre", "Spadina-Fort York", "University-Rosedale"]

downtown = trips[
    trips["start_station_id"].isin(stations[stations["ward"].isin(downtown_wards)]["station_id"])
].copy()
downtown["week"] = downtown["trip_start_time"].dt.to_period("W")

weekly_dt = downtown.groupby(["week", "bike_type"]).size().reset_index(name="trips")
weekly_dt["week_start"] = weekly_dt["week"].apply(lambda p: p.start_time)
weekly_dt.to_csv(f"{OUT}/04_downtown_weekly_by_biketype.csv", index=False)

# Compare the outage window (Oct 1-14) vs. baseline (Sep 15-30)
baseline = downtown[(downtown["trip_start_time"] >= "2025-09-15") & (downtown["trip_start_time"] < "2025-10-01")]
outage = downtown[(downtown["trip_start_time"] >= "2025-10-01") & (downtown["trip_start_time"] < "2025-10-15")]

def bt_share(df):
    return df["bike_type"].value_counts(normalize=True).mul(100).round(1).to_dict()

print("  Downtown e-bike share BEFORE (Sep 15-30):", bt_share(baseline))
print("  Downtown e-bike share DURING (Oct 1-14):", bt_share(outage))

# ============================================================
# 6. HOURLY PATTERN — are commute hours hit hardest?
# ============================================================
hourly = (
    trips.assign(period=np.where(
        trips["trip_month"] == oct_col, "Oct 2025",
        np.where(trips["trip_month"] == sep_col, "Sep 2025", "other")))
    .query("period != 'other'")
    .groupby(["period", "trip_hour"]).size().reset_index(name="trips")
)
hourly.to_csv(f"{OUT}/05_hourly_pattern_sep_vs_oct.csv", index=False)

# ============================================================
# 7. WEATHER CHECK — control for weather
# ============================================================
daily = trips.groupby("trip_date").size().reset_index(name="trips")
daily["trip_date"] = pd.to_datetime(daily["trip_date"])
weather["weather_date"] = pd.to_datetime(weather["weather_date"])
daily = daily.merge(weather, left_on="trip_date", right_on="weather_date")
daily.to_csv(f"{OUT}/06_daily_trips_with_weather.csv", index=False)

print(f"  Sep avg daily trips (dry days): {daily[(daily['weather_date'].dt.month == 9) & (~daily['is_rainy'])]['trips'].mean():.0f}")
print(f"  Oct avg daily trips (dry days): {daily[(daily['weather_date'].dt.month == 10) & (~daily['is_rainy'])]['trips'].mean():.0f}")

# ============================================================
# 8. REBALANCING RECOMMENDATIONS
# ============================================================
print("\nGenerating rebalancing recommendations...")

# Flow imbalance: net arrivals - net departures per station
departures = trips.groupby("start_station_id").size().reset_index(name="departures").rename(columns={"start_station_id": "station_id"})
arrivals = trips.groupby("end_station_id").size().reset_index(name="arrivals").rename(columns={"end_station_id": "station_id"})
flow = departures.merge(arrivals, on="station_id", how="outer").fillna(0)
flow["net_flow"] = flow["arrivals"] - flow["departures"]
flow = flow.merge(stations, on="station_id")
flow["imbalance_per_day"] = flow["net_flow"] / 182  # 6 months

# Top 10 accumulator stations (bikes pile up) and top 10 depletion stations (bikes run out)
top_accum = flow.nlargest(10, "imbalance_per_day")[
    ["station_id", "station_name", "ward", "capacity", "imbalance_per_day"]
]
top_deplete = flow.nsmallest(10, "imbalance_per_day")[
    ["station_id", "station_name", "ward", "capacity", "imbalance_per_day"]
]

top_accum.to_csv(f"{OUT}/07_top_accumulator_stations.csv", index=False)
top_deplete.to_csv(f"{OUT}/08_top_depletion_stations.csv", index=False)

# ============================================================
# 9. VISUALIZATIONS
# ============================================================
print("\nGenerating charts...")
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

# Chart 1: Overall daily trips with Oct shaded
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(daily["weather_date"], daily["trips"], color="#1A3550", linewidth=1.5)
ax.axvspan(pd.Timestamp("2025-10-01"), pd.Timestamp("2025-10-14"), alpha=0.25, color="#C0392B", label="Suspected charging outage")
ax.set_title("Daily Trips — June to November 2025", fontsize=13, fontweight="bold")
ax.set_ylabel("Trips per day")
ax.legend(loc="upper right")
ax.grid(alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
plt.tight_layout()
plt.savefig(f"{OUT}/chart_01_daily_trips.png", dpi=120, bbox_inches="tight")
plt.close()

# Chart 2: MoM change distribution
fig, ax = plt.subplots(figsize=(10, 5))
ax.hist(pivot["mom_change_pct"].dropna(), bins=30, color="#1A3550", edgecolor="white")
ax.axvline(SEASONAL_BASELINE, color="#888", linestyle="--", label=f"Seasonal baseline ({SEASONAL_BASELINE}%)")
ax.axvline(ANOMALY_THRESHOLD, color="#C0392B", linestyle="--", label=f"Anomaly threshold ({ANOMALY_THRESHOLD}%)")
ax.set_title("Station-Level Month-over-Month Change (Sep → Oct 2025)", fontsize=13, fontweight="bold")
ax.set_xlabel("% change in trips")
ax.set_ylabel("Number of stations")
ax.legend()
plt.tight_layout()
plt.savefig(f"{OUT}/chart_02_mom_distribution.png", dpi=120, bbox_inches="tight")
plt.close()

# Chart 3: Downtown weekly by bike type
fig, ax = plt.subplots(figsize=(12, 5))
for bt, color in [("classic", "#1A3550"), ("electric", "#C0392B")]:
    d = weekly_dt[weekly_dt["bike_type"] == bt].sort_values("week_start")
    ax.plot(d["week_start"], d["trips"], label=f"{bt.capitalize()} bikes", color=color, linewidth=2, marker="o")
ax.axvspan(pd.Timestamp("2025-09-29"), pd.Timestamp("2025-10-14"), alpha=0.2, color="#C0392B")
ax.set_title("Downtown Weekly Trips by Bike Type — E-bike usage collapses during outage", fontsize=13, fontweight="bold")
ax.set_ylabel("Weekly trips")
ax.legend()
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(f"{OUT}/chart_03_downtown_biketype.png", dpi=120, bbox_inches="tight")
plt.close()

# Chart 4: Hourly pattern comparison
fig, ax = plt.subplots(figsize=(11, 5))
for period, color in [("Sep 2025", "#1A3550"), ("Oct 2025", "#C0392B")]:
    d = hourly[hourly["period"] == period].sort_values("trip_hour")
    ax.plot(d["trip_hour"], d["trips"], label=period, color=color, linewidth=2, marker="o")
ax.set_title("Hourly Trip Pattern — September vs October 2025", fontsize=13, fontweight="bold")
ax.set_xlabel("Hour of day")
ax.set_ylabel("Total trips")
ax.set_xticks(range(0, 24, 2))
ax.legend()
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(f"{OUT}/chart_04_hourly_pattern.png", dpi=120, bbox_inches="tight")
plt.close()

# Chart 5: Top imbalance stations
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
ax1.barh(top_deplete["station_name"].str[:30], top_deplete["imbalance_per_day"], color="#C0392B")
ax1.set_title("Top 10 Depletion Stations (bikes run out)", fontweight="bold")
ax1.set_xlabel("Net bikes lost per day")
ax1.invert_yaxis()
ax2.barh(top_accum["station_name"].str[:30], top_accum["imbalance_per_day"], color="#1D6F42")
ax2.set_title("Top 10 Accumulator Stations (bikes pile up)", fontweight="bold")
ax2.set_xlabel("Net bikes gained per day")
ax2.invert_yaxis()
plt.tight_layout()
plt.savefig(f"{OUT}/chart_05_imbalance.png", dpi=120, bbox_inches="tight")
plt.close()

print("\n===== SUMMARY =====")
print(f"Total trips analysed: {len(trips):,}")
print(f"Stations flagged as anomalous: {len(anomalous)}")
print(f"Downtown e-bike share dropped from {bt_share(baseline).get('electric', 0)}% to {bt_share(outage).get('electric', 0)}%")
print(f"Top depletion station loses {abs(top_deplete.iloc[0]['imbalance_per_day']):.1f} bikes/day")
print(f"\nAll outputs saved to: {OUT}")
