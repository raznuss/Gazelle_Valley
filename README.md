# Gazelle Valley – Rain & Flow Data Processing

Scripts for analyzing hydrological data in the Gazelle Valley basin.

---

## 1. Discharge Event Detection (`01_discharge_data_process`)
- Identifies flow events from raw discharge data (threshold = 0.01 m³/s).
- Merges events within 48 hours.
- Calculates: start/end/peak time, total volume, peak discharge.
- Outputs: `flow_events_processed.csv` + hydrograph and event plots.

## 2. Rain Gauge Processing (`02_rain_gauge_data_process`)
- Processes rain data from 3 stations: Gazelle Valley, Ziv (LAB), Givat Ram (IMS).
- Resamples to fixed intervals (5–10 min), computes intensity (mm/hr).
- Sets summer rain (Jul–Aug) to 0 for LAB gauges.
- Saves cleaned `_processed.csv` files.

## 3. Rain–Flow Event Matching (`03_match_rain_to_flow_events`)
- Matches flow events with rain events (±24h window, 12h step).
- Extracts rainfall stats: total rain, peak intensity & timing.
- Builds MultiIndex DataFrame: flow + rain per event.
- Assigns seasonal event IDs (e.g. 2023/2024).
- Visualizes rain–flow relations and filters dry events.

---

## Output
- Clean rain and discharge tables.
- Event summary with rainfall & discharge metrics.
- Visual plots: hydrographs, histograms, scatter plots.

---

## Dependencies
`pandas`, `numpy`, `matplotlib`, `seaborn`, `datetime`
