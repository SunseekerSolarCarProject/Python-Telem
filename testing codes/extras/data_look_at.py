import pandas as pd
import os
from tkinter import Tk
from tkinter.filedialog import askopenfilenames

def analyze_files():
    # ─── User-configurable column names ──────────────────────────────────────
    timestamp_col         = 'timestamp'
    voltage_col           = 'BP_PVS_Voltage'
    inst_current_col      = 'BP_ISH_Amps'
    integ_current_col     = 'BP_PVS_Milliamp/s'  # integrated mA·s
    speed_cols            = ['MC1VEL_Velocity', 'MC2VEL_Velocity']

    # ─── Pick CSVs ────────────────────────────────────────────────────────────
    root = Tk(); root.withdraw()
    file_paths = askopenfilenames(
        title="Select CSV files",
        filetypes=[("CSV files", "*.csv")]
    )
    if not file_paths:
        print("No files selected."); return

    results = []
    for path in file_paths:
        print(f"\n▶ Loading '{os.path.basename(path)}'")
        try:
            df = pd.read_csv(path, parse_dates=[timestamp_col])
        except Exception as e:
            print(f"  ✗ Read error: {e}")
            continue

        print("  Columns:", df.columns.tolist())
        # check required columns
        req = {timestamp_col, voltage_col} | set(speed_cols)
        if not req.issubset(df.columns):
            print("  ✗ Missing:", req - set(df.columns))
            continue

        # ─── Compute average velocity ────────────────────────────────────────
        df['velocity_avg_m_s'] = df[speed_cols].mean(axis=1)

        # ─── Time delta ───────────────────────────────────────────────────────
        df['delta_t_s'] = df[timestamp_col].diff().dt.total_seconds().fillna(0)

        # ─── Energy via instantaneous current ────────────────────────────────
        if inst_current_col in df.columns:
            df['power_W']      = df[voltage_col] * df[inst_current_col]
            df['energy_Wh_inst'] = df['power_W'] * df['delta_t_s'] / 3600.0

        # ─── Energy via integrated current ──────────────────────────────────
        if integ_current_col in df.columns:
            # mA·s → A·s
            df['amp_sec']       = df[integ_current_col] / 1000.0
            df['energy_Wh_int'] = df[voltage_col] * df['amp_sec'] / 3600.0

        # ─── Distance ────────────────────────────────────────────────────────
        df['distance_m'] = df['velocity_avg_m_s'] * df['delta_t_s']

        # ─── Summaries ───────────────────────────────────────────────────────
        total_dist_m = df['distance_m'].sum()
        total_dist_mi = total_dist_m * 0.000621371

        # choose which energy to use
        if 'energy_Wh_int' in df:
            total_E = df['energy_Wh_int'].sum()
            method = 'integrated'
        elif 'energy_Wh_inst' in df:
            total_E = df['energy_Wh_inst'].sum()
            method = 'instant'
        else:
            print("  ✗ No current column found for energy calc."); continue

        wh_per_mile = total_E / total_dist_mi if total_dist_mi > 0 else float('nan')

        results.append({
            'file': os.path.basename(path),
            'method': method,
            'energy_Wh': round(total_E, 2),
            'distance_miles': round(total_dist_mi, 2),
            'Wh_per_mile': round(wh_per_mile, 2)
        })

    # ─── Output ─────────────────────────────────────────────────────────────
    if results:
        summary = pd.DataFrame(results)
        print("\n=== Wh/mile Summary ===")
        print(summary.to_string(index=False))
        summary.to_csv("wh_per_mile_summary.csv", index=False)
        print("\nSaved → wh_per_mile_summary.csv")
    else:
        print("\nNo results – check your column names.")

if __name__ == '__main__':
    analyze_files()
