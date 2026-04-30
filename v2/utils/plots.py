"""
Shared plotting utilities.
All functions return a matplotlib Figure so callers can save or display them.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator, AutoMinorLocator
import seaborn as sns


# ── Style constants ────────────────────────────────────────────────────────────
BLUE  = "#4C72B0"
BLACK = "black"


# ── Histogram helper ───────────────────────────────────────────────────────────

def nice_hist(data, bins: int, title: str, xlabel: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 4), dpi=150, constrained_layout=True)
    ax.hist(data, bins=bins, color=BLUE, edgecolor="black",
            linewidth=0.6, alpha=0.85)
    ax.set_title(title, loc="left", pad=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Number of Events")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.set_axisbelow(True)
    ax.grid(True, axis="y", which="major", linestyle=":", linewidth=0.8, alpha=0.6)
    ax.grid(True, axis="y", which="minor", linestyle=":", linewidth=0.5, alpha=0.35)
    ax.grid(False, axis="x")
    ax.spines[["top", "right"]].set_visible(False)
    return fig


# ── Discharge scatter ──────────────────────────────────────────────────────────

def plot_events_over_time(flow_events: pd.DataFrame) -> plt.Figure:
    """Scatter of peak discharge and total volume on a dual-axis timeline."""
    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax2 = ax1.twinx()

    ax1.scatter(flow_events["flow_peak_datetime"],  flow_events["flow_peak_m3_s"],
                color="orange", alpha=0.8, label="Peak Q (m³/s)")
    ax2.scatter(flow_events["flow_end"],            flow_events["flow_total_volume_m3"],
                color="royalblue", alpha=0.7, label="Volume (m³)")

    ax1.set_ylabel("Peak Discharge (m³/s)", color="orange", fontsize=12)
    ax2.set_ylabel("Total Volume (m³)",     color="royalblue", fontsize=12)
    ax1.tick_params(axis="y", labelcolor="orange")
    ax2.tick_params(axis="y", labelcolor="royalblue")
    ax1.set_xlabel("Date", fontsize=12)

    h1 = ax1.scatter([], [], color="orange",    label="Peak Q (m³/s)")
    h2 = ax2.scatter([], [], color="royalblue", label="Volume (m³)")
    ax1.legend([h1, h2], ["Peak Q (m³/s)", "Volume (m³)"], loc="upper left")

    fig.suptitle("Peak Discharge and Total Volume Over Time", fontsize=14, fontweight="bold")
    fig.tight_layout()
    return fig


# ── Rain intensity / cumulative ────────────────────────────────────────────────

def plot_rain_intensity(rain_dfs: list, labels: list,
                        start: str, end: str) -> plt.Figure:
    """Overlay rain intensity time series for multiple gauges."""
    t0 = pd.to_datetime(start, dayfirst=True)
    t1 = pd.to_datetime(end,   dayfirst=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    for df, label in zip(rain_dfs, labels):
        seg = df[(df["date_time"] >= t0) & (df["date_time"] <= t1)]
        ax.plot(seg["date_time"], seg["rain_intens_10min_mm_hr"], label=label)
    ax.set_title("Rain Intensity (mm/hr)")
    ax.set_xlabel("Date / Time")
    ax.set_ylabel("Intensity (mm/hr)")
    ax.set_ylim(0)
    ax.legend()
    ax.grid(True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H"))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    return fig


def plot_cumulative_rain(rain_dfs: list, labels: list,
                         start: str, end: str) -> plt.Figure:
    """Cumulative rain for multiple gauges over a period; prints totals."""
    t0 = pd.to_datetime(start, dayfirst=True)
    t1 = pd.to_datetime(end,   dayfirst=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    for df, label in zip(rain_dfs, labels):
        seg = df[(df["date_time"] >= t0) & (df["date_time"] <= t1)].copy()
        seg["cum"] = seg["rain_mm"].cumsum()
        print(f"{label}: {seg['cum'].iloc[-1]:.1f} mm" if not seg.empty else f"{label}: no data")
        ax.plot(seg["date_time"], seg["cum"], label=label)
    ax.set_title("Cumulative Rain (mm)")
    ax.set_xlabel("Date / Time")
    ax.set_ylabel("Cumulative Rain (mm)")
    ax.set_ylim(0)
    ax.legend()
    ax.grid(True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H"))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    return fig


# ── Hydrograph ─────────────────────────────────────────────────────────────────

def plot_hydrograph(discharge_df: pd.DataFrame,
                    rain_df: pd.DataFrame,
                    start: pd.Timestamp,
                    end: pd.Timestamp,
                    title: str = "Hydrograph",
                    catchment_area_km2: float = None) -> plt.Figure:
    """
    Dual-axis hydrograph: discharge (black line) + rain intensity bars (blue).
    Optionally prints an event summary when catchment_area_km2 is provided.
    """
    q_sel = discharge_df[
        (discharge_df["timestamp"] >= start) & (discharge_df["timestamp"] <= end)
    ].copy()
    r_sel = rain_df[
        (rain_df["date_time"] >= start) & (rain_df["date_time"] <= end)
    ].copy()

    # ── summary ──────────────────────────────────────────────────────────────
    dt_min = 10.0
    if len(r_sel) > 1:
        dt_min = (r_sel["date_time"].iloc[1] - r_sel["date_time"].iloc[0]).total_seconds() / 60.0
    total_rain_mm = (r_sel["rain_intens_10min_mm_hr"] * dt_min / 60.0).sum() if not r_sel.empty else 0.0

    peak_q    = q_sel["discharge_cms"].max() if not q_sel.empty else 0.0
    t_sec     = (q_sel["timestamp"] - q_sel["timestamp"].iloc[0]).dt.total_seconds() if not q_sel.empty else pd.Series([], dtype=float)
    total_vol = float(np.trapz(q_sel["discharge_cms"].values, t_sec.values)) if not q_sel.empty else 0.0

    if catchment_area_km2:
        rain_vol = total_rain_mm * catchment_area_km2 * 1000.0
        rc_str   = f"{total_vol / rain_vol:.3f}" if rain_vol > 0 else "N/A"
        print(f"\n{'='*45}")
        print(f" {title}")
        print(f"{'='*45}")
        print(f"  Accumulated rainfall : {total_rain_mm:.2f} mm")
        print(f"  Runoff volume        : {total_vol:,.0f} m³")
        print(f"  Peak discharge       : {peak_q:.3f} m³/s")
        print(f"  Runoff coefficient   : {rc_str}")
        print(f"{'='*45}\n")

    # ── plot ──────────────────────────────────────────────────────────────────
    try:
        plt.style.use("seaborn-v0_8-whitegrid")   # matplotlib >= 3.6
    except OSError:
        plt.style.use("seaborn-whitegrid")         # matplotlib < 3.6
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()

    qmax = peak_q if peak_q > 0 else 1.0

    if not q_sel.empty:
        ax1.plot(q_sel["timestamp"], q_sel["discharge_cms"],
                 color="black", linewidth=2, label="Discharge")

    if not r_sel.empty:
        ax2.bar(r_sel["date_time"], r_sel["rain_intens_10min_mm_hr"],
                width=pd.Timedelta(minutes=dt_min),
                color="#0000FF", alpha=0.45, label="Rain intensity [mm/h]")
        rmax = r_sel["rain_intens_10min_mm_hr"].max()
        ax2.set_ylim(rmax * 2.2, 0)
        nice_r = MaxNLocator(nbins=4).tick_values(0, rmax)
        ax2.set_yticks(nice_r[::-1])
    else:
        ax2.set_ylim(10, 0)

    ax1.set_xlim(start, end)
    ax1.set_ylim(0, qmax * 2)
    ax1.set_yticks(MaxNLocator(nbins=4).tick_values(0, qmax))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
    fig.autofmt_xdate(rotation=30)

    ax1.set_xlabel("Time", fontsize=16)
    ax1.set_ylabel("Discharge [m³/s]", fontsize=16)
    ax2.set_ylabel("Rainfall intensity [mm/h]", fontsize=16)
    ax1.yaxis.set_label_coords(-0.06, 0.20)
    ax2.yaxis.set_label_coords(1.06, 0.80)
    ax1.tick_params(axis="both", labelsize=13)
    ax2.tick_params(axis="both", labelsize=13)

    lines1, lbl1 = ax1.get_legend_handles_labels()
    lines2, lbl2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lbl1 + lbl2, fontsize=13,
               loc="upper right", framealpha=0.6)

    fig.suptitle(title, fontsize=18, fontweight="bold")
    fig.tight_layout()
    return fig
