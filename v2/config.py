"""
Central configuration: all file paths and hydrological parameters.
Edit this file to adapt the project to a new data location or season.
"""
from pathlib import Path

# ── Data root ────────────────────────────────────────────────────────────────
DATA_ROOT = Path(r"D:\Development\RESEARCH\Gazelle_Valley\Data")

# ── Discharge ─────────────────────────────────────────────────────────────────
DISCHARGE_RAW_CSV   = DATA_ROOT / "discharge" / "discharge_rakafot_gazelle.csv"
FLOW_EVENTS_CSV     = DATA_ROOT / "discharge" / "flow_events_processed.csv"
FLOW_RAIN_CSV       = DATA_ROOT / "discharge" / "flow_rain_events.csv"

# ── Rain gauges ────────────────────────────────────────────────────────────────
RAIN_ROOT = DATA_ROOT / "Precipiteion_Data"

GV_RAW_CSV   = RAIN_ROOT / "gazelle_valley" / "20230921_20250917.csv"
ZIV_RAW_CSV  = RAIN_ROOT / "ziv"            / "20230921_20250917.csv"
RAM_RAW_CSV  = RAIN_ROOT / "givat_ram"      / "20231030_20260429.csv"

GV_PROC_CSV  = RAIN_ROOT / "gazelle_valley" / "20230921_20250917_processed.csv"
ZIV_PROC_CSV = RAIN_ROOT / "ziv"            / "20230921_20250917_processed.csv"
RAM_PROC_CSV = RAIN_ROOT / "givat_ram"      / "20231030_20260429_processed.csv"

RAIN_EVENTS_RAM_CSV = RAIN_ROOT / "rain_events_givat_ram.csv"

# ── Station metadata ───────────────────────────────────────────────────────────
STATIONS = {
    "gazelle_valley": {"label": "Gazelle Valley", "color": "#8DA0CB", "type": "lab",  "interval_min": 10},
    "ziv":            {"label": "Ziv",             "color": "#66C2A5", "type": "lab",  "interval_min": 10},
    "givat_ram":      {"label": "Givat Ram",        "color": "#FC8D62", "type": "ims"},
}
STATION_KEYS  = list(STATIONS.keys())
STATION_FILES = {
    "gazelle_valley": GV_RAW_CSV,
    "ziv":            ZIV_RAW_CSV,
    "givat_ram":      RAM_RAW_CSV,
}

# ── Intensity durations (minutes) ─────────────────────────────────────────────
INTENSITY_DURATIONS = [10, 20, 30, 60, 120, 240, 360, 720, 1440]

# ── Discharge event detection ──────────────────────────────────────────────────
FLOW_THRESHOLD_CMS   = 0.01   # m³/s — minimum discharge to start an event
MERGE_GAP_HOURS      = 48     # hours — merge events closer than this

# ── Catchment ──────────────────────────────────────────────────────────────────
CATCHMENT_AREA_KM2   = 1.1

# ── Rain–flow matching ─────────────────────────────────────────────────────────
RAIN_ACCUM_HOURS     = 6      # window used to judge "is it raining?"
RAIN_THRESHOLD_MM    = 0.1    # mm in the window to count as rain
STEP_HOURS           = 24     # step size when walking forward/backward
MAX_STEPS            = 100    # safety limit

# ── Rain event identification ──────────────────────────────────────────────────
MIN_DRY_GAP_HOURS    = 6      # hours of no rain to split events
MIN_EVENT_TOTAL_MM   = 0.5    # mm — minimum total to keep an event

# ── Filtering ──────────────────────────────────────────────────────────────────
TOTAL_RAIN_THRESHOLD_MM = 1.0  # drop events where all stations < this
