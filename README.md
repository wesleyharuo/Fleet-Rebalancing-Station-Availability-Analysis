# Fleet Rebalancing & Station Availability Analysis

** Operations Analytics Case Study**
**Author:** Wesley Haruo Kurosawa
**Stack:** Python (pandas, matplotlib), SQL (PostgreSQL syntax)

---
<img width="1429" height="588" alt="chart_01_daily_trips" src="https://github.com/user-attachments/assets/570cae02-7f6d-4773-8da9-af55530e9c0a" />
<img width="1666" height="708" alt="chart_05_imbalance" src="https://github.com/user-attachments/assets/61862c2f-85ae-4d6b-b472-a1c117d6fc2d" />
<img width="1309" height="589" alt="chart_04_hourly_pattern" src="https://github.com/user-attachments/assets/459d0368-2fe9-445a-af9b-54de0df69aec" />
<img width="1427" height="588" alt="chart_03_downtown_biketype" src="https://github.com/user-attachments/assets/8e54d26e-15bd-4a84-821c-ccd75638d3bb" />
<img width="1189" height="589" alt="chart_02_mom_distribution" src="https://github.com/user-attachments/assets/38555c77-7873-4b62-b6dc-cfaea7261492" />


## Executive Summary

Between September and October 2025, overall ridership for a share system declined as expected due to seasonality — but a subset of downtown stations dropped at a rate far steeper than the seasonal baseline. This project detects that anomaly, isolates its root cause (an e-bike charging infrastructure outage affecting three downtown wards), quantifies the impact, and delivers a rebalancing recommendation for affected stations.

The analysis replicates the kind of investigation a Data Analyst on the Lyft Urban Solutions team would run when a city partner reports degraded service in a specific area.

**Key findings:**

| Finding | Evidence |
|---|---|
| System-wide MoM drop of ~22% is expected (seasonal baseline) | Historical trend + weather-controlled comparison |
| 2 downtown stations dropped >35% — not explained by seasonality or weather | MoM anomaly detection, Query 2 |
| E-bike share in downtown trips collapsed from **19.9% → 5.0%** during Oct 1–14 | Bike-type segmentation, Query 4 |
| Drop is concentrated in commute hours (8 AM, 5 PM), not off-peak | Hourly pattern comparison, Chart 4 |
| Root cause: temporary e-bike charging infrastructure outage | Isolated to charging-enabled downtown wards |

**Recommendation:** Deploy additional ICONIC (classic) bikes to affected downtown stations during the outage window; prioritize charging-station maintenance response time; add an early-warning alert when a ward's e-bike share deviates >30% from its 30-day rolling baseline.

---

## Business Context

Bike Share Toronto operates 1,042 stations and over 10,000 bikes across all 25 Toronto wards. The system recorded 7.8 million trips in 2025, with e-bikes delivering **twice the trips-per-day** of classic bikes. This makes e-bike availability a critical revenue driver — a charging outage doesn't just inconvenience riders; it materially affects the system's financial performance and its contractual SLAs with the Toronto Parking Authority.

As the operator, Lyft Urban Solutions is contractually required to maintain minimum service levels: bike availability at stations, fleet operational percentage, and maintenance response time. Detecting anomalies early and diagnosing them correctly is directly tied to contract compliance and revenue.

---

## Approach

The analysis follows a structured five-step diagnostic framework:

1. **Define baseline** — what does normal look like? (historical MoM trend, weather-adjusted)
2. **Detect anomalies** — which stations deviate beyond the baseline threshold?
3. **Segment the drop** — by bike type, ward, hour-of-day, user type
4. **Form and test hypotheses** — rule out weather, seasonality, station cannibalization; test for infrastructure failure
5. **Quantify impact and recommend action** — how much ridership was lost, what's the fix, how do we prevent recurrence

---

## Data

Six months of synthetic trip data (June–November 2025) matching the real Bike Share Toronto open data schema:

- **`trips.csv`** — 428,098 trips with timestamps, start/end stations, bike type, user type
- **`stations.csv`** — 118 stations with location, capacity, ward, charging capability
- **`weather.csv`** — Daily temperature and precipitation for the period

The dataset contains an **intentionally injected anomaly**: e-bike availability in three downtown wards (Toronto Centre, Spadina-Fort York, University-Rosedale) is suppressed from October 1–14 to simulate a charging infrastructure outage. This lets the analysis demonstrate a realistic detection → diagnosis → recommendation workflow.

---

## Methodology

### Step 1 — Station-level utilization baseline

Monthly trips per station, normalized by station capacity (trips-per-dock). This controls for differences in station size when comparing utilization across the network. *See Query 1.*

### Step 2 — Anomaly detection

For each station, compute month-over-month percentage change from September to October. Flag stations whose drop exceeds a **35% threshold** (the seasonal baseline is approximately 23%, so 35% represents a meaningful deviation). *See Query 2.*

### Step 3 — Root-cause hypothesis testing

Four competing hypotheses were tested:

| Hypothesis | Test | Verdict |
|---|---|---|
| **H1:** Weather-driven | Filter to dry days only, recompute | Rejected — dry-day trips also dropped |
| **H2:** Station cannibalization | Check for new nearby stations | Rejected — no new stations opened in the period |
| **H3:** Seasonal above expectation | Compare to prior-year seasonal curve | Rejected — deviation exceeds historical pattern |
| **H4:** Infrastructure failure (charging) | Segment by bike type | **Confirmed** — e-bike share collapsed while classic bike use stayed stable |

### Step 4 — Flow imbalance for rebalancing

To inform the operational response, compute net flow (arrivals − departures) per station. Stations with the largest negative net flow are prime candidates for proactive rebalancing moves. Each depletion station is paired with its nearest accumulator station within 2 km (Query 7), giving the operations team an actionable route plan.

---

## Key Results

### Downtown e-bike share — the smoking gun

| Period | Classic | Electric |
|---|---|---|
| Sep 15–30 (baseline) | 80.1% | 19.9% |
| Oct 1–14 (outage window) | 95.0% | 5.0% |

The classic-bike share jumped from 80% to 95% in two weeks — riders didn't stop riding, they switched to whatever bikes were available. This pattern is diagnostic of a supply-side issue (charging infrastructure), not a demand-side issue (weather, pricing, interest).

### Hourly pattern

The drop is concentrated in commute hours (8 AM and 5 PM). Off-peak hours show normal seasonal patterns. This reinforces the diagnosis — commuters rely on e-bikes for predictable, fast trips; recreational riders are more flexible.

### Weather control

Dry-day-only average trips:
- September: 2,381/day
- October: 1,856/day
- Drop: ~22% — in line with the seasonal baseline system-wide, but much smaller than the 35%+ drop seen in affected downtown stations.

---

## Recommendations

### Immediate (during outage)
1. **Deploy temporary ICONIC bike reinforcements** to the three affected downtown wards — increase classic fleet by ~20% in these stations until charging infrastructure is restored.
2. **Accelerate charging station maintenance** — reduce current mean-time-to-repair target by 50% for downtown charging docks.

### Medium-term (next quarter)
1. **Automated early-warning alert** — flag any ward where e-bike share deviates >30% from its 30-day rolling baseline. Current outage could have been detected within 48 hours instead of two weeks.
2. **Rebalancing route optimization** — Query 7 output suggests 20 depletion/supplier pairs that could reduce daily bike shortfall by up to 100 bikes/day through targeted rebalancing.

### Long-term (next year)
1. **Redundant charging capacity** in top-10 revenue stations so a single maintenance event doesn't collapse e-bike supply.
2. **Contractual clarification** — discuss SLA response-time targets with TPA given that charging-infrastructure outages have asymmetric revenue impact compared to non-charging maintenance events.

---

## Repository Structure

```
project1_fleet_rebalancing/
├── README.md                          # This file
├── analysis.py                        # Full Python analysis pipeline
├── queries.sql                        # 7 SQL queries (Postgres syntax)
└── outputs/
    ├── 01_station_monthly_utilization.csv
    ├── 02_anomalous_stations.csv
    ├── 03_ward_bike_type_change.csv
    ├── 04_downtown_weekly_by_biketype.csv
    ├── 05_hourly_pattern_sep_vs_oct.csv
    ├── 06_daily_trips_with_weather.csv
    ├── 07_top_accumulator_stations.csv
    ├── 08_top_depletion_stations.csv
    ├── chart_01_daily_trips.png
    ├── chart_02_mom_distribution.png
    ├── chart_03_downtown_biketype.png
    ├── chart_04_hourly_pattern.png
    └── chart_05_imbalance.png
```

---

## How to Run

```bash
# From project root
pip install pandas numpy matplotlib
python ../_shared_data/generate_data.py    # generates the input CSVs (only needs to run once)
python analysis.py                          # runs the full analysis
```

Outputs are written to `outputs/`.

---

## What This Project Demonstrates

- **Root-cause analysis on KPI degradation** — the exact workflow a Data Analyst uses when a city partner reports a service issue
- **Hypothesis-driven investigation** — not just reporting the drop, but ruling out alternative explanations
- **Segmentation discipline** — every aggregate metric broken down by bike type, ward, hour-of-day, user type
- **Operational translation** — converting analytical findings into specific rebalancing actions with quantified impact
- **SQL + Python dual implementation** — the same analysis in both stacks, showing fluency in both
- **Stakeholder-appropriate communication** — executive summary, technical methodology, and action-oriented recommendations in one document
