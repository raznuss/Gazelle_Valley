"""
Discharge event detection and processing.
"""
import pandas as pd
import numpy as np


def load_discharge(path: str) -> pd.DataFrame:
    """Load raw discharge CSV and return a clean timeseries DataFrame."""
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(
        df["Date"] + " " + df["Time"], dayfirst=True, errors="coerce"
    )
    df = (
        df[["timestamp", "Computed Discharge(m³/s)"]]
        .rename(columns={"Computed Discharge(m³/s)": "discharge_cms"})
        .dropna(subset=["timestamp", "discharge_cms"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    return df


def detect_raw_events(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Add a raw_event_id column: 0 = below threshold, >0 = event number.

    Fully vectorised — no Python loops.
    Trick: cumsum of the 'starts' boolean array gives a monotonically
    increasing event counter; masking with 'above' sets inter-event rows to 0.
    """
    df = df.copy()
    above  = df["discharge_cms"] > threshold
    starts = above & ~above.shift(fill_value=False)
    df["raw_event_id"] = (starts.cumsum() * above).astype(int)
    return df


def build_event_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each raw event, find the zero-crossing boundaries,
    compute volume (trapezoidal) and peak, return one row per event.

    Works on raw numpy arrays + positional indices to avoid repeated
    pandas DataFrame slicing inside the loop.
    """
    # Pull everything into numpy once — avoids per-iteration pandas overhead
    ts  = df["timestamp"].values          # numpy datetime64
    q   = df["discharge_cms"].values      # float64
    ids = df["raw_event_id"].values       # int

    zero_positions = np.where(q == 0)[0]  # pre-compute all zero positions

    rows = []
    for raw_id in np.unique(ids):
        if raw_id == 0:
            continue

        positions = np.where(ids == raw_id)[0]
        first_pos = int(positions[0])
        last_pos  = int(positions[-1])

        # last zero strictly before the event
        pre_zeros = zero_positions[zero_positions < first_pos]
        start_pos = int(pre_zeros[-1]) if len(pre_zeros) else 0

        # first zero strictly after the event
        post_zeros = zero_positions[zero_positions > last_pos]
        end_pos = int(post_zeros[0]) if len(post_zeros) else len(df) - 1

        seg_ts = ts[start_pos : end_pos + 1]
        seg_q  = q[start_pos  : end_pos + 1]

        # volume via trapz (timestamps → seconds)
        t_sec  = (seg_ts - seg_ts[0]).astype("timedelta64[s]").astype(np.float64)
        volume = float(np.trapz(seg_q, t_sec))

        peak_local = int(np.argmax(seg_q))

        rows.append({
            "flow_start":           pd.Timestamp(seg_ts[0]),
            "flow_end":             pd.Timestamp(seg_ts[-1]),
            "flow_peak_datetime":   pd.Timestamp(seg_ts[peak_local]),
            "flow_peak_m3_s":       float(seg_q[peak_local]),
            "flow_total_volume_m3": volume,
        })

    return (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["flow_start", "flow_end"])
        .sort_values("flow_start")
        .reset_index(drop=True)
    )


def merge_close_events(events: pd.DataFrame, max_gap_hours: float) -> pd.DataFrame:
    """Merge consecutive events separated by less than max_gap_hours."""
    events = events.sort_values("flow_start").reset_index(drop=True)
    merged, cur = [], events.iloc[0].copy()

    for _, nxt in events.iloc[1:].iterrows():
        gap = (nxt["flow_start"] - cur["flow_end"]).total_seconds() / 3600
        if gap <= max_gap_hours:
            cur["flow_end"]            = nxt["flow_end"]
            cur["flow_total_volume_m3"] += nxt["flow_total_volume_m3"]
            if nxt["flow_peak_m3_s"] > cur["flow_peak_m3_s"]:
                cur["flow_peak_m3_s"]      = nxt["flow_peak_m3_s"]
                cur["flow_peak_datetime"]  = nxt["flow_peak_datetime"]
        else:
            merged.append(cur.to_dict())
            cur = nxt.copy()

    merged.append(cur.to_dict())
    return pd.DataFrame(merged).reset_index(drop=True)


def assign_season_id(df: pd.DataFrame, date_col: str = "flow_start") -> pd.Series:
    """
    Return a Series of integer event IDs based on hydrological season
    (Sep–Aug). Format: season_index * 100 + event_number_within_season.
    E.g. 101, 102 … 201, 202 …
    """
    tmp = df[[date_col]].copy()
    tmp["season_year"] = tmp[date_col].apply(
        lambda d: d.year if d.month >= 9 else d.year - 1
    )
    tmp["season_index"] = tmp["season_year"] - tmp["season_year"].min() + 1
    tmp["event_number"] = tmp.groupby("season_year").cumcount() + 1
    return (tmp["season_index"] * 100 + tmp["event_number"]).astype("Int64")
