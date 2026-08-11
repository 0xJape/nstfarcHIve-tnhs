from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from shapely.geometry import MultiPolygon, Point, Polygon, box, mapping, shape
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree


ARCGIS_QUERY_URL = (
    "https://ulap-nga.georisk.gov.ph/arcgis/rest/services/PSA/"
    "Municipal/MapServer/0/query"
)
GITHUB_BASE = (
    "https://raw.githubusercontent.com/faeldon/philippines-json-maps/master/"
    "2023/geojson"
)
PROVINCE_FILES = {
    "1204700000": "provdists/medres/municities-provdist-1204700000.0.01.json",
    "1206300000": "provdists/medres/municities-provdist-1206300000.0.01.json",
    "1206500000": "provdists/medres/municities-provdist-1206500000.0.01.json",
    "1208000000": "provdists/medres/municities-provdist-1208000000.0.01.json",
}
GENSAN_BARANGAYS = "municities/medres/bgysubmuns-municity-1230800000.0.01.json"


@dataclass(frozen=True)
class BoundaryResult:
    geojson: dict[str, Any]
    province_geojson: dict[str, Any]
    region_geojson: dict[str, Any]
    outside_mask: dict[str, Any]
    gap_report: dict[str, Any]
    source: str
    cache_path: Path


def normalize_text(value: Any) -> str:
    text = str(value or "").upper().strip()
    text = text.replace("CITY OF ", "").replace("MUNICIPALITY OF ", "")
    text = text.replace("Ñ", "N")
    text = re.sub(r"[^A-Z0-9']+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_location(value: Any) -> str:
    text = normalize_text(value)
    replacements = {
        "GENERAL SANTOS CITY": "GENERAL SANTOS",
        "GEN SANTOS": "GENERAL SANTOS",
        "SANTO NINO": "SANTO NIÑO",
        "SENATOR NINOY AQUINO": "SEN. NINOY AQUINO",
        "SEN NINOY AQUINO": "SEN. NINOY AQUINO",
        "MLANG": "M'LANG",
        "T BOLI": "T'BOLI",
    }
    return replacements.get(text, text)


def psgc10(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        try:
            value = str(int(value))
        except (TypeError, ValueError, OverflowError):
            value = str(value)
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    return digits.zfill(10)[-10:]


def _polygonal_parts(geometry: Any) -> list[Polygon]:
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return [part for part in geometry.geoms if not part.is_empty]
    return [part for part in getattr(geometry, "geoms", []) if isinstance(part, Polygon) and not part.is_empty]


def _valid_polygon(geometry: Any) -> Any:
    if geometry is None:
        return None
    if not geometry.is_valid:
        geometry = geometry.buffer(0)
    if geometry.is_empty or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        return None
    return geometry


def _outer_shell_without_holes(geometry: Any) -> Any:
    shells = [Polygon(part.exterior) for part in _polygonal_parts(geometry) if len(part.exterior.coords) >= 4]
    result = unary_union(shells) if shells else geometry
    return _valid_polygon(result)


def geometry_area_km2_approx(geometry: Any) -> float:
    if geometry is None or geometry.is_empty:
        return 0.0
    point = geometry.representative_point()
    return float(max(geometry.area, 0.0) * 111.32 * 111.32 * math.cos(math.radians(float(point.y))))


def _extract_feature(feature: dict[str, Any]) -> tuple[str, str, str, str, Any] | None:
    props = feature.get("properties") or {}
    code = psgc10(
        props.get("psgc_10d")
        or props.get("city_code")
        or props.get("adm3_psgc")
        or feature.get("id")
    )
    name = canonical_location(
        props.get("city_name")
        or props.get("adm3_en")
        or props.get("name")
        or props.get("NAME_2")
    )
    province = str(
        props.get("prov_name")
        or props.get("province")
        or props.get("adm2_en")
        or ""
    ).strip()
    province_code = psgc10(props.get("prov_code") or props.get("adm2_psgc"))
    geometry = _valid_polygon(shape(feature.get("geometry"))) if feature.get("geometry") else None
    if not code or not name or geometry is None:
        return None
    return code, name, province, province_code, geometry


def _canonical_feature(
    code: str,
    name: str,
    province: str,
    province_code: str,
    geometry: Any,
    source: str,
) -> dict[str, Any]:
    point = geometry.representative_point()
    return {
        "type": "Feature",
        "id": code,
        "properties": {
            "PSGC": code,
            "LOCATION": canonical_location(name),
            "PROVINCE": province,
            "PROVINCE_PSGC": province_code,
            "REGION_PSGC": "1200000000",
            "SOURCE": source,
            "AREA_KM2_APPROX": round(geometry_area_km2_approx(geometry), 4),
            "REP_LAT": round(float(point.y), 7),
            "REP_LON": round(float(point.x), 7),
        },
        "geometry": mapping(geometry),
    }


def _request_json(url: str, *, params: dict[str, Any] | None, timeout: int) -> dict[str, Any]:
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={"User-Agent": "arcHIVe-Phase2/2.0 (+research-development)"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object from {url}")
    return payload


def download_arcgis(expected_codes: set[str], timeout: int = 90) -> dict[str, Any]:
    attempts = [
        "reg_name LIKE '%SOCCSKSARGEN%'",
        "reg_name LIKE '%REGION XII%'",
        "reg_code = '120000000'",
        "reg_code = '1200000000'",
    ]
    last_error: Exception | None = None
    for where in attempts:
        try:
            payload = _request_json(
                ARCGIS_QUERY_URL,
                params={
                    "where": where,
                    "outFields": "*",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "geojson",
                },
                timeout=timeout,
            )
            features: dict[str, dict[str, Any]] = {}
            for raw in payload.get("features") or []:
                parsed = _extract_feature(raw)
                if parsed is None:
                    continue
                code, name, province, province_code, geometry = parsed
                if code in expected_codes:
                    features[code] = _canonical_feature(
                        code, name, province, province_code, geometry, "GeoRiskPH PSA Municipal ArcGIS"
                    )
            if set(features) == expected_codes:
                return {"type": "FeatureCollection", "features": [features[c] for c in sorted(features)]}
            missing = sorted(expected_codes - set(features))
            last_error = RuntimeError(f"ArcGIS query {where!r} returned {len(features)}/{len(expected_codes)} expected boundaries; missing {missing}")
        except Exception as exc:                                                  
            last_error = exc
    raise RuntimeError(f"Official ArcGIS boundary download failed: {last_error}")


def download_github_fallback(expected_codes: set[str], timeout: int = 90) -> dict[str, Any]:
    collected: dict[str, dict[str, Any]] = {}
    for province_code, relative in PROVINCE_FILES.items():
        payload = _request_json(f"{GITHUB_BASE}/{relative}", params=None, timeout=timeout)
        for raw in payload.get("features") or []:
            parsed = _extract_feature(raw)
            if parsed is None:
                continue
            code, name, province, parsed_province_code, geometry = parsed
            if code in expected_codes:
                collected[code] = _canonical_feature(
                    code,
                    name,
                    province or province_code,
                    parsed_province_code or province_code,
                    geometry,
                    "faeldon/philippines-json-maps 2023",
                )

    if "1230800000" in expected_codes and "1230800000" not in collected:
        payload = _request_json(f"{GITHUB_BASE}/{GENSAN_BARANGAYS}", params=None, timeout=timeout)
        geometries = []
        for raw in payload.get("features") or []:
            if raw.get("geometry"):
                geometry = _valid_polygon(shape(raw["geometry"]))
                if geometry is not None:
                    geometries.append(geometry)
        if geometries:
            gensan = _outer_shell_without_holes(unary_union(geometries))
            collected["1230800000"] = _canonical_feature(
                "1230800000",
                "GENERAL SANTOS",
                "General Santos City",
                "1230800000",
                gensan,
                "faeldon 2023 barangay dissolve",
            )

    missing = sorted(expected_codes - set(collected))
    if missing:
        raise RuntimeError(
            "GitHub boundary fallback did not provide every current Region XII municipality. "
            f"Missing PSGC codes: {missing}"
        )
    return {"type": "FeatureCollection", "features": [collected[c] for c in sorted(collected)]}


def validate_boundary_join(geojson: dict[str, Any], expected: dict[str, str]) -> dict[str, Any]:
    seen: dict[str, str] = {}
    null_geometries: list[str] = []
    invalid_geometries: list[str] = []
    for feature in geojson.get("features") or []:
        props = feature.get("properties") or {}
        code = psgc10(props.get("PSGC") or feature.get("id"))
        name = canonical_location(props.get("LOCATION"))
        if not feature.get("geometry"):
            null_geometries.append(code)
            continue
        geometry = _valid_polygon(shape(feature["geometry"]))
        if geometry is None:
            invalid_geometries.append(code)
            continue
        seen[code] = name
    missing = sorted(set(expected) - set(seen))
    extra = sorted(set(seen) - set(expected))
    name_mismatches = {
        code: {"expected": expected[code], "boundary": seen[code]}
        for code in sorted(set(expected) & set(seen))
        if canonical_location(expected[code]) != canonical_location(seen[code])
    }
    result = {
        "expected_count": len(expected),
        "feature_count": len(seen),
        "missing_psgc": missing,
        "extra_psgc": extra,
        "null_geometries": null_geometries,
        "invalid_geometries": invalid_geometries,
        "name_mismatches": name_mismatches,
        "valid": not (missing or extra or null_geometries or invalid_geometries),
    }
    if not result["valid"]:
        raise ValueError(f"Region XII municipal boundary validation failed: {json.dumps(result, indent=2)}")
    return result


def fill_internal_boundary_gaps(
    geojson: dict[str, Any],
    tolerance_degrees: float = 0.0015,
    validation_ratio_tolerance: float = 1e-9,
) -> tuple[dict[str, Any], Any, dict[str, Any]]:
    features = geojson.get("features") or []
    originals: list[Any] = []
    for index, feature in enumerate(features):
        geometry = _valid_polygon(shape(feature.get("geometry")))
        if geometry is None:
            raise ValueError(f"Invalid polygon geometry at boundary feature {index}")
        originals.append(geometry)

    raw_union = _valid_polygon(unary_union(originals))
    if raw_union is None:
        raise RuntimeError("Could not union Region XII municipality polygons")
    closed = raw_union.buffer(tolerance_degrees, join_style=2).buffer(-tolerance_degrees, join_style=2)
    if closed.is_empty:
        closed = raw_union
    region_shell = _outer_shell_without_holes(closed)
    if region_shell is None:
        raise RuntimeError("Could not construct a Region XII boundary shell")

    boundary_linework = unary_union([region_shell.boundary, *[geometry.boundary for geometry in originals]])
    atomic_faces: list[Polygon] = []
    for face in polygonize(boundary_linework):
        if face.is_empty or face.area <= 1e-13:
            continue
        point = face.representative_point()
        if region_shell.covers(point):
            atomic_faces.extend(part for part in _polygonal_parts(face.intersection(region_shell)) if part.area > 1e-13)
    if not atomic_faces:
        raise RuntimeError("Boundary topology partitioning produced no polygon faces")

    tree = STRtree(originals)
    interior_points = [geometry.representative_point() for geometry in originals]
    assigned: list[list[Any]] = [[] for _ in originals]
    gap_count = overlap_count = 0
    gap_area = overlap_area = 0.0
    for face in atomic_faces:
        point = face.representative_point()
        candidate_indices = [int(v) for v in tree.query(point)]
        covering = [index for index in candidate_indices if originals[index].covers(point)]
        if len(covering) == 1:
            owner = covering[0]
        elif len(covering) > 1:
            owner = min(covering, key=lambda index: (point.distance(interior_points[index]), index))
            overlap_count += 1
            overlap_area += float(face.area)
        else:
            owner = int(tree.nearest(point))
            gap_count += 1
            gap_area += float(face.area)
        assigned[owner].append(face)

    filled = []
    for index, faces in enumerate(assigned):
        if not faces:
            raise RuntimeError(f"No partition face was assigned to municipality index {index}")
        geometry = _valid_polygon(unary_union(faces))
        if geometry is None:
            raise RuntimeError(f"Invalid filled geometry for municipality index {index}")
        filled.append(geometry)

    filled_union = _valid_polygon(unary_union(filled))
    shell_area = max(float(region_shell.area), 1e-15)
    residual_area = float(max(region_shell.difference(filled_union).area, 0.0))
    overlap_after = float(max(sum(item.area for item in filled) - filled_union.area, 0.0))
    residual_ratio = residual_area / shell_area
    overlap_ratio = overlap_after / shell_area
    if residual_ratio > validation_ratio_tolerance or overlap_ratio > validation_ratio_tolerance:
        raise RuntimeError(
            "Gap repair failed partition validation: "
            f"residual_ratio={residual_ratio:.3e}, overlap_ratio={overlap_ratio:.3e}"
        )

    result = json.loads(json.dumps(geojson))
    total_added = total_removed = 0.0
    for index, feature in enumerate(result["features"]):
        final = filled[index]
        added = final.difference(originals[index])
        removed = originals[index].difference(final)
        total_added += float(max(added.area, 0.0))
        total_removed += float(max(removed.area, 0.0))
        feature["geometry"] = mapping(final)
        props = feature.setdefault("properties", {})
        props["TOPOLOGY_GAP_FILLED"] = round(float(max(added.area, 0.0)), 12)
        props["TOPOLOGY_OVERLAP_REMOVED"] = round(float(max(removed.area, 0.0)), 12)
        point = final.representative_point()
        props["REP_LAT"] = round(float(point.y), 7)
        props["REP_LON"] = round(float(point.x), 7)
        props["AREA_KM2_APPROX"] = round(geometry_area_km2_approx(final), 4)

    report = {
        "feature_count": len(features),
        "tolerance_degrees": tolerance_degrees,
        "detected_gap_face_count": gap_count,
        "detected_overlap_face_count": overlap_count,
        "detected_gap_area_degrees2": gap_area,
        "detected_overlap_area_degrees2": overlap_area,
        "total_added_area_degrees2": total_added,
        "total_removed_overlap_area_degrees2": total_removed,
        "residual_uncovered_ratio": residual_ratio,
        "residual_overlap_ratio": overlap_ratio,
        "fully_covered": residual_ratio <= validation_ratio_tolerance,
        "non_overlapping": overlap_ratio <= validation_ratio_tolerance,
    }
    return result, region_shell, report


def dissolve_provinces(geojson: dict[str, Any]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[Any]] = {}
    for feature in geojson.get("features") or []:
        props = feature.get("properties") or {}
        key = (str(props.get("PROVINCE_PSGC") or ""), str(props.get("PROVINCE") or ""))
        groups.setdefault(key, []).append(shape(feature["geometry"]))
    result = []
    for (code, name), geometries in sorted(groups.items()):
        geometry = _valid_polygon(unary_union(geometries))
        result.append({
            "type": "Feature",
            "id": code or name,
            "properties": {"PROVINCE_PSGC": code, "PROVINCE": name},
            "geometry": mapping(geometry),
        })
    return {"type": "FeatureCollection", "features": result}


def region_feature(region_shell: Any) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "id": "1200000000",
            "properties": {"REGION_PSGC": "1200000000", "REGION": "SOCCSKSARGEN (Region XII)"},
            "geometry": mapping(region_shell),
        }],
    }


def outside_mask(region_shell: Any) -> dict[str, Any]:
    world = box(-180.0, -85.0, 180.0, 85.0)
    outside = world.difference(region_shell)
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"PURPOSE": "Gray-out mask outside Region XII"},
            "geometry": mapping(outside),
        }],
    }


def create_test_fixture(expected: dict[str, str]) -> dict[str, Any]:
    """Generate a deterministic topology fixture for offline package tests only."""
    province_order = ["Cotabato", "South Cotabato", "Sultan Kudarat", "Sarangani", "General Santos City"]
    codes = sorted(expected)
    province_by_prefix = {
        "12047": "Cotabato", "12063": "South Cotabato", "12065": "Sultan Kudarat",
        "12080": "Sarangani", "12308": "General Santos City",
    }
    grouped: dict[str, list[str]] = {name: [] for name in province_order}
    for code in codes:
        grouped[province_by_prefix.get(code[:5], "General Santos City")].append(code)
    origins = {
        "Cotabato": (124.30, 6.75),
        "South Cotabato": (124.55, 6.15),
        "Sultan Kudarat": (123.95, 6.15),
        "Sarangani": (124.75, 5.65),
        "General Santos City": (125.05, 5.95),
    }
    features = []
    for province in province_order:
        items = grouped[province]
        if not items:
            continue
        cols = max(1, math.ceil(math.sqrt(len(items))))
        x0, y0 = origins[province]
        for i, code in enumerate(items):
            col, row = i % cols, i // cols
            geometry = box(x0 + col * 0.09, y0 + row * 0.09, x0 + (col + 1) * 0.09, y0 + (row + 1) * 0.09)
            features.append(_canonical_feature(code, expected[code], province, code[:5] + "00000", geometry, "TEST FIXTURE - NOT OPERATIONAL"))
    return {"type": "FeatureCollection", "features": features}


def load_boundaries(
    expected: dict[str, str],
    cache_path: Path,
    metadata_path: Path,
    *,
    force_download: bool = False,
    use_test_fixture: bool = False,
    timeout: int = 90,
    gap_tolerance_degrees: float = 0.0015,
) -> BoundaryResult:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    source = ""
    if use_test_fixture:
        raw = create_test_fixture(expected)
        source = "offline test fixture"
    elif cache_path.exists() and not force_download:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        source = "validated local cache"
    else:
        errors: list[str] = []
        try:
            raw = download_arcgis(set(expected), timeout=timeout)
            source = "GeoRiskPH PSA Municipal ArcGIS"
        except Exception as exc:
            errors.append(str(exc))
            try:
                raw = download_github_fallback(set(expected), timeout=timeout)
                source = "faeldon/philippines-json-maps 2023 fallback"
            except Exception as fallback_exc:
                errors.append(str(fallback_exc))
                raise RuntimeError(
                    "Actual Region XII boundaries could not be downloaded. Internet access is required "
                    "for the first operational run. The system refuses to substitute fabricated map polygons.\n"
                    + "\n".join(f"- {item}" for item in errors)
                ) from fallback_exc
        cache_path.write_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    validation = validate_boundary_join(raw, expected)
    repaired, shell, gap_report = fill_internal_boundary_gaps(raw, tolerance_degrees=gap_tolerance_degrees)
    validation_after = validate_boundary_join(repaired, expected)
    provinces = dissolve_provinces(repaired)
    region = region_feature(shell)
    mask = outside_mask(shell)
    if not use_test_fixture:
        cache_path.write_text(json.dumps(repaired, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "cache_path": str(cache_path),
        "validation_before": validation,
        "validation_after": validation_after,
        "gap_report": gap_report,
        "operational": not use_test_fixture,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return BoundaryResult(
        geojson=repaired,
        province_geojson=provinces,
        region_geojson=region,
        outside_mask=mask,
        gap_report=gap_report,
        source=source,
        cache_path=cache_path,
    )
