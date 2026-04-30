"""
Rain–flow event matching and MultiIndex table construction.
"""
from datetime import timedelta
from typing import Optional
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg


def find_rain_boundary(rain_dfs: list, flow_time: pd.Timestamp,
                       direction: str) -> Optional[pd.Timestamp]:
    """
    Walk backward (direction='backward') from flow_time or forward
    (direction='forward') until all rain stations show < RAIN_THRESHOLD_MM
    within a RAIN_ACCUM_HOURS window.

    Returns the boundary timestamp or None if MAX_STEPS exceeded.
    """
    delta = timedelta(hours=cfg.RAIN_ACCUM_HOURS)
    step  = timedelta(hours=cfg.STEP_HOURS)
    sign  = -1 if direction == "backward" else +1

    positions = [flow_time + sign * step for _ in rain_dfs]

    for _ in range(cfg.MAX_STEPS):
        all_dry = []
        for i, rdf in enumerate(rain_dfs):
            t = positions[i]
            window = rdf.loc[t - delta : t] if direction == "backward" else rdf.loc[t : t + delta]
            is_dry = window["rain_mm"].sum() < cfg.RAIN_THRESHOLD_MM
            if not is_dry:
                positions[i] += sign * step
            all_dry.append(is_dry)

        if all(all_dry):
            return max(positions) if direction == "backward" else min(positions)

    return None


def build_rainflow_table(flow_events: pd.DataFrame,
                         rain_dfs: list,
                         station_names: list,
                         area_km2: float) -> pd.DataFrame:
    """
    For each flow event:
      1. Find rain window boundaries.
      2. Compute per-station rain statistics.
      3. Compute runoff depth and runoff coefficient.

    Returns a MultiIndex column DataFrame.
    """
    from utils.rain import summarize_rain_for_events

    # ── 1. find rain boundaries ────────────────────────────────────────────────
    rain_starts, rain_ends = [], []
    for _, row in flow_events.iterrows():
        rain_starts.append(find_rain_boundary(rain_dfs, row["flow_start"],  "backward"))
        rain_ends.append(  find_rain_boundary(rain_dfs, row["flow_end"],    "forward"))

    flow_events = flow_events.copy()
    flow_events["rain_event_start"] = rain_starts
    flow_events["rain_event_end"]   = rain_ends

    # ── 2. collect all intensity columns across stations ───────────────────────
    all_intens_cols = sorted({
        c for rdf in rain_dfs for c in rdf.columns if c.startswith("rain_intens_")
    })

    # ── 3. build MultiIndex dict ───────────────────────────────────────────────
    data = {}
    for col in ["flow_peak_datetime", "flow_peak_m3_s", "flow_total_volume_m3",
                "flow_start"]:
        data[("discharge", col)] = flow_events[col].values

    data[("rain", "rain_event_start")] = flow_events["rain_event_start"].values
    data[("rain", "rain_event_end")]   = flow_events["rain_event_end"].values

    for rdf, name in zip(rain_dfs, station_names):
        stats = summarize_rain_for_events(flow_events, rdf, all_intens_cols)
        data[(name, "total_mm")] = stats["total_mm"].values
        for col in all_intens_cols:
            data[(name, f"max_{col}")]      = stats[f"max_{col}"].values
            data[(name, f"{col}_datetime")] = stats[f"{col}_datetime"].values

    df = pd.DataFrame(data)
    df.columns = pd.MultiIndex.from_tuples(df.columns)

    # ── 4. runoff depth + coefficients ────────────────────────────────────────
    area_m2   = area_km2 * 1_000_000.0
    vol       = pd.to_numeric(df[("discharge", "flow_total_volume_m3")], errors="coerce")
    depth_mm  = 1000.0 * vol / area_m2
    df[("discharge", "runoff_depth_mm")] = depth_mm

    for name in station_names:
        rain_mm = pd.to_numeric(df[(name, "total_mm")], errors="coerce")
        rc = (depth_mm / rain_mm).where(rain_mm > 0)
        df[(name, "runoff_co")] = rc

    return df


def filter_by_total_rain(df: pd.DataFrame, station_names: list,
                         threshold_mm: float) -> pd.DataFrame:
    """Keep events where at least one station recorded >= threshold_mm."""
    mask = pd.Series(False, index=df.index)
    for name in station_names:
        col = (name, "total_mm")
        if col in df.columns:
            mask |= (df[col].notna() & (df[col] >= threshold_mm))
    return df[mask].copy()
