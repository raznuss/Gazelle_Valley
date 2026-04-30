"""
Rain gauge loading, resampling, intensity computation, and event detection.
Handles both LAB tipping-bucket gauges and IMS official gauges.
"""
from collections import Counter
import pandas as pd
import numpy as np


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _compute_intensities(df: pd.DataFrame, base_step_min: float,
                         durations_min: list) -> pd.DataFrame:
    """
    Add rolling-window rainfall intensity columns (mm/hr) to df.
    df must have a 'rain_mm' column and a regular DatetimeIndex.
    """
    for dur in sorted(set(durations_min)):
        if dur <= 0:
            raise ValueError(f"Duration must be positive, got {dur}")
        if dur % base_step_min != 0:
            raise ValueError(
                f"Duration {dur} min is not a multiple of base step {base_step_min:.0f} min"
            )
        window = int(dur / base_step_min)
        col = f"rain_intens_{int(dur)}min_mm_hr"
        rolling = df["rain_mm"].rolling(window=window, min_periods=window).sum()
        df[col] = rolling * (60.0 / dur)
    return df


# ── LAB tipping-bucket gauge ───────────────────────────────────────────────────

def process_lab_gauge(file_path: str, interval_min: int = 10,
                      durations_min: list = None) -> pd.DataFrame:
    """
    Process a LAB HOBO tipping-bucket gauge CSV.

    Each row represents a 0.1 mm tip event.
    Steps:
      1. Resample to a fixed interval, summing tips → rain_mm.
      2. Zero out July and August (dew artefact).
      3. Compute rolling intensities for each requested duration.

    Returns a flat DataFrame: date_time | rain_mm | rain_intens_*min_mm_hr …
    """
    if interval_min not in (5, 10):
        raise ValueError("interval_min must be 5 or 10")
    if durations_min is None:
        durations_min = [10]

    df = pd.read_csv(file_path, parse_dates=["Date Time"], dayfirst=True)
    df = df.set_index("Date Time")
    df["rain_mm"] = 0.1

    freq = f"{interval_min}min"
    df = df.resample(freq).sum()

    # Remove dew artefact in summer
    df.loc[df.index.month.isin([7, 8]), "rain_mm"] = 0.0

    df = _compute_intensities(df, float(interval_min), durations_min)

    intensity_cols = [c for c in df.columns if c.startswith("rain_intens_")]
    df = df[["rain_mm"] + intensity_cols].reset_index()
    df = df.rename(columns={"Date Time": "date_time"})
    df["date_time"] = pd.to_datetime(df["date_time"])
    return df


# ── IMS official gauge ─────────────────────────────────────────────────────────

def process_ims_gauge(file_path: str, durations_min: list = None) -> pd.DataFrame:
    """
    Process an IMS official rain gauge CSV (pre-aggregated at 10-min intervals).

    Steps:
      1. Parse and clean timestamps (remove duplicates, strip timezone).
      2. Auto-detect the dominant time step.
      3. Resample and compute rolling intensities.

    Returns a flat DataFrame: date_time | rain_mm | rain_intens_*min_mm_hr …
    """
    if durations_min is None:
        durations_min = [10]

    df = pd.read_csv(file_path, parse_dates=["Date Time"], dayfirst=True)
    df["Date Time"] = pd.to_datetime(
        df["Date Time"], format="%d/%m/%Y %H:%M", errors="coerce"
    )
    df = (
        df.dropna(subset=["Date Time", "Rain (mm)"])
        .drop_duplicates(subset=["Date Time"], keep="first")
    )
    df["Date Time"] = df["Date Time"].dt.tz_localize(None)
    df = df.set_index("Date Time").rename(columns={"Rain (mm)": "rain_mm"})

    # Infer dominant time step
    diffs = df.index.to_series().diff().dropna().dt.total_seconds()
    most_common_sec = int(Counter(diffs.round()).most_common(1)[0][0])
    base_step_min   = most_common_sec / 60.0
    freq            = f"{int(most_common_sec // 60)}min"

    print(f"IMS gauge — detected interval: {freq}  "
          f"(step breakdown: {Counter(diffs.round()).most_common(3)})")

    df = df.resample(freq).sum().fillna(0.0)
    df.index = df.index.tz_localize(None)

    df = _compute_intensities(df, base_step_min, durations_min)

    intensity_cols = [c for c in df.columns if c.startswith("rain_intens_")]
    df = df[["rain_mm"] + intensity_cols].reset_index()
    df = df.rename(columns={"Date Time": "date_time"})
    df = (
        df.dropna(subset=["date_time"])
        .drop_duplicates(subset=["date_time"], keep="first")
        .sort_values("date_time")
        .reset_index(drop=True)
    )
    return df


# ── Rain event identification ──────────────────────────────────────────────────

def identify_rain_events(rain_df: pd.DataFrame,
                         rain_col: str = "rain_mm",
                         time_col: str = "date_time",
                         min_dry_gap_hours: float = 6,
                         min_event_total_mm: float = 0.5) -> pd.DataFrame:
    """
    Split a rain timeseries into discrete events separated by dry gaps.

    Returns a DataFrame with: rain_event_start | rain_event_end | total_rain_mm
    """
    df = rain_df.copy()
    if time_col in df.columns:
        df[time_col] = pd.to_datetime(df[time_col], dayfirst=True, errors="coerce")
        df = df.set_index(time_col)
    df = df.sort_index()

    wet = df[df[rain_col] > 0].copy()
    if wet.empty:
        return pd.DataFrame(columns=["rain_event_start", "rain_event_end", "total_rain_mm"])

    wet["gap_hr"]     = wet.index.to_series().diff().dt.total_seconds().div(3600).fillna(0)
    wet["new_event"]  = wet["gap_hr"] > min_dry_gap_hours
    wet["event_group"] = wet["new_event"].cumsum()

    rows = []
    for _, grp in wet.groupby("event_group"):
        total = grp[rain_col].sum()
        if total >= min_event_total_mm:
            rows.append({
                "rain_event_start": grp.index.min(),
                "rain_event_end":   grp.index.max(),
                "total_rain_mm":    total,
            })
    return pd.DataFrame(rows).reset_index(drop=True)


# ── Rain statistics per event ──────────────────────────────────────────────────

def summarize_rain_for_events(event_df: pd.DataFrame,
                               rain_df: pd.DataFrame,
                               intensity_cols: list = None) -> pd.DataFrame:
    """
    For each row in event_df (must have rain_event_start / rain_event_end),
    slice rain_df and compute:
      - total_mm
      - max_<col> and <col>_datetime for each intensity column

    rain_df must be indexed by datetime.

    Returns a DataFrame aligned to event_df's index.
    """
    if intensity_cols is None:
        intensity_cols = [c for c in rain_df.columns if c.startswith("rain_intens_")]

    records = []
    for _, row in event_df.iterrows():
        seg = rain_df.loc[row["rain_event_start"]:row["rain_event_end"]]
        rec = {"total_mm": seg["rain_mm"].sum() if not seg.empty else float("nan")}

        for col in intensity_cols:
            if col not in seg.columns or seg.empty:
                rec[f"max_{col}"]     = float("nan")
                rec[f"{col}_datetime"] = pd.NaT
                continue
            max_val = seg[col].max()
            rec[f"max_{col}"] = max_val
            rec[f"{col}_datetime"] = (
                seg[seg[col] == max_val].index[0] if pd.notna(max_val) else pd.NaT
            )
        records.append(rec)

    return pd.DataFrame(records, index=event_df.index)
