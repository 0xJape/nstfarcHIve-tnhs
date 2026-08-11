from __future__ import annotations

import gc
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from contextlib import closing
from pathlib import Path

import joblib
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.model_runtime import MunicipalityLSTM
RUN_ID = "_package_verification"
RUN_DIR = ROOT / "outputs" / RUN_ID
POINTER = ROOT / "outputs" / "latest_phase2_run.txt"
CACHE_FILES = [
    ROOT / "data" / "cache" / "region12_municipalities_gap_filled.geojson",
    ROOT / "data" / "cache" / "region12_municipalities_metadata.json",
]


def remove_directory(path: Path, attempts: int = 20) -> None:
    if not path.exists():
        return
    last_error: OSError | None = None
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc
            gc.collect()
            time.sleep(min(0.15 * (attempt + 1), 1.5))
    if path.exists():
        pending = path.with_name(f"{path.name}_cleanup_pending_{os.getpid()}")
        try:
            if pending.exists():
                shutil.rmtree(pending, ignore_errors=True)
            path.replace(pending)
            print(f"Verification output cleanup deferred: {pending}", file=sys.stderr)
            return
        except OSError:
            print(f"Verification passed, but temporary output could not be removed: {path}", file=sys.stderr)
            if last_error is not None:
                print(str(last_error), file=sys.stderr)


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()
    gc.collect()
    time.sleep(0.5)


def run(command: list[str], timeout: int = 360) -> None:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}")


def validate_models() -> None:
    required = [
        ROOT / "README.md",
        ROOT / "requirements.txt",
        ROOT / "spatiotemporal_config.json",
        ROOT / "data" / "arcHIVe_Municipality_Monthly.csv",
        ROOT / "models" / "mlr_pipeline.joblib",
        ROOT / "models" / "lstm_state.pt",
        ROOT / "models" / "model_bundle.json",
        ROOT / "src" / "run_phase2_system.py",
        ROOT / "src" / "phase2_runtime_api.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing package files: " + ", ".join(missing))
    bundle = json.loads((ROOT / "models" / "model_bundle.json").read_text(encoding="utf-8"))
    test_r2 = float(bundle["metrics"]["Hybrid"]["test"]["r2"])
    if test_r2 < 0.9:
        raise ValueError(f"Hybrid chronological test R2 is below 0.9: {test_r2:.6f}")
    if abs(float(bundle["hybrid_mlr_weight"]) + float(bundle["hybrid_lstm_weight"]) - 1.0) > 1e-8:
        raise ValueError("Hybrid model weights do not sum to one")
    joblib.load(ROOT / "models" / "mlr_pipeline.joblib")
    architecture = bundle["lstm_architecture"]
    model = MunicipalityLSTM(
        sequence_features=int(architecture["sequence_features"]),
        current_features=int(architecture["current_features"]),
        location_count=len(bundle["locations"]),
        hidden_size=int(architecture["hidden_size"]),
        embedding_size=int(architecture["embedding_size"]),
    )
    state = torch.load(ROOT / "models" / "lstm_state.pt", map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()


def main() -> int:
    old_pointer = POINTER.read_text(encoding="utf-8") if POINTER.exists() else None
    old_cache = {path: path.read_bytes() if path.exists() else None for path in CACHE_FILES}
    remove_directory(RUN_DIR)
    try:
        run([sys.executable, "-m", "compileall", "-q", "src", "scripts"], timeout=120)
        validate_models()
        run([
            sys.executable,
            "-m",
            "src.run_phase2_system",
            "--config",
            "spatiotemporal_config.json",
            "--test-fixture-boundaries",
            "--forecast-start",
            "2025-01",
            "--forecast-end",
            "2025-12",
            "--planning-period",
            "2025-12",
            "--run-id",
            RUN_ID,
        ])
        verification = json.loads((RUN_DIR / "VERIFICATION_SUMMARY.json").read_text(encoding="utf-8"))
        if verification["status"] != "PASS":
            raise RuntimeError("Simulation verification did not pass")
        if verification["municipalities"] != 49 or verification["forecast_rows"] != 588:
            raise RuntimeError("Unexpected municipality or forecast row count")
        if verification["max_regional_reconciliation_error"] > 1e-6:
            raise RuntimeError("Regional reconciliation failed")
        if verification["boundary_residual_gap_ratio"] > 1e-9:
            raise RuntimeError("Boundary gap validation failed")
        if verification["boundary_residual_overlap_ratio"] > 1e-9:
            raise RuntimeError("Boundary overlap validation failed")
        map_path = RUN_DIR / "maps" / "arcHIVe_Region_XII_Interactive_Forecast_Map.html"
        database_path = RUN_DIR / "database" / "archive_phase2.sqlite"
        required_outputs = [
            map_path,
            database_path,
            RUN_DIR / "tables" / "monthly_municipality_forecasts.csv",
            RUN_DIR / "tables" / "dynamic_hotspot_results.csv",
            RUN_DIR / "tables" / "transmission_compartment_simulation.csv",
            RUN_DIR / "tables" / "testing_center_recommendations.csv",
            RUN_DIR / "charts" / "01_regional_historical_and_forecast.png",
            RUN_DIR / "arcHIVe_Phase2_SpatioTemporal_GIS_Report.html",
        ]
        missing = [str(path) for path in required_outputs if not path.exists()]
        if missing:
            raise RuntimeError("Missing generated outputs: " + ", ".join(missing))
        map_text = map_path.read_text(encoding="utf-8")
        for marker in ["arcHIVe · Region XII HIV Forecast Map", "Testing Centers", "Time-series decomposition", "leaflet"]:
            if marker not in map_text:
                raise RuntimeError(f"Map marker is missing: {marker}")
        with closing(sqlite3.connect(database_path)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            required_tables = {
                "municipalities",
                "forecast_values",
                "hotspot_results",
                "transmission_pressure",
                "decomposition_results",
                "compartment_dynamics",
                "testing_center_recommendations",
                "alerts",
                "regional_summary",
                "adjacency_edges",
                "metadata",
            }
            if not required_tables.issubset(tables):
                raise RuntimeError("Required SQLite tables are missing")
            if connection.execute("SELECT COUNT(*) FROM forecast_values").fetchone()[0] != 588:
                raise RuntimeError("Unexpected SQLite forecast row count")
        process = subprocess.Popen(
            [sys.executable, "-m", "src.phase2_runtime_api", "--host", "127.0.0.1", "--port", "8876", "--run-dir", str(RUN_DIR)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            for _ in range(40):
                try:
                    with urllib.request.urlopen("http://127.0.0.1:8876/api/health", timeout=2) as response:
                        if json.loads(response.read()).get("status") == "ok":
                            break
                except Exception:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Runtime API did not become healthy")
            endpoints = [
                "/api/municipalities",
                "/api/dates",
                "/api/snapshot?period=2025-12",
                "/api/hotspots?period=2025-12",
                "/api/transmission?period=2025-12",
                "/api/compartments?period=2025-12",
                "/api/testing-centers",
                "/api/region-summary",
                "/api/geometry/municipalities",
                "/map",
            ]
            for endpoint in endpoints:
                with urllib.request.urlopen(f"http://127.0.0.1:8876{endpoint}", timeout=10) as response:
                    if response.status != 200 or not response.read(64):
                        raise RuntimeError(f"API endpoint failed: {endpoint}")
        finally:
            stop_process(process)
        print(json.dumps(verification, indent=2))
        print("arcHIVe developer handoff verification passed")
        return 0
    finally:
        remove_directory(RUN_DIR)
        if old_pointer is None:
            POINTER.unlink(missing_ok=True)
        else:
            POINTER.parent.mkdir(parents=True, exist_ok=True)
            POINTER.write_text(old_pointer, encoding="utf-8")
        for path, content in old_cache.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)


if __name__ == "__main__":
    raise SystemExit(main())
