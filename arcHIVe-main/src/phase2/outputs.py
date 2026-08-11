from __future__ import annotations

import html
import json
import sqlite3
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def save_table(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def write_sqlite(
    path: Path,
    municipalities: pd.DataFrame,
    forecasts: pd.DataFrame,
    decomposition: pd.DataFrame,
    recommendations: pd.DataFrame,
    alerts: pd.DataFrame,
    regional: pd.DataFrame,
    edges: pd.DataFrame,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as connection:
        municipalities.to_sql("municipalities", connection, index=False)
        forecasts.to_sql("forecast_values", connection, index=False)
        forecasts[[
            "PERIOD", "PSGC", "PROVINCE", "LOCATION", "GLOBAL_MORANS_I", "LOCAL_MORANS_I",
            "LOCAL_MORAN_CLUSTER", "GI_STAR_Z_SCORE", "GI_STAR_P_VALUE", "HOTSPOT_CLASS",
            "HOTSPOT_CLUSTER_ID", "HOTSPOT_CLUSTER_SIZE",
        ]].to_sql("hotspot_results", connection, index=False)
        forecasts[[
            "PERIOD", "PSGC", "PROVINCE", "LOCATION", "POPULATION",
            "MONTHLY_POPULATION_GROWTH_RATE", "NATURAL_POPULATION_CHANGE",
            "NET_MIGRATION_CHANGE", "PLHIV_NET_MIGRATION",
            "NEW_INFECTIONS_ESTIMATE", "NEW_INFECTION_RATE_PER_100K",
            "PREDICTED_CASES", "DIAGNOSIS_GROWTH_RATIO",
            "EFFECTIVE_INFECTIOUS_POOL", "LOCAL_INFECTIOUS_PREVALENCE",
            "NEIGHBOR_INFECTIOUS_PREVALENCE", "NEIGHBOR_INFECTIOUS_POOL_PER_100K",
            "NEIGHBOR_RATE_PER_100K", "TESTING_ACCESS_SCORE",
            "CENTER_EFFECT_ON_TRANSMISSION", "ACTIVE_TESTING_CENTERS",
            "NEW_TESTING_CENTERS_OPENED", "PENDING_TESTING_CENTERS",
            "TRANSMISSION_PRESSURE_INDEX", "TRANSMISSION_PRESSURE_LEVEL",
            "TESTING_CENTER_NEED_SCORE",
        ]].to_sql("transmission_pressure", connection, index=False)
        forecasts[[
            "PERIOD", "PSGC", "PROVINCE", "LOCATION", "POPULATION",
            "PLHIV_UNDIAGNOSED", "PLHIV_DIAGNOSED_NOT_ON_ART",
            "PLHIV_ON_ART_UNSUPPRESSED", "PLHIV_VIRALLY_SUPPRESSED", "TOTAL_PLHIV",
            "EFFECTIVE_INFECTIOUS_POOL", "NEW_INFECTIONS_ESTIMATE", "PREDICTED_CASES",
            "NEW_ART_ENROLLMENTS", "NEWLY_VIRALLY_SUPPRESSED",
            "TREATMENT_INTERRUPTION", "PLHIV_ATTRITION", "ART_COVERAGE",
            "VIRAL_SUPPRESSION_COVERAGE", "INFECTIOUS_POOL_REDUCTION_FROM_TREATMENT",
            "TREATMENT_DECOMPOSITION_RATE", "TESTING_ACCESS_SCORE",
            "ACTIVE_TESTING_CENTERS",
        ]].to_sql("compartment_dynamics", connection, index=False)
        decomposition.to_sql("decomposition_results", connection, index=False)
        recommendations.to_sql("testing_center_recommendations", connection, index=False)
        alerts.to_sql("alerts", connection, index=False)
        regional.to_sql("regional_summary", connection, index=False)
        edges.to_sql("adjacency_edges", connection, index=False)
        pd.DataFrame([{"KEY": key, "VALUE": json.dumps(value, ensure_ascii=False, default=str)} for key, value in metadata.items()]).to_sql("metadata", connection, index=False)
        indexes = [
            "CREATE INDEX idx_forecast_period ON forecast_values(PERIOD)",
            "CREATE INDEX idx_forecast_psgc ON forecast_values(PSGC)",
            "CREATE INDEX idx_hotspot_period ON hotspot_results(PERIOD)",
            "CREATE INDEX idx_decomp_location_period ON decomposition_results(LOCATION, PERIOD)",
            "CREATE INDEX idx_alerts_period ON alerts(PERIOD)",
            "CREATE INDEX idx_compartment_location_period ON compartment_dynamics(LOCATION, PERIOD)",
        ]
        for statement in indexes:
            connection.execute(statement)
        connection.commit()


def _save(fig: plt.Figure, path: Path, dpi: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def generate_charts(
    charts_dir: Path,
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    decomposition: pd.DataFrame,
    recommendations: pd.DataFrame,
    regional: pd.DataFrame,
    dpi: int = 220,
) -> list[Path]:
    charts_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    historical_regional = history.groupby("PERIOD", as_index=False)["CASES"].sum()
    fig, ax = plt.subplots(figsize=(13, 5.5))
    ax.plot(pd.to_datetime(historical_regional["PERIOD"]), historical_regional["CASES"], label="Historical development series")
    ax.plot(pd.to_datetime(regional["PERIOD"]), regional["REGIONAL_SCENARIO_CASES"], label="Regional scenario")
    ax.fill_between(pd.to_datetime(regional["PERIOD"]), regional["LOWER_95_SUM"], regional["UPPER_95_SUM"], alpha=0.22, label="Summed 95% scenario interval")
    ax.set_title("Region XII monthly HIV diagnosis scenario")
    ax.set_ylabel("Cases")
    ax.grid(alpha=0.25)
    ax.legend()
    path = charts_dir / "01_regional_historical_and_forecast.png"; _save(fig, path, dpi); outputs.append(path)

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(pd.to_datetime(regional["PERIOD"]), regional["GLOBAL_MORANS_I"])
    ax.axhline(0, linewidth=1)
    ax.set_title("Dynamic global Moran's I of rolling municipality case rates")
    ax.set_ylabel("Moran's I")
    ax.grid(alpha=0.25)
    path = charts_dir / "02_dynamic_global_morans_i.png"; _save(fig, path, dpi); outputs.append(path)

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(pd.to_datetime(regional["PERIOD"]), regional["HOT_SPOT_MUNICIPALITIES"], label="Hot spots")
    ax.plot(pd.to_datetime(regional["PERIOD"]), regional["ACTIVE_ALERTS"], label="Automatic watches")
    ax.plot(pd.to_datetime(regional["PERIOD"]), regional["HIGH_OR_CRITICAL_PRESSURE"], label="High/Critical pressure")
    ax.set_title("Dynamic hotspot and alert counts")
    ax.set_ylabel("Municipalities")
    ax.grid(alpha=0.25)
    ax.legend()
    path = charts_dir / "03_dynamic_hotspot_alert_counts.png"; _save(fig, path, dpi); outputs.append(path)

    latest_period = forecast["PERIOD"].max()
    latest = forecast[forecast["PERIOD"] == latest_period].sort_values("TRANSMISSION_PRESSURE_INDEX", ascending=True).tail(20)
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(latest["LOCATION"], latest["TRANSMISSION_PRESSURE_INDEX"])
    ax.set_title(f"Top municipality transmission-pressure proxy · {latest_period}")
    ax.set_xlabel("Pressure index (0–100)")
    ax.grid(axis="x", alpha=0.25)
    path = charts_dir / "04_transmission_pressure_ranking.png"; _save(fig, path, dpi); outputs.append(path)

    rec = recommendations.sort_values("TESTING_CENTER_NEED_SCORE", ascending=True).tail(20)
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(rec["LOCATION"], rec["TESTING_CENTER_NEED_SCORE"])
    ax.set_title("Testing-center establishment priority")
    ax.set_xlabel("Need score (0–100)")
    ax.grid(axis="x", alpha=0.25)
    path = charts_dir / "05_testing_center_priority.png"; _save(fig, path, dpi); outputs.append(path)

    pivot = forecast.pivot(index="LOCATION", columns="PERIOD", values="PREDICTED_CASES")
    annual_columns = [column for column in pivot.columns if column.endswith("-01")]
    sample = pivot[annual_columns] if annual_columns else pivot.iloc[:, ::12]
    fig, ax = plt.subplots(figsize=(15, 10))
    image = ax.imshow(sample.to_numpy(), aspect="auto", interpolation="nearest")
    ax.set_yticks(np.arange(len(sample.index)))
    ax.set_yticklabels(sample.index, fontsize=7)
    ax.set_xticks(np.arange(len(sample.columns)))
    ax.set_xticklabels([str(value)[:4] for value in sample.columns], rotation=45, ha="right")
    ax.set_title("Municipality forecast heatmap · January snapshots")
    ax.set_xlabel("Year")
    fig.colorbar(image, ax=ax, label="Predicted monthly cases")
    path = charts_dir / "06_municipality_forecast_heatmap.png"; _save(fig, path, dpi); outputs.append(path)

    selected_location = recommendations.iloc[0]["LOCATION"] if not recommendations.empty else forecast.iloc[0]["LOCATION"]
    decomp = decomposition[(decomposition["LOCATION"] == selected_location) & (decomposition["SERIES_STATUS"] == "FORECAST SCENARIO")]
    fig, ax = plt.subplots(figsize=(13, 6))
    dates = pd.to_datetime(decomp["PERIOD"])
    ax.plot(dates, decomp["TREND_COMPONENT"], label="Trend")
    ax.plot(dates, decomp["SEASONAL_COMPONENT"], label="Seasonal")
    ax.plot(dates, decomp["RESIDUAL_COMPONENT"], label="Residual")
    ax.set_title(f"Time-series decomposition · {selected_location}")
    ax.set_ylabel("log(1 + cases) component")
    ax.grid(alpha=0.25)
    ax.legend()
    path = charts_dir / "07_time_series_decomposition_example.png"; _save(fig, path, dpi); outputs.append(path)

    fig, ax = plt.subplots(figsize=(13, 5))
    width = regional["UPPER_95_SUM"] - regional["LOWER_95_SUM"]
    ax.plot(pd.to_datetime(regional["PERIOD"]), width)
    ax.set_title("Regional summed scenario-interval width")
    ax.set_ylabel("Cases")
    ax.grid(alpha=0.25)
    path = charts_dir / "08_uncertainty_width.png"; _save(fig, path, dpi); outputs.append(path)

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(pd.to_datetime(regional["PERIOD"]), regional["TOTAL_POPULATION"] / 1_000_000.0)
    ax.set_title("Region XII simulated monthly population growth")
    ax.set_ylabel("Population (millions)")
    ax.grid(alpha=0.25)
    path = charts_dir / "09_population_growth.png"; _save(fig, path, dpi); outputs.append(path)

    fig, ax = plt.subplots(figsize=(13, 6))
    dates = pd.to_datetime(regional["PERIOD"])
    ax.stackplot(
        dates,
        regional["PLHIV_UNDIAGNOSED"],
        regional["PLHIV_DIAGNOSED_NOT_ON_ART"],
        regional["PLHIV_ON_ART_UNSUPPRESSED"],
        regional["PLHIV_VIRALLY_SUPPRESSED"],
        labels=["Undiagnosed", "Diagnosed, not on ART", "On ART, unsuppressed", "Virally suppressed"],
        alpha=0.82,
    )
    ax.set_title("Regional PLHIV care-cascade compartment simulation")
    ax.set_ylabel("People")
    ax.grid(alpha=0.20)
    ax.legend(loc="upper left")
    path = charts_dir / "10_care_cascade_compartments.png"; _save(fig, path, dpi); outputs.append(path)

    fig, ax = plt.subplots(figsize=(13, 5.5))
    ax.plot(dates, regional["NEW_INFECTIONS_ESTIMATE"], label="Estimated new infections")
    ax.plot(dates, regional["ALLOCATED_MUNICIPAL_CASES"], label="Predicted reported diagnoses")
    ax.plot(dates, regional["NEW_ART_ENROLLMENTS"], label="ART enrollments")
    ax.plot(dates, regional["NEWLY_VIRALLY_SUPPRESSED"], label="Newly virally suppressed")
    ax.set_title("Monthly transmission, diagnosis, treatment, and suppression flows")
    ax.set_ylabel("People per month")
    ax.grid(alpha=0.25)
    ax.legend()
    path = charts_dir / "11_transmission_and_treatment_flows.png"; _save(fig, path, dpi); outputs.append(path)

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(dates, regional["TOTAL_PLHIV"], label="Total PLHIV")
    ax.plot(dates, regional["EFFECTIVE_INFECTIOUS_POOL"], label="Effective transmission-active pool")
    ax.set_title("Treatment-driven decomposition of the effective infectious pool")
    ax.set_ylabel("People-equivalent")
    ax.grid(alpha=0.25)
    ax.legend()
    path = charts_dir / "12_effective_infectious_pool_decomposition.png"; _save(fig, path, dpi); outputs.append(path)

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(dates, regional["ACTIVE_TESTING_CENTERS"], label="Active centers")
    ax.plot(dates, regional["PENDING_TESTING_CENTERS"], label="Pending centers")
    ax.set_title("Dynamic HIV testing-center establishment scenario")
    ax.set_ylabel("Centers")
    ax.grid(alpha=0.25)
    ax.legend()
    path = charts_dir / "13_testing_center_expansion.png"; _save(fig, path, dpi); outputs.append(path)

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(dates, regional["MEAN_ART_COVERAGE"] * 100.0, label="ART coverage")
    ax.plot(dates, regional["MEAN_VIRAL_SUPPRESSION_COVERAGE"] * 100.0, label="Viral suppression coverage")
    ax.plot(dates, regional["MEAN_TESTING_ACCESS_SCORE"] * 100.0, label="Testing access score")
    ax.set_title("Testing access and treatment coverage")
    ax.set_ylabel("Percent")
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.25)
    ax.legend()
    path = charts_dir / "14_testing_treatment_coverage.png"; _save(fig, path, dpi); outputs.append(path)

    return outputs


def generate_report(
    path: Path,
    metadata: dict[str, Any],
    recommendations: pd.DataFrame,
    alerts: pd.DataFrame,
    charts: list[Path],
) -> None:
    chart_items = "".join(
        f'<figure><img src="charts/{html.escape(item.name)}"><figcaption>{html.escape(item.stem.replace("_", " ").title())}</figcaption></figure>'
        for item in charts
    )
    rec_html = recommendations.head(20).to_html(index=False, border=0, classes="data", float_format=lambda value: f"{value:.3f}")
    alert_html = alerts.head(30).to_html(index=False, border=0, classes="data", float_format=lambda value: f"{value:.3f}") if not alerts.empty else "<p>No alerts generated.</p>"
    report = f'''<!doctype html><html><head><meta charset="utf-8"><title>arcHIVe Training Report</title><style>
body{{font:12pt Arial,sans-serif;max-width:1240px;margin:28px auto;padding:0 22px;color:#172033}}h1,h2{{color:#102a43}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.metric{{border:1px solid #cbd5e1;padding:11px;border-radius:8px}}figure{{margin:22px 0}}img{{max-width:100%;border:1px solid #cbd5e1}}table.data{{border-collapse:collapse;width:100%;font-size:9pt;display:block;overflow:auto}}table.data th,table.data td{{border:1px solid #cbd5e1;padding:5px;text-align:right;white-space:nowrap}}table.data th:first-child,table.data td:first-child{{text-align:left}}code{{background:#eef2f6;padding:2px 4px}}</style></head><body>
<h1>arcHIVe Training Report</h1>
<h2>Run summary</h2><div class="metrics"><div class="metric"><b>Municipalities</b><br>{metadata['municipality_count']}</div><div class="metric"><b>Forecast months</b><br>{metadata['forecast_months']}</div><div class="metric"><b>Phase 1 Hybrid test R²</b><br>{metadata['phase1_hybrid_test_r2']:.6f}</div><div class="metric"><b>Boundary source</b><br>{html.escape(str(metadata.get('boundary_source','')))}</div></div>
<p><b>Forecast period:</b> {metadata['forecast_start']} through {metadata['forecast_end']}<br><b>Simulation:</b> monthly population growth + undiagnosed/diagnosed/ART/suppressed compartments + dynamic centers + spatial neighbor force<br><b>Boundary topology:</b> residual gap ratio {metadata.get('boundary_gap_report',{}).get('residual_uncovered_ratio',0):.3e}; residual overlap ratio {metadata.get('boundary_gap_report',{}).get('residual_overlap_ratio',0):.3e}<br><b>Hybrid:</b> MLR {metadata['hybrid_weights']['mlr']:.2%}, LSTM {metadata['hybrid_weights']['lstm']:.2%}; spatial diffusion {metadata['spatial_diffusion_weight']:.2%}</p>
<p><a href="maps/arcHIVe_Region_XII_Interactive_Forecast_Map.html">Open the interactive Region XII map</a></p>
<h2>Testing-center planning priorities</h2>{rec_html}<h2>Highest-priority alerts</h2>{alert_html}<h2>Generated charts</h2>{chart_items}
<h2>Backend outputs</h2><ul><li><code>database/archive_phase2.sqlite</code></li><li><code>tables/monthly_municipality_forecasts.csv</code></li><li><code>tables/dynamic_hotspot_results.csv</code></li><li><code>tables/time_series_decomposition.csv</code></li><li><code>tables/transmission_pressure.csv</code></li><li><code>tables/transmission_compartment_simulation.csv</code></li><li><code>tables/testing_center_establishment_schedule.csv</code></li><li><code>tables/testing_center_recommendations.csv</code></li><li><code>tables/alerts.csv</code></li><li><code>maps/region12_municipalities_gap_filled.geojson</code></li></ul>
</body></html>'''
    path.write_text(report, encoding="utf-8")
