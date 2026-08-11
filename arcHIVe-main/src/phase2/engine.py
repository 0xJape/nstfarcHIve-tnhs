from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch
from shapely.geometry import shape

from src.model_runtime import MunicipalityLSTM
from src.phase2.spatial import (
    SpatialWeights,
    connected_components,
    getis_ord_gi_star,
    global_morans_i,
    hotspot_class,
    local_moran_clusters,
)


@dataclass(frozen=True)
class Phase2Outputs:
    monthly: pd.DataFrame
    decomposition: pd.DataFrame
    center_recommendations: pd.DataFrame
    alerts: pd.DataFrame
    regional_summary: pd.DataFrame
    metadata: dict[str, Any]


def add_month(period: str, months: int = 1) -> str:
    year, month = (int(part) for part in period[:7].split("-"))
    index = year * 12 + month - 1 + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_range(start: str, end: str) -> list[str]:
    result = []
    current = start[:7]
    while current <= end[:7]:
        result.append(current)
        current = add_month(current)
    return result


def robust_scale(values: np.ndarray, low: float = 0.10, high: float = 0.90) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if not len(finite):
        return np.zeros_like(values)
    lo, hi = np.quantile(finite, [low, high])
    if hi <= lo + 1e-12:
        return np.zeros_like(values)
    return np.clip((values - lo) / (hi - lo), 0.0, 1.0)


def classify_pressure(score: float) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 45:
        return "MODERATE"
    return "LOW"


class Phase2Predictor:
    def __init__(self, root: Path, spatial: SpatialWeights, config: dict[str, Any]) -> None:
        self.root = root
        self.spatial = spatial
        self.config = config
        self.bundle = json.loads((root / "models" / "model_bundle.json").read_text(encoding="utf-8"))
        self.mlr = joblib.load(root / "models" / "mlr_pipeline.joblib")
        architecture = self.bundle["lstm_architecture"]
        self.lstm = MunicipalityLSTM(
            sequence_features=int(architecture["sequence_features"]),
            current_features=int(architecture["current_features"]),
            location_count=len(self.bundle["locations"]),
            hidden_size=int(architecture["hidden_size"]),
            embedding_size=int(architecture["embedding_size"]),
        )
        state_path = root / "models" / "lstm_state.pt"
        try:
            state = torch.load(state_path, map_location="cpu", weights_only=True)
        except TypeError:
            state = torch.load(state_path, map_location="cpu")
        self.lstm.load_state_dict(state)
        self.lstm.eval()
        self.history = self._load_history()
        self.profile = self._load_profile()
        self.location_metadata = self._location_metadata()
        self.location_order = list(self.spatial.names)
        if set(self.location_order) != set(self.bundle["locations"]):
            missing = sorted(set(self.bundle["locations"]) - set(self.location_order))
            extra = sorted(set(self.location_order) - set(self.bundle["locations"]))
            raise ValueError(f"Boundary/model location mismatch. Missing={missing}; extra={extra}")

    def _load_history(self) -> pd.DataFrame:
        frame = pd.read_csv(
            self.root / "data" / "arcHIVe_Municipality_Monthly.csv",
            encoding="cp1252",
        )
        frame = frame[(frame["Current_Region_XII"] == "Yes") & (frame["Model_Eligible"] == "Yes")].copy()
        frame["PERIOD"] = pd.to_datetime(
            frame["Period"],
            format="mixed",
            dayfirst=False,
            errors="raise",
        ).dt.strftime("%Y-%m")
        frame = frame.rename(columns={
            "Year": "YEAR", "Month": "MONTH", "PSGC_Code": "PSGC", "Province": "PROVINCE",
            "Location": "LOCATION", "Reported_HIV_Cases": "CASES", "Total_Population": "POPULATION",
            "Population_Density_per_km2": "DENSITY", "Active_Testing_Centers": "CENTERS",
            "Case_Data_Status": "CASE_DATA_STATUS",
        })
        for column in ["YEAR", "MONTH", "CASES", "POPULATION", "DENSITY", "CENTERS"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
        return frame[["PERIOD", "YEAR", "MONTH", "PSGC", "PROVINCE", "LOCATION", "CASES", "POPULATION", "DENSITY", "CENTERS", "CASE_DATA_STATUS"]].sort_values(["LOCATION", "PERIOD"]).reset_index(drop=True)

    def _load_profile(self) -> dict[tuple[str, int], float]:
        pointer = self.root / "outputs" / "latest_training_run.txt"
        profile_path: Path | None = None
        if pointer.exists():
            raw = pointer.read_text(encoding="utf-8", errors="ignore").strip().strip('"')
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = self.root / candidate
            possible = candidate / "tables" / "historical_monthly_location_profiles.csv"
            if possible.exists():
                profile_path = possible
        profile: dict[tuple[str, int], float] = {}
        if profile_path:
            with profile_path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    profile[(row["location"], int(row["month"]))] = float(row["historical_share"])
        else:
            recent = self.history[(self.history["YEAR"] >= 2018) & (self.history["YEAR"] <= 2022)].copy()
            totals = recent.groupby(["YEAR", "MONTH"])["CASES"].transform("sum").replace(0, np.nan)
            recent["SHARE"] = (recent["CASES"] / totals).fillna(0.0)
            grouped = recent.groupby(["LOCATION", "MONTH"])["SHARE"].mean()
            profile = {(location, int(month)): float(value) for (location, month), value in grouped.items()}
        for month in range(1, 13):
            total = sum(profile.get((location, month), 0.0) for location in self.bundle["locations"])
            if total > 0:
                for location in self.bundle["locations"]:
                    profile[(location, month)] = profile.get((location, month), 0.0) / total
            else:
                for location in self.bundle["locations"]:
                    profile[(location, month)] = 1.0 / len(self.bundle["locations"])
        return profile

    def _location_metadata(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for location, group in self.history.groupby("LOCATION"):
            last = group.iloc[-1]
            result[str(location)] = {
                "PSGC": str(last["PSGC"]),
                "PROVINCE": str(last["PROVINCE"]),
                "POPULATION_2024": float(last["POPULATION"]),
                "DENSITY_2024": float(last["DENSITY"]),
                "CENTERS_2024": float(last["CENTERS"]),
            }
        return result

    def regional_scenario(self, period: str) -> float:
        model = self.bundle["regional_model"]
        year, month = (int(part) for part in period.split("-"))
        base_year = int(model["base_year"])
        base_total = float(model["base_annual_total"])
        initial_growth = float(model["annual_growth_rate"])
        cfg = self.config["projection"]
        growth_cap = float(cfg.get("annual_growth_cap", 0.12))
        long_term_growth = float(cfg.get("long_term_growth", 0.03))
        damping_years = max(float(cfg.get("regional_growth_damping_years", 8.0)), 0.5)
        annual_total = base_total
        if year >= base_year:
            for step_year in range(base_year + 1, year + 1):
                age = step_year - base_year
                effective = long_term_growth + (min(initial_growth, growth_cap) - long_term_growth) * math.exp(-age / damping_years)
                annual_total *= 1.0 + effective
        else:
            annual_total /= (1.0 + min(initial_growth, growth_cap)) ** (base_year - year)
        share = float(model["month_shares"][month - 1])
        return max(0.0, annual_total * share)

    def _estimate_annual_population_growth(self, rows: list[dict[str, Any]]) -> float:
        """Estimate a stable municipality CAGR from the historical population panel."""
        cfg = self.config.get("population_simulation", {})
        minimum = float(cfg.get("minimum_annual_growth", 0.001))
        maximum = float(cfg.get("maximum_annual_growth", 0.025))
        anchor = float(cfg.get("official_regional_annual_growth_anchor", 0.0055))
        usable = [row for row in rows if float(row.get("population", 0.0)) > 0]
        if len(usable) < 13:
            return anchor
        window = usable[-min(len(usable), 61):]
        years = max((len(window) - 1) / 12.0, 1.0)
        first = float(window[0]["population"])
        last = float(window[-1]["population"])
        if first <= 0 or last <= 0:
            return anchor
        cagr = (last / first) ** (1.0 / years) - 1.0

                                                                                    
        blended = 0.65 * cagr + 0.35 * anchor
        return float(np.clip(blended, minimum, maximum))

    def _initialize_compartment_state(
        self,
        by_location: dict[str, list[dict[str, Any]]],
    ) -> dict[str, dict[str, Any]]:
        """Allocate a regional HIV care cascade to municipalities for simulation."""
        cfg = self.config.get("transmission_simulation", {})
        total_plhiv = float(cfg.get("regional_plhiv_2025", 7700.0))
        diagnosed_fraction = float(cfg.get("diagnosed_fraction", 0.54))
        art_fraction = float(cfg.get("art_fraction_of_diagnosed", 0.71))
        suppressed_fraction = float(cfg.get("suppressed_fraction_of_art", 0.25))

        populations = np.asarray([
            float(by_location[location][-1]["population"]) for location in self.location_order
        ], dtype=float)
        densities = np.asarray([
            float(by_location[location][-1]["density"]) for location in self.location_order
        ], dtype=float)
        recent = np.asarray([
            sum(float(row["cases"]) for row in by_location[location][-24:])
            for location in self.location_order
        ], dtype=float)
        pop_share = populations / max(populations.sum(), 1.0)
        burden_share = (recent + 0.25) / max((recent + 0.25).sum(), 1.0)
        density_score = robust_scale(densities, 0.05, 0.95)
        density_share = (density_score + 0.15) / max((density_score + 0.15).sum(), 1.0)
        weights = 0.55 * burden_share + 0.30 * pop_share + 0.15 * density_share
        weights = weights / max(weights.sum(), 1e-12)

        infection_ratio = float(cfg.get("infection_to_diagnosis_ratio_at_calibration", 1.15))
        states: dict[str, dict[str, Any]] = {}
        for index, location in enumerate(self.location_order):
            local_plhiv = max(1.0, total_plhiv * float(weights[index]))
            diagnosed = local_plhiv * diagnosed_fraction
            on_art = diagnosed * art_fraction
            suppressed = on_art * suppressed_fraction
            art_unsuppressed = max(0.0, on_art - suppressed)
            diagnosed_no_art = max(0.0, diagnosed - on_art)
            undiagnosed = max(0.0, local_plhiv - diagnosed)
            latest_cases = [float(row["cases"]) for row in by_location[location][-3:]]
            recent_infections = [max(0.0, value * infection_ratio) for value in latest_cases]
            states[location] = {
                "undiagnosed": undiagnosed,
                "diagnosed_no_art": diagnosed_no_art,
                "art_unsuppressed": art_unsuppressed,
                "suppressed": suppressed,
                "recent_infections": recent_infections,
                "base_annual_population_growth": self._estimate_annual_population_growth(by_location[location]),
                "center_need_streak": 0,
                "last_center_schedule_horizon": -10_000,
                "pending_center_openings": [],
                "total_new_centers": 0,
            }
        return states

    def _population_step(
        self,
        population: float,
        base_annual_growth: float,
        density_score: float,
        year: int,
        month: int,
        horizon_index: int,
    ) -> tuple[float, float, float, float]:
        """Compound natural increase and deterministic net migration each month."""
        cfg = self.config.get("population_simulation", {})
        long_term = float(cfg.get("long_term_annual_growth", 0.0055))
        damping_years = max(float(cfg.get("growth_damping_years", 15.0)), 0.5)
        years_forward = max((horizon_index - 1) / 12.0, 0.0)
        annual_rate = long_term + (base_annual_growth - long_term) * math.exp(-years_forward / damping_years)
        natural_share = float(cfg.get("natural_increase_share", 0.72))
        minimum_natural = float(cfg.get("minimum_natural_increase_annual", 0.0015))
        natural_annual = max(minimum_natural, annual_rate * natural_share)

        migration_pull = float(cfg.get("urban_migration_pull_annual", 0.004))
        migration_damping = max(float(cfg.get("migration_damping_years", 12.0)), 0.5)

                                                                                      
        urban_pull = (density_score - 0.50) * 2.0 * migration_pull * math.exp(-years_forward / migration_damping)
        migration_annual = annual_rate - natural_annual + urban_pull
        amplitude = float(cfg.get("migration_seasonality_amplitude", 0.18))
        peak_month = int(cfg.get("migration_peak_month", 6))
        seasonal = 1.0 + amplitude * math.cos(2.0 * math.pi * (month - peak_month) / 12.0)

        natural_change = population * ((1.0 + natural_annual) ** (1.0 / 12.0) - 1.0)
        migration_change = population * migration_annual / 12.0 * seasonal
        maximum_monthly_change = float(cfg.get("maximum_monthly_population_change", 0.0045))
        total_change = float(np.clip(
            natural_change + migration_change,
            -population * maximum_monthly_change,
            population * maximum_monthly_change,
        ))

        uncapped = natural_change + migration_change
        if abs(uncapped) > 1e-12:
            factor = total_change / uncapped
            natural_change *= factor
            migration_change *= factor
        new_population = max(1.0, population + natural_change + migration_change)
        monthly_rate = new_population / max(population, 1.0) - 1.0
        return float(new_population), float(natural_change), float(migration_change), float(monthly_rate)

    def forecast(self, start_period: str, end_period: str) -> tuple[pd.DataFrame, dict[str, Any]]:
        periods = month_range(start_period, end_period)
        by_location: dict[str, list[dict[str, Any]]] = defaultdict(list)
        regional_history: dict[tuple[int, int], float] = defaultdict(float)
        for row in self.history.itertuples(index=False):
            record = {
                "period": row.PERIOD, "year": int(row.YEAR), "month": int(row.MONTH),
                "cases": float(row.CASES), "population": float(row.POPULATION),
                "density": float(row.DENSITY), "centers": float(row.CENTERS),
            }
            by_location[str(row.LOCATION)].append(record)
            regional_history[(int(row.YEAR), int(row.MONTH))] += float(row.CASES)
        for rows in by_location.values():
            rows.sort(key=lambda item: item["period"])

        scale = self.bundle["scaling"]
        spatial_cfg = self.config.get("spatial", {})
        transmission_cfg = self.config.get("transmission_simulation", {})
        center_cfg = self.config.get("testing_center_dynamics", {})
        output_diffusion = float(spatial_cfg.get("diffusion_weight", 0.12))
        temporal_memory = float(spatial_cfg.get("temporal_memory_weight", 0.12))
        rmse = float(self.bundle["metrics"]["Hybrid"]["test"]["rmse"])
        output_rows: list[dict[str, Any]] = []
        previous_prediction = np.zeros(len(self.location_order), dtype=float)
        dynamic_regional_ratio = 1.0
        infection_calibration: float | None = None
        diagnosis_calibration: float | None = None

        states = self._initialize_compartment_state(by_location)
        initial_densities = np.asarray([
            float(by_location[location][-1]["density"]) for location in self.location_order
        ], dtype=float)
        density_scores = robust_scale(initial_densities, 0.05, 0.95)
        initial_centers = {
            location: int(round(float(by_location[location][-1]["centers"])))
            for location in self.location_order
        }

        capacity_per_center = float(center_cfg.get("capacity_population_per_center", 140000.0))
        neighbor_access_weight = float(center_cfg.get("neighbor_access_weight", 0.20))
        auto_centers = bool(center_cfg.get("auto_establish_enabled", True))
        trigger_score = float(center_cfg.get("trigger_score", 70.0))
        sustained_months = int(center_cfg.get("sustained_months", 6))
        construction_lead = int(center_cfg.get("construction_lead_months", 9))
        cooldown_months = int(center_cfg.get("cooldown_months", 18))
        max_new_centers = int(center_cfg.get("max_new_centers_per_municipality", 4))
        maximum_total_centers = int(center_cfg.get("maximum_total_centers", 8))

        mechanistic_weight = float(transmission_cfg.get("mechanistic_blend_weight", 0.65))
        ratio_adaptation = float(transmission_cfg.get("dynamic_regional_ratio_adaptation", 0.20))
        minimum_ratio = float(transmission_cfg.get("dynamic_regional_ratio_min", 0.45))
        maximum_ratio = float(transmission_cfg.get("dynamic_regional_ratio_max", 1.55))

        for horizon_index, period in enumerate(periods, start=1):
            year, month = (int(part) for part in period.split("-"))
            base_regional_cases = self.regional_scenario(period)
            model_regional_cases = base_regional_cases * dynamic_regional_ratio

            populations = np.zeros(len(self.location_order), dtype=float)
            densities = np.zeros(len(self.location_order), dtype=float)
            centers = np.zeros(len(self.location_order), dtype=float)
            natural_changes = np.zeros(len(self.location_order), dtype=float)
            migration_changes = np.zeros(len(self.location_order), dtype=float)
            monthly_population_rates = np.zeros(len(self.location_order), dtype=float)
            opened_centers = np.zeros(len(self.location_order), dtype=float)


            for index, location in enumerate(self.location_order):
                state = states[location]
                due = [value for value in state["pending_center_openings"] if value <= horizon_index]
                state["pending_center_openings"] = [
                    value for value in state["pending_center_openings"] if value > horizon_index
                ]
                opened = len(due)
                opened_centers[index] = opened
                previous_center_count = int(round(float(by_location[location][-1]["centers"])))
                active_centers = min(maximum_total_centers, previous_center_count + opened)
                centers[index] = float(active_centers)

                last = by_location[location][-1]
                population, natural, migration, monthly_rate = self._population_step(
                    float(last["population"]),
                    float(state["base_annual_population_growth"]),
                    float(density_scores[index]),
                    year,
                    month,
                    horizon_index,
                )
                populations[index] = population
                natural_changes[index] = natural
                migration_changes[index] = migration
                monthly_population_rates[index] = monthly_rate
                densities[index] = float(last["density"] * population / max(float(last["population"]), 1.0))


                                                                        
            compartment_totals_before_migration = np.asarray([
                states[location]["undiagnosed"] + states[location]["diagnosed_no_art"]
                + states[location]["art_unsuppressed"] + states[location]["suppressed"]
                for location in self.location_order
            ], dtype=float)
            regional_prevalence = float(compartment_totals_before_migration.sum() / max(populations.sum(), 1.0))
            plhiv_net_migration = np.zeros(len(self.location_order), dtype=float)
            import_multiplier = float(transmission_cfg.get("plhiv_migration_prevalence_multiplier", 1.0))
            for index, location in enumerate(self.location_order):
                migration = migration_changes[index]
                state = states[location]
                if migration >= 0:
                    imported = migration * regional_prevalence * import_multiplier
                    state["undiagnosed"] += imported
                    plhiv_net_migration[index] = imported
                else:
                    out_fraction = min(0.05, -migration / max(populations[index] - migration, 1.0))
                    removed = 0.0
                    for field in ["undiagnosed", "diagnosed_no_art", "art_unsuppressed", "suppressed"]:
                        amount = state[field] * out_fraction
                        state[field] -= amount
                        removed += amount
                    plhiv_net_migration[index] = -removed

            direct_capacity_ratio = centers * capacity_per_center / np.maximum(populations, 1.0)
            direct_access = 1.0 - np.exp(-direct_capacity_ratio)
            neighbor_capacity_ratio = np.asarray(self.spatial.matrix @ direct_capacity_ratio).reshape(-1)
            neighbor_access = 1.0 - np.exp(-neighbor_capacity_ratio)
            testing_access = np.clip(
                (1.0 - neighbor_access_weight) * direct_access + neighbor_access_weight * neighbor_access,
                0.0,
                1.0,
            )


            model_rows: list[list[Any]] = []
            sequences: list[list[list[float]]] = []
            currents: list[list[float]] = []
            ids: list[int] = []
            metadata: list[dict[str, Any]] = []
            for index, location in enumerate(self.location_order):
                rows = by_location[location]
                lookback = int(self.bundle["lookback_months"])
                past = rows[-lookback:]
                if len(past) < lookback:
                    raise RuntimeError(f"Insufficient lookback for {location}")
                past_cases = [float(item["cases"]) for item in past]
                share = float(self.profile.get((location, month), 0.0))
                record = {
                    "regional_cases": model_regional_cases,
                    "historical_share": share,
                    "profile_expected_cases": model_regional_cases * share,
                    "population": populations[index],
                    "density": densities[index],
                    "centers": centers[index],
                    "year": year,
                    "month_sin": math.sin(2 * math.pi * month / 12),
                    "month_cos": math.cos(2 * math.pi * month / 12),
                    "time_index": (year - 1998) * 12 + month - 1,
                    "lag1": past_cases[-1], "lag2": past_cases[-2], "lag3": past_cases[-3],
                    "lag6": past_cases[-6], "lag12": past_cases[0],
                    "rolling3": float(np.mean(past_cases[-3:])),
                    "rolling6": float(np.mean(past_cases[-6:])),
                    "rolling12": float(np.mean(past_cases)),
                    "std12": float(np.std(past_cases)),
                }
                model_rows.append([location] + [record[name] for name in self.bundle["numeric_features"]])
                sequence = []
                for item in past:
                    sequence.append([
                        item["cases"] / scale["max_case"],
                        regional_history[(item["year"], item["month"])] / scale["max_regional"],
                        self.profile.get((location, item["month"]), 0.0),
                        math.sin(2 * math.pi * item["month"] / 12),
                        math.cos(2 * math.pi * item["month"] / 12),
                        item["population"] / scale["max_population"],
                        item["centers"] / scale["max_centers"],
                    ])
                sequences.append(sequence)
                currents.append([
                    model_regional_cases / scale["max_regional"], share,
                    model_regional_cases * share / scale["max_case"],
                    populations[index] / scale["max_population"], densities[index] / scale["max_density"],
                    centers[index] / scale["max_centers"], record["month_sin"], record["month_cos"],
                    record["time_index"] / scale["max_time"],
                    record["lag1"] / scale["max_case"], record["rolling12"] / scale["max_case"],
                ])
                ids.append(int(self.bundle["location_to_id"][location]))
                metadata.append({
                    "PSGC": self.location_metadata[location]["PSGC"],
                    "PROVINCE": self.location_metadata[location]["PROVINCE"],
                    "LOCATION": location,
                    "HISTORICAL_SHARE": share,
                })

            mlr_prediction = np.maximum(0.0, self.mlr.predict(np.asarray(model_rows, dtype=object)))
            with torch.no_grad():
                lstm_prediction = self.lstm(
                    torch.tensor(np.asarray(sequences, dtype=np.float32)),
                    torch.tensor(np.asarray(currents, dtype=np.float32)),
                    torch.tensor(np.asarray(ids, dtype=np.int64)),
                ).cpu().numpy()
            base_hybrid = (
                float(self.bundle["hybrid_mlr_weight"]) * mlr_prediction
                + float(self.bundle["hybrid_lstm_weight"]) * lstm_prediction
            )
            base_hybrid = np.maximum(base_hybrid, 0.0)
            if base_hybrid.sum() <= 0:
                base_hybrid = np.asarray([self.profile[(location, month)] for location in self.location_order])
            base_hybrid *= model_regional_cases / max(base_hybrid.sum(), 1e-12)

            undiagnosed = np.asarray([states[location]["undiagnosed"] for location in self.location_order], dtype=float)
            diagnosed_no_art = np.asarray([states[location]["diagnosed_no_art"] for location in self.location_order], dtype=float)
            art_unsuppressed = np.asarray([states[location]["art_unsuppressed"] for location in self.location_order], dtype=float)
            suppressed = np.asarray([states[location]["suppressed"] for location in self.location_order], dtype=float)
            recent_infections = np.asarray([
                sum(states[location]["recent_infections"][-3:]) for location in self.location_order
            ], dtype=float)

            weight_diagnosed = float(transmission_cfg.get("infectivity_diagnosed_untreated", 0.75))
            weight_art = float(transmission_cfg.get("infectivity_art_unsuppressed", 0.18))
            weight_suppressed = float(transmission_cfg.get("infectivity_virally_suppressed", 0.0))
            acute_multiplier = float(transmission_cfg.get("acute_infectivity_multiplier", 4.0))
            effective_infectious_pool = (
                undiagnosed
                + weight_diagnosed * diagnosed_no_art
                + weight_art * art_unsuppressed
                + weight_suppressed * suppressed
                + max(0.0, acute_multiplier - 1.0) * recent_infections
            )
            local_infectious_prevalence = effective_infectious_pool / np.maximum(populations, 1.0)
            neighbor_infectious_prevalence = np.asarray(
                self.spatial.matrix @ local_infectious_prevalence
            ).reshape(-1)
            neighbor_force_weight = float(transmission_cfg.get("neighbor_force_weight", 0.35))
            density_modifier = 0.82 + 0.36 * density_scores
            mobility_modifier = 0.90 + 0.22 * density_scores
            seasonal_amplitude = float(transmission_cfg.get("transmission_seasonality_amplitude", 0.06))
            seasonal_peak = int(transmission_cfg.get("transmission_peak_month", 3))
            seasonal_modifier = 1.0 + seasonal_amplitude * math.cos(
                2.0 * math.pi * (month - seasonal_peak) / 12.0
            )
            maximum_center_reduction = float(
                transmission_cfg.get("direct_center_prevention_max_reduction", 0.18)
            )
            center_prevention_reduction = maximum_center_reduction * testing_access
            raw_infection_score = (
                populations
                * (local_infectious_prevalence + neighbor_force_weight * neighbor_infectious_prevalence)
                * density_modifier
                * mobility_modifier
                * seasonal_modifier
                * (1.0 - center_prevention_reduction)
            )
            if infection_calibration is None:
                target_infections = base_regional_cases * float(
                    transmission_cfg.get("infection_to_diagnosis_ratio_at_calibration", 1.15)
                )
                infection_calibration = target_infections / max(raw_infection_score.sum(), 1e-12)
            new_infections = np.maximum(0.0, raw_infection_score * infection_calibration)

                                                                                             

                                                                                              

            background_fraction = float(
                transmission_cfg.get("background_incidence_fraction_of_baseline", 0.12)
            )
            background_access_reduction = float(
                transmission_cfg.get("background_incidence_access_reduction", 0.55)
            )
            background_total = (
                base_regional_cases
                * float(transmission_cfg.get("infection_to_diagnosis_ratio_at_calibration", 1.15))
                * background_fraction
                * max(0.20, 1.0 - background_access_reduction * float(np.mean(testing_access)))
            )
            profile_weights = np.asarray([
                self.profile.get((location, month), 0.0) for location in self.location_order
            ], dtype=float)
            population_weights = populations / max(populations.sum(), 1.0)
            density_weights = (density_scores + 0.10) / max((density_scores + 0.10).sum(), 1e-12)
            background_weights = 0.50 * profile_weights + 0.30 * population_weights + 0.20 * density_weights
            background_weights /= max(background_weights.sum(), 1e-12)
            new_infections += background_total * background_weights
            maximum_incidence = populations * float(
                transmission_cfg.get("maximum_monthly_incidence_per_100k", 4.0)
            ) / 100000.0
            new_infections = np.minimum(new_infections, maximum_incidence)

            base_diagnosis_rate = float(transmission_cfg.get("base_monthly_diagnosis_rate", 0.015))
            diagnosis_increment = float(transmission_cfg.get("testing_access_diagnosis_increment", 0.055))
            diagnosis_rate = np.clip(base_diagnosis_rate + diagnosis_increment * testing_access, 0.0, 0.30)
            acute_detection_fraction = float(transmission_cfg.get("acute_detection_fraction", 0.20))
            raw_mechanistic_diagnoses = (
                undiagnosed * diagnosis_rate
                + new_infections * acute_detection_fraction * (0.35 + 0.65 * testing_access)
            )
            if diagnosis_calibration is None:
                diagnosis_calibration = float(np.clip(
                    base_regional_cases / max(raw_mechanistic_diagnoses.sum(), 1e-12),
                    0.35,
                    3.0,
                ))
            mechanistic_diagnoses = np.maximum(0.0, raw_mechanistic_diagnoses * diagnosis_calibration)

            combined_prediction = (
                (1.0 - mechanistic_weight) * base_hybrid
                + mechanistic_weight * mechanistic_diagnoses
            )
            neighbor_prediction = np.asarray(self.spatial.matrix @ combined_prediction).reshape(-1)
            combined_prediction = (
                (1.0 - output_diffusion) * combined_prediction
                + output_diffusion * neighbor_prediction
            )
            if horizon_index > 1:
                combined_prediction = (
                    (1.0 - temporal_memory) * combined_prediction
                    + temporal_memory * previous_prediction
                )
            combined_prediction = np.maximum(combined_prediction, 0.0)
            raw_ratio = combined_prediction.sum() / max(base_regional_cases, 1e-12)
            dynamic_regional_ratio = float(np.clip(
                (1.0 - ratio_adaptation) * dynamic_regional_ratio + ratio_adaptation * raw_ratio,
                minimum_ratio,
                maximum_ratio,
            ))
            dynamic_regional_cases = base_regional_cases * dynamic_regional_ratio
            combined_prediction *= dynamic_regional_cases / max(combined_prediction.sum(), 1e-12)
            availability = undiagnosed + new_infections + np.maximum(plhiv_net_migration, 0.0)
            combined_prediction = np.minimum(combined_prediction, np.maximum(availability * 0.95, 0.0))
            dynamic_regional_cases = float(combined_prediction.sum())
            dynamic_regional_ratio = dynamic_regional_cases / max(base_regional_cases, 1e-12)
            previous_prediction = combined_prediction.copy()

            linkage_base = float(transmission_cfg.get("base_monthly_linkage_rate", 0.08))
            linkage_increment = float(transmission_cfg.get("testing_access_linkage_increment", 0.14))
            suppression_base = float(transmission_cfg.get("base_monthly_suppression_rate", 0.05))
            suppression_increment = float(transmission_cfg.get("testing_access_suppression_increment", 0.10))
            interruption_base = float(transmission_cfg.get("base_monthly_treatment_interruption_rate", 0.007))
            retention_effect = float(transmission_cfg.get("testing_access_retention_effect", 0.65))
            minimum_interruption = float(transmission_cfg.get("minimum_monthly_treatment_interruption_rate", 0.002))
            reengagement_rate = float(transmission_cfg.get("monthly_reengagement_rate", 0.025))
            mortality_u = float(transmission_cfg.get("monthly_attrition_undiagnosed", 0.0015))
            mortality_d = float(transmission_cfg.get("monthly_attrition_diagnosed_no_art", 0.0012))
            mortality_a = float(transmission_cfg.get("monthly_attrition_art_unsuppressed", 0.0008))
            mortality_v = float(transmission_cfg.get("monthly_attrition_suppressed", 0.0004))

            new_art = np.zeros(len(self.location_order), dtype=float)
            new_suppressed = np.zeros(len(self.location_order), dtype=float)
            interruptions = np.zeros(len(self.location_order), dtype=float)
            attrition = np.zeros(len(self.location_order), dtype=float)
            treatment_reduction = np.zeros(len(self.location_order), dtype=float)
            decomposition_rate = np.zeros(len(self.location_order), dtype=float)
            total_plhiv = np.zeros(len(self.location_order), dtype=float)
            art_coverage = np.zeros(len(self.location_order), dtype=float)
            suppression_coverage = np.zeros(len(self.location_order), dtype=float)
            provisional_need_scores = np.zeros(len(self.location_order), dtype=float)
            scheduled_due_periods: list[str] = [""] * len(self.location_order)
            pending_center_counts = np.zeros(len(self.location_order), dtype=float)


            horizon_years = max((horizon_index - 1) / 12.0, 0.0)
            cv = min(
                float(self.config["uncertainty"].get("maximum_cv", 0.90)),
                float(self.config["uncertainty"].get("base_cv", 0.35))
                + horizon_years * float(self.config["uncertainty"].get("cv_growth_per_year", 0.015)),
            )
            standard_error = np.sqrt(np.maximum(combined_prediction, 0.0) + rmse * rmse) * (0.55 + cv)
            lower80 = np.maximum(0.0, combined_prediction - 1.282 * standard_error)
            upper80 = combined_prediction + 1.282 * standard_error
            lower95 = np.maximum(0.0, combined_prediction - 1.960 * standard_error)
            upper95 = combined_prediction + 1.960 * standard_error

            rolling_rates = np.zeros(len(self.location_order), dtype=float)
            growth_ratios = np.zeros(len(self.location_order), dtype=float)
            rolling_cases_array = np.zeros(len(self.location_order), dtype=float)
            for index, location in enumerate(self.location_order):
                rows = by_location[location]
                state = states[location]
                diagnosis = float(combined_prediction[index])
                infection = float(new_infections[index])

                u_pool = max(0.0, float(state["undiagnosed"]) + infection - diagnosis)
                d_pool = max(0.0, float(state["diagnosed_no_art"]) + diagnosis)
                linkage_rate = float(np.clip(
                    linkage_base + linkage_increment * testing_access[index]
                    + reengagement_rate * testing_access[index],
                    0.0,
                    0.55,
                ))
                art_start = min(d_pool, d_pool * linkage_rate)
                d_after_linkage = max(0.0, d_pool - art_start)

                a_pool = max(0.0, float(state["art_unsuppressed"]) + art_start)
                suppression_rate = float(np.clip(
                    suppression_base + suppression_increment * testing_access[index],
                    0.0,
                    0.45,
                ))
                suppression_flow = min(a_pool, a_pool * suppression_rate)
                a_after_suppression = max(0.0, a_pool - suppression_flow)
                v_pool = max(0.0, float(state["suppressed"]) + suppression_flow)

                interruption_rate = max(
                    minimum_interruption,
                    interruption_base * (1.0 - retention_effect * testing_access[index]),
                )
                interrupted_a = a_after_suppression * interruption_rate
                interrupted_v = v_pool * interruption_rate * 0.55
                a_after_interruption = max(0.0, a_after_suppression - interrupted_a)
                v_after_interruption = max(0.0, v_pool - interrupted_v)
                d_after_interruption = d_after_linkage + interrupted_a + interrupted_v

                death_u = u_pool * mortality_u
                death_d = d_after_interruption * mortality_d
                death_a = a_after_interruption * mortality_a
                death_v = v_after_interruption * mortality_v
                state["undiagnosed"] = max(0.0, u_pool - death_u)
                state["diagnosed_no_art"] = max(0.0, d_after_interruption - death_d)
                state["art_unsuppressed"] = max(0.0, a_after_interruption - death_a)
                state["suppressed"] = max(0.0, v_after_interruption - death_v)
                state["recent_infections"].append(infection)
                state["recent_infections"] = state["recent_infections"][-3:]

                new_art[index] = art_start
                new_suppressed[index] = suppression_flow
                interruptions[index] = interrupted_a + interrupted_v
                attrition[index] = death_u + death_d + death_a + death_v
                treatment_reduction[index] = (
                    art_start * max(0.0, weight_diagnosed - weight_art)
                    + suppression_flow * max(0.0, weight_art - weight_suppressed)
                )
                decomposition_rate[index] = treatment_reduction[index] / max(effective_infectious_pool[index], 1e-9)
                total = (
                    state["undiagnosed"] + state["diagnosed_no_art"]
                    + state["art_unsuppressed"] + state["suppressed"]
                )
                total_plhiv[index] = total
                art_coverage[index] = (state["art_unsuppressed"] + state["suppressed"]) / max(total, 1e-9)
                suppression_coverage[index] = state["suppressed"] / max(total, 1e-9)

                past_cases = [float(item["cases"]) for item in rows[-12:]]
                rolling12 = sum(past_cases[-11:]) + diagnosis
                rolling_cases_array[index] = rolling12
                rolling_rate = rolling12 / max(populations[index], 1.0) * 100000.0
                rolling_rates[index] = rolling_rate
                recent3 = max(float(np.mean(past_cases[-3:])), 0.1)
                growth_ratios[index] = diagnosis / recent3

            neighbor_infectious_rate = np.asarray(
                self.spatial.matrix @ (effective_infectious_pool / np.maximum(populations, 1.0) * 100000.0)
            ).reshape(-1)
            for index, location in enumerate(self.location_order):
                state = states[location]
                facility_load = populations[index] / max(centers[index], 0.5)
                rate_score = np.clip(rolling_rates[index] / float(center_cfg.get("trigger_rate_per_100k", 18.0)), 0.0, 1.0)
                infectious_score = np.clip(
                    effective_infectious_pool[index] / max(populations[index], 1.0) * 100000.0
                    / float(center_cfg.get("trigger_infectious_pool_per_100k", 120.0)),
                    0.0,
                    1.0,
                )
                neighbor_score = np.clip(
                    neighbor_infectious_rate[index]
                    / float(center_cfg.get("trigger_neighbor_infectious_pool_per_100k", 100.0)),
                    0.0,
                    1.0,
                )
                capacity_score = np.clip(facility_load / capacity_per_center, 0.0, 1.0)
                access_gap = 1.0 - testing_access[index]
                provisional_need = 100.0 * (
                    0.26 * rate_score
                    + 0.22 * infectious_score
                    + 0.16 * neighbor_score
                    + 0.22 * capacity_score
                    + 0.14 * access_gap
                )
                provisional_need_scores[index] = provisional_need

                if provisional_need >= trigger_score:
                    state["center_need_streak"] += 1
                else:
                    state["center_need_streak"] = max(0, state["center_need_streak"] - 1)
                no_pending = len(state["pending_center_openings"]) == 0
                cooldown_ok = horizon_index - int(state["last_center_schedule_horizon"]) >= cooldown_months
                below_caps = (
                    int(state["total_new_centers"]) < max_new_centers
                    and centers[index] < maximum_total_centers
                )
                if (
                    auto_centers
                    and state["center_need_streak"] >= sustained_months
                    and no_pending
                    and cooldown_ok
                    and below_caps
                ):
                    due_horizon = horizon_index + construction_lead
                    state["pending_center_openings"].append(due_horizon)
                    state["last_center_schedule_horizon"] = horizon_index
                    state["center_need_streak"] = 0
                    state["total_new_centers"] += 1
                    scheduled_due_periods[index] = add_month(period, construction_lead)
                pending_center_counts[index] = len(state["pending_center_openings"])

            for index, meta in enumerate(metadata):
                location = meta["LOCATION"]
                state = states[location]
                output_rows.append({
                    "PERIOD": period,
                    "YEAR": year,
                    "MONTH": month,
                    "HORIZON_MONTH": horizon_index,
                    "PSGC": meta["PSGC"],
                    "PROVINCE": meta["PROVINCE"],
                    "LOCATION": location,
                    "BASE_REGIONAL_SCENARIO_CASES": float(base_regional_cases),
                    "MODEL_REGIONAL_INPUT_CASES": float(model_regional_cases),
                    "REGIONAL_SCENARIO_CASES": float(dynamic_regional_cases),
                    "REGIONAL_DYNAMIC_RATIO": float(dynamic_regional_ratio),
                    "MLR_CASES": float(mlr_prediction[index]),
                    "LSTM_CASES": float(lstm_prediction[index]),
                    "HYBRID_CASES_BEFORE_SPATIAL": float(base_hybrid[index]),
                    "MECHANISTIC_DIAGNOSES": float(mechanistic_diagnoses[index]),
                    "NEIGHBOR_SPATIAL_LAG_CASES": float(neighbor_prediction[index]),
                    "PREDICTED_CASES": float(combined_prediction[index]),
                    "LOWER_80": float(lower80[index]),
                    "UPPER_80": float(upper80[index]),
                    "LOWER_95": float(lower95[index]),
                    "UPPER_95": float(upper95[index]),
                    "POPULATION": float(populations[index]),
                    "MONTHLY_POPULATION_GROWTH_RATE": float(monthly_population_rates[index]),
                    "NATURAL_POPULATION_CHANGE": float(natural_changes[index]),
                    "NET_MIGRATION_CHANGE": float(migration_changes[index]),
                    "PLHIV_NET_MIGRATION": float(plhiv_net_migration[index]),
                    "DENSITY": float(densities[index]),
                    "ACTIVE_TESTING_CENTERS": float(centers[index]),
                    "NEW_TESTING_CENTERS_OPENED": int(opened_centers[index]),
                    "PENDING_TESTING_CENTERS": int(pending_center_counts[index]),
                    "CENTER_ESTABLISHMENT_SCHEDULED_FOR": scheduled_due_periods[index],
                    "TESTING_ACCESS_SCORE": float(testing_access[index]),
                    "CENTER_EFFECT_ON_TRANSMISSION": float(center_prevention_reduction[index]),
                    "HISTORICAL_SHARE": float(meta["HISTORICAL_SHARE"]),
                    "NEW_INFECTIONS_ESTIMATE": float(new_infections[index]),
                    "LOCAL_INFECTIOUS_PREVALENCE": float(local_infectious_prevalence[index]),
                    "NEIGHBOR_INFECTIOUS_PREVALENCE": float(neighbor_infectious_prevalence[index]),
                    "LOCAL_FORCE_OF_INFECTION_SCORE": float(raw_infection_score[index]),
                    "EFFECTIVE_INFECTIOUS_POOL": float(effective_infectious_pool[index]),
                    "PLHIV_UNDIAGNOSED": float(state["undiagnosed"]),
                    "PLHIV_DIAGNOSED_NOT_ON_ART": float(state["diagnosed_no_art"]),
                    "PLHIV_ON_ART_UNSUPPRESSED": float(state["art_unsuppressed"]),
                    "PLHIV_VIRALLY_SUPPRESSED": float(state["suppressed"]),
                    "TOTAL_PLHIV": float(total_plhiv[index]),
                    "NEW_ART_ENROLLMENTS": float(new_art[index]),
                    "NEWLY_VIRALLY_SUPPRESSED": float(new_suppressed[index]),
                    "TREATMENT_INTERRUPTION": float(interruptions[index]),
                    "PLHIV_ATTRITION": float(attrition[index]),
                    "ART_COVERAGE": float(art_coverage[index]),
                    "VIRAL_SUPPRESSION_COVERAGE": float(suppression_coverage[index]),
                    "INFECTIOUS_POOL_REDUCTION_FROM_TREATMENT": float(treatment_reduction[index]),
                    "TREATMENT_DECOMPOSITION_RATE": float(decomposition_rate[index]),
                    "ROLLING_12M_CASES": float(rolling_cases_array[index]),
                    "ROLLING_12M_RATE_PER_100K": float(rolling_rates[index]),
                    "DIAGNOSIS_GROWTH_RATIO": float(growth_ratios[index]),
                    "PROVISIONAL_CENTER_NEED_SCORE": float(provisional_need_scores[index]),
                    "DATA_STATUS": "MODEL-BASED MECHANISTIC SCENARIO FROM CONSTRAINED DEVELOPMENT DATA",
                })
                by_location[location].append({
                    "period": period, "year": year, "month": month,
                    "cases": float(combined_prediction[index]),
                    "population": float(populations[index]),
                    "density": float(densities[index]),
                    "centers": float(centers[index]),
                })
            regional_history[(year, month)] = float(dynamic_regional_cases)

        frame = pd.DataFrame(output_rows)
        frame = self._add_spatial_hotspots_and_pressure(frame)
        metadata = {
            "forecast_start": start_period,
            "forecast_end": end_period,
            "forecast_months": len(periods),
            "municipality_count": len(self.location_order),
            "phase1_hybrid_test_r2": float(self.bundle["metrics"]["Hybrid"]["test"]["r2"]),
            "phase1_hybrid_test_rmse": rmse,
            "hybrid_weights": {
                "mlr": float(self.bundle["hybrid_mlr_weight"]),
                "lstm": float(self.bundle["hybrid_lstm_weight"]),
                "mechanistic": mechanistic_weight,
            },
            "spatial_diffusion_weight": output_diffusion,
            "population_model": self.config.get("population_simulation", {}),
            "transmission_model": transmission_cfg,
            "testing_center_dynamics": center_cfg,
            "regional_model_warning": self.bundle["regional_model"]["warning"],
            "scientific_scope": (
                "Municipality-time targets were generated as constrained development simulations. "
                "The enhanced transmission engine is a deterministic population-level compartment and "
                "spatial-interaction scenario. It is not an individual-contact model, R0 estimate, or official "
                "surveillance forecast. Viral suppression is assigned near-zero sexual-transmission weight "
                "in accordance with treatment-as-prevention evidence, while all rates remain configurable assumptions."
            ),
        }
        return frame, metadata

    def _add_spatial_hotspots_and_pressure(self, frame: pd.DataFrame) -> pd.DataFrame:
        results = []
        for period, group in frame.groupby("PERIOD", sort=True):
            indexed = group.set_index("LOCATION").loc[self.location_order].copy()
            rate = indexed["ROLLING_12M_RATE_PER_100K"].to_numpy(float)
            growth = indexed["DIAGNOSIS_GROWTH_RATIO"].to_numpy(float)
            population = indexed["POPULATION"].to_numpy(float)
            centers = indexed["ACTIVE_TESTING_CENTERS"].to_numpy(float)
            infectious_rate = (
                indexed["EFFECTIVE_INFECTIOUS_POOL"].to_numpy(float)
                / np.maximum(population, 1.0) * 100000.0
            )
            new_infection_rate = (
                indexed["NEW_INFECTIONS_ESTIMATE"].to_numpy(float)
                / np.maximum(population, 1.0) * 100000.0
            )
            testing_access = indexed["TESTING_ACCESS_SCORE"].to_numpy(float)
            suppression_coverage = indexed["VIRAL_SUPPRESSION_COVERAGE"].to_numpy(float)
            neighbor_rate = np.asarray(self.spatial.matrix @ rate).reshape(-1)
            neighbor_infectious_rate = np.asarray(self.spatial.matrix @ infectious_rate).reshape(-1)
            moran = global_morans_i(rate, self.spatial.matrix)
            local_i, local_lag, clusters = local_moran_clusters(rate, self.spatial.matrix)
            gi_z, gi_p = getis_ord_gi_star(rate, self.spatial.binary)
            hotspot_classes = np.asarray([hotspot_class(value) for value in gi_z], dtype=object)
            hot_mask = gi_z >= 1.645
            component_ids, component_sizes = connected_components(hot_mask, self.spatial.binary, minimum_size=2)

            facility_load = np.divide(population, np.maximum(centers, 0.5))
            rate_score = robust_scale(rate)
            growth_score = robust_scale(growth)
            neighbor_score = robust_scale(neighbor_rate)
            infectious_score = robust_scale(infectious_rate)
            neighbor_infectious_score = robust_scale(neighbor_infectious_rate)
            infection_score = robust_scale(new_infection_rate)
            hotspot_score = np.clip((gi_z + 1.645) / 4.5, 0.0, 1.0)
            facility_score = robust_scale(facility_load)
            access_gap_score = np.clip(1.0 - testing_access, 0.0, 1.0)
            suppression_gap_score = np.clip(1.0 - suppression_coverage, 0.0, 1.0)
            pressure = 100.0 * (
                0.17 * rate_score
                + 0.10 * growth_score
                + 0.12 * neighbor_score
                + 0.16 * infectious_score
                + 0.13 * neighbor_infectious_score
                + 0.10 * infection_score
                + 0.10 * hotspot_score
                + 0.07 * access_gap_score
                + 0.05 * suppression_gap_score
            )
            center_need = 100.0 * (
                0.20 * rate_score
                + 0.14 * growth_score
                + 0.15 * hotspot_score
                + 0.18 * facility_score
                + 0.15 * access_gap_score
                + 0.10 * infectious_score
                + 0.08 * neighbor_infectious_score
            )

            center_need = 0.70 * center_need + 0.30 * indexed["PROVISIONAL_CENTER_NEED_SCORE"].to_numpy(float)
            alert = np.asarray([classify_pressure(value) for value in pressure], dtype=object)
            automatic = (
                (pressure >= 65.0)
                | (gi_z >= 1.96)
                | ((component_sizes >= 2) & (pressure >= 55.0))
                | ((neighbor_infectious_rate >= np.quantile(neighbor_infectious_rate, 0.85)) & (infectious_rate >= np.quantile(infectious_rate, 0.65)))
            )
            reasons = []
            for i in range(len(indexed)):
                parts = []
                if pressure[i] >= 65.0:
                    parts.append("TRANSMISSION_PRESSURE_PROXY")
                if gi_z[i] >= 1.96:
                    parts.append("STATISTICAL_HOTSPOT")
                if component_sizes[i] >= 2:
                    parts.append("CONNECTED_HOTSPOT_CLUSTER")
                if center_need[i] >= 70.0:
                    parts.append("TESTING_CENTER_GAP")
                if neighbor_infectious_score[i] >= 0.80:
                    parts.append("NEIGHBOR_INFECTIOUS_PRESSURE")
                if indexed.iloc[i]["PENDING_TESTING_CENTERS"] > 0:
                    parts.append("CENTER_EXPANSION_PENDING")
                reasons.append("+".join(parts) if parts else "NONE")

            indexed["GLOBAL_MORANS_I"] = moran
            indexed["LOCAL_MORANS_I"] = local_i
            indexed["LOCAL_SPATIAL_LAG_Z"] = local_lag
            indexed["LOCAL_MORAN_CLUSTER"] = clusters
            indexed["GI_STAR_Z_SCORE"] = gi_z
            indexed["GI_STAR_P_VALUE"] = gi_p
            indexed["HOTSPOT_CLASS"] = hotspot_classes
            indexed["HOTSPOT_CLUSTER_ID"] = component_ids
            indexed["HOTSPOT_CLUSTER_SIZE"] = component_sizes
            indexed["NEIGHBOR_RATE_PER_100K"] = neighbor_rate
            indexed["NEIGHBOR_INFECTIOUS_POOL_PER_100K"] = neighbor_infectious_rate
            indexed["NEW_INFECTION_RATE_PER_100K"] = new_infection_rate
            indexed["TRANSMISSION_PRESSURE_INDEX"] = pressure
            indexed["TRANSMISSION_PRESSURE_LEVEL"] = alert
            indexed["TESTING_CENTER_NEED_SCORE"] = center_need
            indexed["AUTOMATIC_ALERT"] = automatic.astype(int)
            indexed["ALERT_REASON"] = reasons
            results.append(indexed.reset_index())
        return pd.concat(results, ignore_index=True)

def classical_decomposition(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    locations: list[str],
) -> pd.DataFrame:
    observed = history.rename(columns={"CASES": "VALUE"})[["PERIOD", "LOCATION", "VALUE"]].copy()
    observed["SERIES_STATUS"] = "HISTORICAL DEVELOPMENT DATA"
    future = forecast.rename(columns={"PREDICTED_CASES": "VALUE"})[["PERIOD", "LOCATION", "VALUE"]].copy()
    future["SERIES_STATUS"] = "FORECAST SCENARIO"
    combined = pd.concat([observed, future], ignore_index=True)
    rows = []
    for location in locations:
        group = combined[combined["LOCATION"] == location].sort_values("PERIOD").copy()
        values = np.log1p(group["VALUE"].to_numpy(float))
        trend = pd.Series(values).rolling(12, center=True, min_periods=6).mean()
        trend = trend.bfill().ffill().to_numpy(float)
        detrended = values - trend
        months = np.asarray([int(period[5:7]) for period in group["PERIOD"]], dtype=int)
        historical_mask = group["SERIES_STATUS"].eq("HISTORICAL DEVELOPMENT DATA").to_numpy()
        seasonal_profile = {}
        for month in range(1, 13):
            selection = detrended[(months == month) & historical_mask]
            seasonal_profile[month] = float(np.mean(selection)) if len(selection) else 0.0
        mean_seasonal = float(np.mean(list(seasonal_profile.values())))
        seasonal_profile = {month: value - mean_seasonal for month, value in seasonal_profile.items()}
        seasonal = np.asarray([seasonal_profile[month] for month in months])
        residual = values - trend - seasonal
        historical_residual = residual[historical_mask]
        residual_mean = float(np.mean(historical_residual)) if len(historical_residual) else 0.0
        residual_std = float(np.std(historical_residual)) if len(historical_residual) else 1.0
        residual_z = (residual - residual_mean) / max(residual_std, 1e-9)
        var_residual = float(np.var(historical_residual)) if len(historical_residual) else 0.0
        var_detrended = float(np.var((values - trend)[historical_mask])) if historical_mask.any() else 0.0
        var_deseasonal = float(np.var((values - seasonal)[historical_mask])) if historical_mask.any() else 0.0
        trend_strength = max(0.0, 1.0 - var_residual / max(var_deseasonal, 1e-9))
        seasonal_strength = max(0.0, 1.0 - var_residual / max(var_detrended, 1e-9))
        for index, record in enumerate(group.itertuples(index=False)):
            rows.append({
                "PERIOD": record.PERIOD,
                "LOCATION": location,
                "OBSERVED_OR_FORECAST_VALUE": float(record.VALUE),
                "LOG1P_VALUE": float(values[index]),
                "TREND_COMPONENT": float(trend[index]),
                "SEASONAL_COMPONENT": float(seasonal[index]),
                "RESIDUAL_COMPONENT": float(residual[index]),
                "RESIDUAL_Z_SCORE": float(residual_z[index]),
                "RESIDUAL_ANOMALY": int(abs(residual_z[index]) >= 2.0),
                "TREND_STRENGTH": float(trend_strength),
                "SEASONAL_STRENGTH": float(seasonal_strength),
                "SERIES_STATUS": record.SERIES_STATUS,
            })
    return pd.DataFrame(rows)


def build_center_recommendations(
    forecast: pd.DataFrame,
    geojson: dict[str, Any],
    *,
    planning_period: str,
) -> pd.DataFrame:
    latest = forecast[forecast["PERIOD"] == planning_period].copy()
    horizon_summary = forecast.groupby(["PSGC", "PROVINCE", "LOCATION"], as_index=False).agg(
        MEAN_PRESSURE=("TRANSMISSION_PRESSURE_INDEX", "mean"),
        MAX_PRESSURE=("TRANSMISSION_PRESSURE_INDEX", "max"),
        HOTSPOT_MONTHS=("HOTSPOT_CLASS", lambda values: int(sum(str(v).startswith("HOT_SPOT") for v in values))),
        ALERT_MONTHS=("AUTOMATIC_ALERT", "sum"),
        MEAN_PREDICTED_CASES=("PREDICTED_CASES", "mean"),
        MAX_PREDICTED_CASES=("PREDICTED_CASES", "max"),
    )
    latest = latest.merge(horizon_summary, on=["PSGC", "PROVINCE", "LOCATION"], how="left")
    geometry_lookup = {
        str((feature.get("properties") or {}).get("PSGC")): shape(feature["geometry"])
        for feature in geojson.get("features") or []
    }
    rows = []
    for record in latest.itertuples(index=False):
        population = float(record.POPULATION)
        centers = float(record.ACTIVE_TESTING_CENTERS)
        pressure = float(record.TESTING_CENTER_NEED_SCORE)
        hotspot_persistence = float(record.HOTSPOT_MONTHS) / max(forecast["PERIOD"].nunique(), 1)
        capacity_need = max(0, math.ceil(population / 140000.0) - int(round(centers)))
        if pressure >= 75 or hotspot_persistence >= 0.30:
            capacity_need = max(capacity_need, 1)
        if pressure >= 88 and population >= 250000:
            capacity_need = max(capacity_need, 2)
        geometry = geometry_lookup[str(record.PSGC)]
        point = geometry.representative_point()
        level = "CRITICAL" if pressure >= 80 else "HIGH" if pressure >= 65 else "MODERATE" if pressure >= 45 else "LOW"
        rows.append({
            "PLANNING_PERIOD": planning_period,
            "PSGC": str(record.PSGC),
            "PROVINCE": str(record.PROVINCE),
            "LOCATION": str(record.LOCATION),
            "POPULATION": population,
            "CURRENT_ESTIMATED_TESTING_CENTERS": centers,
            "POPULATION_PER_CENTER": population / max(centers, 0.5),
            "MEAN_FORECAST_PRESSURE": float(record.MEAN_PRESSURE),
            "MAX_FORECAST_PRESSURE": float(record.MAX_PRESSURE),
            "HOTSPOT_MONTHS": int(record.HOTSPOT_MONTHS),
            "ALERT_MONTHS": int(record.ALERT_MONTHS),
            "TESTING_CENTER_NEED_SCORE": pressure,
            "PRIORITY_LEVEL": level,
            "RECOMMENDED_ADDITIONAL_CENTERS": int(capacity_need),
            "CANDIDATE_LATITUDE": float(point.y),
            "CANDIDATE_LONGITUDE": float(point.x),
            "CANDIDATE_METHOD": "Municipality representative point; exact site requires accessibility, land, privacy, staffing, and DOH validation",
            "RECOMMENDATION_STATUS": "SCENARIO PLANNING CANDIDATE - NOT AN APPROVED FACILITY SITE",
        })
    return pd.DataFrame(rows).sort_values(
        ["RECOMMENDED_ADDITIONAL_CENTERS", "TESTING_CENTER_NEED_SCORE"], ascending=False
    ).reset_index(drop=True)


def build_alerts(forecast: pd.DataFrame, recommendations: pd.DataFrame) -> pd.DataFrame:
    alerts = forecast[forecast["AUTOMATIC_ALERT"] == 1][[
        "PERIOD", "PSGC", "PROVINCE", "LOCATION", "PREDICTED_CASES", "ROLLING_12M_RATE_PER_100K",
        "HOTSPOT_CLASS", "HOTSPOT_CLUSTER_ID", "HOTSPOT_CLUSTER_SIZE", "TRANSMISSION_PRESSURE_INDEX",
        "TRANSMISSION_PRESSURE_LEVEL", "TESTING_CENTER_NEED_SCORE", "ALERT_REASON",
    ]].copy()
    alerts["ALERT_TYPE"] = "DYNAMIC SPATIOTEMPORAL WATCH"
    alerts["ALERT_STATUS"] = "SCENARIO-BASED; VERIFY WITH OFFICIAL SURVEILLANCE"
    facility = recommendations[recommendations["RECOMMENDED_ADDITIONAL_CENTERS"] > 0].copy()
    if not facility.empty:
        facility_alerts = pd.DataFrame({
            "PERIOD": facility["PLANNING_PERIOD"], "PSGC": facility["PSGC"],
            "PROVINCE": facility["PROVINCE"], "LOCATION": facility["LOCATION"],
            "PREDICTED_CASES": np.nan, "ROLLING_12M_RATE_PER_100K": np.nan,
            "HOTSPOT_CLASS": "FACILITY_NEED", "HOTSPOT_CLUSTER_ID": 0, "HOTSPOT_CLUSTER_SIZE": 0,
            "TRANSMISSION_PRESSURE_INDEX": facility["MAX_FORECAST_PRESSURE"],
            "TRANSMISSION_PRESSURE_LEVEL": facility["PRIORITY_LEVEL"],
            "TESTING_CENTER_NEED_SCORE": facility["TESTING_CENTER_NEED_SCORE"],
            "ALERT_REASON": "TESTING_CENTER_ESTABLISHMENT_CANDIDATE",
            "ALERT_TYPE": "TESTING CENTER PLANNING",
            "ALERT_STATUS": "REQUIRES DOH/LGU FACILITY REGISTRY AND SITE FEASIBILITY REVIEW",
        })
        alerts = pd.concat([alerts, facility_alerts], ignore_index=True)
    return alerts.sort_values(["PERIOD", "TRANSMISSION_PRESSURE_INDEX"], ascending=[True, False]).reset_index(drop=True)


def regional_summary(forecast: pd.DataFrame) -> pd.DataFrame:
    grouped = forecast.groupby("PERIOD", as_index=False).agg(
        BASE_REGIONAL_SCENARIO_CASES=("BASE_REGIONAL_SCENARIO_CASES", "first"),
        REGIONAL_SCENARIO_CASES=("REGIONAL_SCENARIO_CASES", "first"),
        REGIONAL_DYNAMIC_RATIO=("REGIONAL_DYNAMIC_RATIO", "first"),
        ALLOCATED_MUNICIPAL_CASES=("PREDICTED_CASES", "sum"),
        NEW_INFECTIONS_ESTIMATE=("NEW_INFECTIONS_ESTIMATE", "sum"),
        NEW_ART_ENROLLMENTS=("NEW_ART_ENROLLMENTS", "sum"),
        NEWLY_VIRALLY_SUPPRESSED=("NEWLY_VIRALLY_SUPPRESSED", "sum"),
        TREATMENT_INTERRUPTION=("TREATMENT_INTERRUPTION", "sum"),
        PLHIV_ATTRITION=("PLHIV_ATTRITION", "sum"),
        TOTAL_POPULATION=("POPULATION", "sum"),
        PLHIV_UNDIAGNOSED=("PLHIV_UNDIAGNOSED", "sum"),
        PLHIV_DIAGNOSED_NOT_ON_ART=("PLHIV_DIAGNOSED_NOT_ON_ART", "sum"),
        PLHIV_ON_ART_UNSUPPRESSED=("PLHIV_ON_ART_UNSUPPRESSED", "sum"),
        PLHIV_VIRALLY_SUPPRESSED=("PLHIV_VIRALLY_SUPPRESSED", "sum"),
        TOTAL_PLHIV=("TOTAL_PLHIV", "sum"),
        EFFECTIVE_INFECTIOUS_POOL=("EFFECTIVE_INFECTIOUS_POOL", "sum"),
        ACTIVE_TESTING_CENTERS=("ACTIVE_TESTING_CENTERS", "sum"),
        NEW_TESTING_CENTERS_OPENED=("NEW_TESTING_CENTERS_OPENED", "sum"),
        PENDING_TESTING_CENTERS=("PENDING_TESTING_CENTERS", "sum"),
        MEAN_TESTING_ACCESS_SCORE=("TESTING_ACCESS_SCORE", "mean"),
        MEAN_ART_COVERAGE=("ART_COVERAGE", "mean"),
        MEAN_VIRAL_SUPPRESSION_COVERAGE=("VIRAL_SUPPRESSION_COVERAGE", "mean"),
        LOWER_95_SUM=("LOWER_95", "sum"),
        UPPER_95_SUM=("UPPER_95", "sum"),
        HOT_SPOT_MUNICIPALITIES=("HOTSPOT_CLASS", lambda values: int(sum(str(v).startswith("HOT_SPOT") for v in values))),
        HIGH_OR_CRITICAL_PRESSURE=("TRANSMISSION_PRESSURE_LEVEL", lambda values: int(sum(v in {"HIGH", "CRITICAL"} for v in values))),
        ACTIVE_ALERTS=("AUTOMATIC_ALERT", "sum"),
        GLOBAL_MORANS_I=("GLOBAL_MORANS_I", "first"),
        MAX_TRANSMISSION_PRESSURE=("TRANSMISSION_PRESSURE_INDEX", "max"),
    )
    grouped["REGIONAL_PLHIV_PREVALENCE_PER_100K"] = (
        grouped["TOTAL_PLHIV"] / grouped["TOTAL_POPULATION"].clip(lower=1.0) * 100000.0
    )
    grouped["REGIONAL_EFFECTIVE_INFECTIOUS_POOL_PER_100K"] = (
        grouped["EFFECTIVE_INFECTIOUS_POOL"] / grouped["TOTAL_POPULATION"].clip(lower=1.0) * 100000.0
    )
    return grouped
