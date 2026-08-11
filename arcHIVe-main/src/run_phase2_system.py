from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.phase2.boundaries import load_boundaries
from src.phase2.engine import (
    Phase2Predictor,
    build_alerts,
    build_center_recommendations,
    classical_decomposition,
    regional_summary,
)
from src.phase2.map_builder import build_interactive_map
from src.phase2.outputs import generate_charts, generate_report, save_table, write_sqlite
from src.phase2.spatial import build_spatial_weights


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the arcHIVe Phase 2 spatiotemporal GIS system")
    parser.add_argument("--config", type=Path, default=ROOT / "spatiotemporal_config.json")
    parser.add_argument("--forecast-start")
    parser.add_argument("--forecast-end")
    parser.add_argument("--planning-period")
    parser.add_argument("--force-boundary-download", action="store_true")
    parser.add_argument("--test-fixture-boundaries", action="store_true", help="Offline verification only; never operational")
    parser.add_argument("--run-id")
    parser.add_argument("--skip-charts", action="store_true")
    return parser.parse_args()


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    return config


def expected_locations(root: Path) -> tuple[dict[str, str], pd.DataFrame]:
    history = pd.read_csv(
        root / "data" / "arcHIVe_Municipality_Monthly.csv",
        dtype={"PSGC_Code": str},
        encoding="cp1252",
    )
    history = history[(history["Current_Region_XII"] == "Yes") & (history["Model_Eligible"] == "Yes")].copy()
    history["PSGC_Code"] = history["PSGC_Code"].str.replace(r"\.0$", "", regex=True).str.zfill(10)
    latest = history.sort_values(["Location", "Period"]).groupby("Location", as_index=False).tail(1)
    expected = {str(row.PSGC_Code): str(row.Location) for row in latest.itertuples(index=False)}
    if len(expected) != 49:
        raise ValueError(f"Expected 49 current Region XII model locations, found {len(expected)}")
    return expected, history


def municipality_table(boundary_geojson: dict, history: pd.DataFrame) -> pd.DataFrame:
    latest = history.sort_values(["Location", "Period"]).groupby("Location", as_index=False).tail(1)
    data = latest.set_index("Location")
    rows = []
    for feature in boundary_geojson.get("features") or []:
        props = feature.get("properties") or {}
        location = str(props["LOCATION"])
        record = data.loc[location]
        point = shape(feature["geometry"]).representative_point()
        rows.append({
            "PSGC": str(props["PSGC"]),
            "PROVINCE": str(record["Province"]),
            "LOCATION": location,
            "POPULATION_2024": float(record["Total_Population"]),
            "DENSITY_2024": float(record["Population_Density_per_km2"]),
            "ESTIMATED_TESTING_CENTERS_2024": float(record["Active_Testing_Centers"]),
            "AREA_KM2_APPROX": float(props.get("AREA_KM2_APPROX") or 0.0),
            "REPRESENTATIVE_LATITUDE": float(point.y),
            "REPRESENTATIVE_LONGITUDE": float(point.x),
            "BOUNDARY_SOURCE": str(props.get("SOURCE") or ""),
            "CASE_DATA_STATUS": "CONSTRAINED DEVELOPMENT SIMULATION",
        })
    return pd.DataFrame(rows).sort_values(["PROVINCE", "LOCATION"]).reset_index(drop=True)


def validate_outputs(
    forecasts: pd.DataFrame,
    decomposition: pd.DataFrame,
    recommendations: pd.DataFrame,
    alerts: pd.DataFrame,
    regional: pd.DataFrame,
    municipalities: pd.DataFrame,
    gap_report: dict,
) -> dict:
    errors = []
    if municipalities["PSGC"].nunique() != 49:
        errors.append("Municipality table does not contain exactly 49 unique PSGC codes")
    if forecasts.groupby("PERIOD")["PSGC"].nunique().min() != 49:
        errors.append("At least one forecast month is missing municipalities")
    reconciliation = (
        forecasts.groupby("PERIOD")["PREDICTED_CASES"].sum()
        - forecasts.groupby("PERIOD")["REGIONAL_SCENARIO_CASES"].first()
    ).abs()
    max_reconciliation_error = float(reconciliation.max())
    if max_reconciliation_error > 1e-6:
        errors.append(f"Forecast regional reconciliation error is {max_reconciliation_error}")
    numeric_columns = [
        "PREDICTED_CASES", "LOWER_95", "UPPER_95", "ROLLING_12M_RATE_PER_100K",
        "GI_STAR_Z_SCORE", "TRANSMISSION_PRESSURE_INDEX", "TESTING_CENTER_NEED_SCORE",
        "POPULATION", "NEW_INFECTIONS_ESTIMATE", "PLHIV_UNDIAGNOSED",
        "PLHIV_DIAGNOSED_NOT_ON_ART", "PLHIV_ON_ART_UNSUPPRESSED",
        "PLHIV_VIRALLY_SUPPRESSED", "TOTAL_PLHIV", "EFFECTIVE_INFECTIOUS_POOL",
        "TESTING_ACCESS_SCORE", "ART_COVERAGE", "VIRAL_SUPPRESSION_COVERAGE",
        "TREATMENT_DECOMPOSITION_RATE",
    ]
    if not np.isfinite(forecasts[numeric_columns].to_numpy(float)).all():
        errors.append("Forecast table contains non-finite numeric values")
    if (forecasts["PREDICTED_CASES"] < 0).any() or (forecasts["LOWER_95"] < 0).any():
        errors.append("Forecast output contains negative case values")
    nonnegative_columns = [
        "POPULATION", "NEW_INFECTIONS_ESTIMATE", "PLHIV_UNDIAGNOSED",
        "PLHIV_DIAGNOSED_NOT_ON_ART", "PLHIV_ON_ART_UNSUPPRESSED",
        "PLHIV_VIRALLY_SUPPRESSED", "TOTAL_PLHIV", "EFFECTIVE_INFECTIOUS_POOL",
        "ACTIVE_TESTING_CENTERS", "NEW_TESTING_CENTERS_OPENED",
    ]
    if (forecasts[nonnegative_columns] < -1e-9).any().any():
        errors.append("Mechanistic simulation contains negative state values")
    compartment_sum = (
        forecasts["PLHIV_UNDIAGNOSED"]
        + forecasts["PLHIV_DIAGNOSED_NOT_ON_ART"]
        + forecasts["PLHIV_ON_ART_UNSUPPRESSED"]
        + forecasts["PLHIV_VIRALLY_SUPPRESSED"]
    )
    maximum_compartment_balance_error = float((compartment_sum - forecasts["TOTAL_PLHIV"]).abs().max())
    if maximum_compartment_balance_error > 1e-6:
        errors.append(f"Care-cascade compartment balance error is {maximum_compartment_balance_error}")
    for column in ["TESTING_ACCESS_SCORE", "ART_COVERAGE", "VIRAL_SUPPRESSION_COVERAGE"]:
        if ((forecasts[column] < -1e-9) | (forecasts[column] > 1.0 + 1e-9)).any():
            errors.append(f"{column} is outside the 0-1 range")
    population_change = forecasts.sort_values(["LOCATION", "PERIOD"]).groupby("LOCATION")["POPULATION"].pct_change().dropna()
    if (population_change.abs() > 0.005).any():
        errors.append("Monthly population change exceeds the configured realism bound")
    center_diff = forecasts.sort_values(["LOCATION", "PERIOD"]).groupby("LOCATION")["ACTIVE_TESTING_CENTERS"].diff().dropna()
    if (center_diff < -1e-9).any():
        errors.append("Testing-center count decreased during the establishment scenario")
    if decomposition.empty or decomposition["LOCATION"].nunique() != 49:
        errors.append("Decomposition output is incomplete")
    if recommendations["PSGC"].nunique() != 49:
        errors.append("Testing-center recommendations are incomplete")
    if float(gap_report.get("residual_uncovered_ratio", 1.0)) > 1e-9:
        errors.append("Boundary partition retains an internal uncovered gap")
    if float(gap_report.get("residual_overlap_ratio", 1.0)) > 1e-9:
        errors.append("Boundary partition retains an overlap")
    if errors:
        raise RuntimeError("Phase 2 validation failed:\n- " + "\n- ".join(errors))
    return {
        "status": "PASS",
        "municipalities": int(municipalities["PSGC"].nunique()),
        "forecast_rows": int(len(forecasts)),
        "forecast_months": int(forecasts["PERIOD"].nunique()),
        "decomposition_rows": int(len(decomposition)),
        "recommendation_rows": int(len(recommendations)),
        "alert_rows": int(len(alerts)),
        "max_regional_reconciliation_error": max_reconciliation_error,
        "boundary_residual_gap_ratio": float(gap_report.get("residual_uncovered_ratio", 0.0)),
        "boundary_residual_overlap_ratio": float(gap_report.get("residual_overlap_ratio", 0.0)),
        "regional_rows": int(len(regional)),
        "new_testing_centers_opened": int(forecasts["NEW_TESTING_CENTERS_OPENED"].sum()),
        "maximum_compartment_balance_error": maximum_compartment_balance_error,
        "maximum_monthly_population_change": float(population_change.abs().max()) if len(population_change) else 0.0,
        "minimum_testing_access_score": float(forecasts["TESTING_ACCESS_SCORE"].min()),
        "maximum_testing_access_score": float(forecasts["TESTING_ACCESS_SCORE"].max()),
        "final_regional_art_coverage": float(regional.iloc[-1]["MEAN_ART_COVERAGE"]),
        "final_regional_viral_suppression_coverage": float(regional.iloc[-1]["MEAN_VIRAL_SUPPRESSION_COVERAGE"]),
    }


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    start = args.forecast_start or config["projection"]["forecast_start"]
    end = args.forecast_end or config["projection"]["forecast_end"]
    planning_period = args.planning_period or config["testing_center_planning"]["planning_period"]
    if not (start <= planning_period <= end):
        planning_period = end
    run_id = args.run_id or (
        ("test_fixture_run_" if args.test_fixture_boundaries else "phase2_run_")
        + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    run_dir = ROOT / "outputs" / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    for subdir in ["tables", "charts", "maps", "database", "logs"]:
        (run_dir / subdir).mkdir(parents=True, exist_ok=True)

    expected, history = expected_locations(ROOT)
    boundary_cfg = config["boundaries"]
    cache_path = ROOT / boundary_cfg["cache_geojson"]
    metadata_path = ROOT / boundary_cfg["cache_metadata"]
    boundary = load_boundaries(
        expected,
        cache_path,
        metadata_path,
        force_download=args.force_boundary_download or bool(boundary_cfg.get("force_download")),
        use_test_fixture=args.test_fixture_boundaries,
        timeout=int(boundary_cfg.get("request_timeout_seconds", 90)),
        gap_tolerance_degrees=float(boundary_cfg.get("gap_fill_tolerance_degrees", 0.0015)),
    )

    latest_by_code = history.sort_values(["Location", "Period"]).groupby("Location", as_index=False).tail(1).copy()
    latest_by_code["PSGC_Code"] = latest_by_code["PSGC_Code"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    province_lookup = {str(row.PSGC_Code): str(row.Province) for row in latest_by_code.itertuples(index=False)}
    province_code_lookup = {
        "12047": "1204700000", "12063": "1206300000", "12065": "1206500000",
        "12080": "1208000000", "12308": "1230800000",
    }
    for feature in boundary.geojson.get("features") or []:
        props = feature.setdefault("properties", {})
        code = str(props.get("PSGC") or feature.get("id")).zfill(10)
        props["LOCATION"] = expected[code]
        props["PROVINCE"] = province_lookup[code]
        props["PROVINCE_PSGC"] = province_code_lookup.get(code[:5], props.get("PROVINCE_PSGC", ""))

    from src.phase2.boundaries import dissolve_provinces, region_feature, outside_mask
    boundary = type(boundary)(
        geojson=boundary.geojson,
        province_geojson=dissolve_provinces(boundary.geojson),
        region_geojson=region_feature(shape(boundary.region_geojson["features"][0]["geometry"])),
        outside_mask=outside_mask(shape(boundary.region_geojson["features"][0]["geometry"])),
        gap_report=boundary.gap_report, source=boundary.source, cache_path=boundary.cache_path,
    )

    spatial_cfg = config["spatial"]
    spatial = build_spatial_weights(
        boundary.geojson,
        tolerance_degrees=float(spatial_cfg.get("boundary_tolerance_degrees", 0.00008)),
        minimum_neighbors=int(spatial_cfg.get("minimum_neighbors", 2)),
        fallback_max_distance_km=float(spatial_cfg.get("fallback_max_distance_km", 60.0)),
    )

    predictor = Phase2Predictor(ROOT, spatial, config)
    forecasts, metadata = predictor.forecast(start, end)
    decomposition = classical_decomposition(predictor.history, forecasts, predictor.location_order)
    recommendations = build_center_recommendations(
        forecasts, boundary.geojson, planning_period=planning_period
    )
    alerts = build_alerts(forecasts, recommendations)
    regional = regional_summary(forecasts)
    municipalities = municipality_table(boundary.geojson, history)
    edges = pd.DataFrame(spatial.edges)

    metadata.update({
        "run_id": run_id,
        "project_name": config["project_name"],
        "boundary_source": boundary.source,
        "boundary_cache": str(boundary.cache_path.relative_to(ROOT)) if boundary.cache_path.is_relative_to(ROOT) else str(boundary.cache_path),
        "boundary_gap_report": boundary.gap_report,
        "testing_center_planning_period": planning_period,
        "configuration": config,
        "python_version": sys.version,
        "operational_boundaries": not args.test_fixture_boundaries,
    })


    save_table(forecasts, run_dir / "tables" / "monthly_municipality_forecasts.csv")
    save_table(forecasts[[
        "PERIOD", "PSGC", "PROVINCE", "LOCATION", "GLOBAL_MORANS_I", "LOCAL_MORANS_I",
        "LOCAL_MORAN_CLUSTER", "GI_STAR_Z_SCORE", "GI_STAR_P_VALUE", "HOTSPOT_CLASS",
        "HOTSPOT_CLUSTER_ID", "HOTSPOT_CLUSTER_SIZE", "AUTOMATIC_ALERT", "ALERT_REASON",
    ]], run_dir / "tables" / "dynamic_hotspot_results.csv")
    transmission_columns = [
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
    ]
    save_table(forecasts[transmission_columns], run_dir / "tables" / "transmission_pressure.csv")
    compartment_columns = [
        "PERIOD", "PSGC", "PROVINCE", "LOCATION", "POPULATION",
        "PLHIV_UNDIAGNOSED", "PLHIV_DIAGNOSED_NOT_ON_ART",
        "PLHIV_ON_ART_UNSUPPRESSED", "PLHIV_VIRALLY_SUPPRESSED", "TOTAL_PLHIV",
        "EFFECTIVE_INFECTIOUS_POOL", "NEW_INFECTIONS_ESTIMATE", "PREDICTED_CASES",
        "NEW_ART_ENROLLMENTS", "NEWLY_VIRALLY_SUPPRESSED",
        "TREATMENT_INTERRUPTION", "PLHIV_ATTRITION", "ART_COVERAGE",
        "VIRAL_SUPPRESSION_COVERAGE", "INFECTIOUS_POOL_REDUCTION_FROM_TREATMENT",
        "TREATMENT_DECOMPOSITION_RATE", "TESTING_ACCESS_SCORE",
        "ACTIVE_TESTING_CENTERS",
    ]
    save_table(forecasts[compartment_columns], run_dir / "tables" / "transmission_compartment_simulation.csv")
    center_schedule = forecasts[(forecasts["NEW_TESTING_CENTERS_OPENED"] > 0) | (forecasts["CENTER_ESTABLISHMENT_SCHEDULED_FOR"].astype(str).str.len() > 0)][[
        "PERIOD", "PSGC", "PROVINCE", "LOCATION", "ACTIVE_TESTING_CENTERS",
        "NEW_TESTING_CENTERS_OPENED", "PENDING_TESTING_CENTERS",
        "CENTER_ESTABLISHMENT_SCHEDULED_FOR", "PROVISIONAL_CENTER_NEED_SCORE",
        "TESTING_CENTER_NEED_SCORE", "TESTING_ACCESS_SCORE",
    ]]
    save_table(center_schedule, run_dir / "tables" / "testing_center_establishment_schedule.csv")
    save_table(decomposition, run_dir / "tables" / "time_series_decomposition.csv")
    save_table(recommendations, run_dir / "tables" / "testing_center_recommendations.csv")
    save_table(alerts, run_dir / "tables" / "alerts.csv")
    save_table(regional, run_dir / "tables" / "regional_monthly_summary.csv")
    save_table(municipalities, run_dir / "tables" / "municipalities.csv")
    save_table(edges, run_dir / "tables" / "spatial_adjacency_edges.csv")

    (run_dir / "maps" / "region12_municipalities_gap_filled.geojson").write_text(
        json.dumps(boundary.geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (run_dir / "maps" / "region12_provinces.geojson").write_text(
        json.dumps(boundary.province_geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (run_dir / "maps" / "region12_boundary.geojson").write_text(
        json.dumps(boundary.region_geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    write_sqlite(
        run_dir / "database" / "archive_phase2.sqlite",
        municipalities, forecasts, decomposition, recommendations, alerts, regional, edges, metadata,
    )
    build_interactive_map(
        run_dir / "maps" / "arcHIVe_Region_XII_Interactive_Forecast_Map.html",
        boundary.geojson, boundary.province_geojson, boundary.region_geojson, boundary.outside_mask,
        forecasts, decomposition, recommendations, regional, metadata,
        playback_interval_ms=int(config["interface"].get("playback_interval_ms", 2600)),
    )

    charts = []
    if not args.skip_charts:
        charts = generate_charts(
            run_dir / "charts", predictor.history, forecasts, decomposition, recommendations, regional,
            dpi=int(config["outputs"].get("plot_dpi", 220)),
        )
    generate_report(
        run_dir / "arcHIVe_Phase2_SpatioTemporal_GIS_Report.html",
        metadata, recommendations, alerts, charts,
    )

    verification = validate_outputs(
        forecasts, decomposition, recommendations, alerts, regional, municipalities, boundary.gap_report
    )
    (run_dir / "VERIFICATION_SUMMARY.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    (run_dir / "PHASE2_SYSTEM_SUCCESS.txt").write_text(
        "arcHIVe Phase 2 completed successfully.\n"
        f"Run: {run_id}\nForecast period: {start} to {end}\n"
        f"Municipalities: 49\nForecast rows: {len(forecasts)}\n"
        f"Phase 1 Hybrid chronological test R-squared: {metadata['phase1_hybrid_test_r2']:.6f}\n"
        f"New testing centers opened in scenario: {verification['new_testing_centers_opened']}\n"
        f"Final mean ART coverage: {verification['final_regional_art_coverage']:.3%}\n"
        f"Final mean viral suppression coverage: {verification['final_regional_viral_suppression_coverage']:.3%}\n"
        "Scientific scope: municipality-time training targets are constrained development simulations.\n",
        encoding="utf-8",
    )
    pointer = ROOT / "outputs" / "latest_phase2_run.txt"
    pointer.write_text(str(run_dir.relative_to(ROOT)), encoding="utf-8")
    print(json.dumps(verification, indent=2))
    print(f"Phase 2 run saved to: {run_dir}")
    print(f"Interactive map: {run_dir / 'maps' / 'arcHIVe_Region_XII_Interactive_Forecast_Map.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
