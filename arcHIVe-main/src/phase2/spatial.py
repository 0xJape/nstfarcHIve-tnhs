from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import sparse
from scipy.stats import norm
from shapely.geometry import shape
from shapely.strtree import STRtree


@dataclass(frozen=True)
class SpatialWeights:
    codes: list[str]
    names: list[str]
    matrix: sparse.csr_matrix
    binary: sparse.csr_matrix
    edges: list[dict[str, Any]]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(value))


def build_spatial_weights(
    geojson: dict[str, Any],
    *,
    tolerance_degrees: float = 0.00008,
    minimum_neighbors: int = 2,
    fallback_max_distance_km: float = 60.0,
) -> SpatialWeights:
    features = geojson.get("features") or []
    codes = [str((feature.get("properties") or {}).get("PSGC") or feature.get("id")) for feature in features]
    names = [str((feature.get("properties") or {}).get("LOCATION") or "") for feature in features]
    geometries = [shape(feature["geometry"]) for feature in features]
    points = [geometry.representative_point() for geometry in geometries]
    tree = STRtree(geometries)
    neighbors: list[set[int]] = [set() for _ in features]
    edge_types: dict[tuple[int, int], str] = {}

    for i, geometry in enumerate(geometries):
        query_geometry = geometry.buffer(tolerance_degrees)
        for raw_index in tree.query(query_geometry):
            j = int(raw_index)
            if i == j:
                continue
            if query_geometry.intersects(geometries[j]):
                a, b = sorted((i, j))
                neighbors[i].add(j)
                neighbors[j].add(i)
                edge_types[(a, b)] = "QUEEN_CONTIGUITY"


    for i in range(len(features)):
        if len(neighbors[i]) >= minimum_neighbors:
            continue
        distances = []
        for j in range(len(features)):
            if i == j or j in neighbors[i]:
                continue
            distance = haversine_km(points[i].y, points[i].x, points[j].y, points[j].x)
            distances.append((distance, j))
        for distance, j in sorted(distances):
            if distance > fallback_max_distance_km and neighbors[i]:
                break
            a, b = sorted((i, j))
            neighbors[i].add(j)
            neighbors[j].add(i)
            edge_types.setdefault((a, b), "DISTANCE_FALLBACK")
            if len(neighbors[i]) >= minimum_neighbors:
                break

    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []
    binary_values: list[int] = []
    for i, members in enumerate(neighbors):
        degree = max(len(members), 1)
        for j in sorted(members):
            rows.append(i)
            cols.append(j)
            values.append(1.0 / degree)
            binary_values.append(1)
    matrix = sparse.csr_matrix((values, (rows, cols)), shape=(len(features), len(features)))
    binary = sparse.csr_matrix((binary_values, (rows, cols)), shape=(len(features), len(features)))

    edges = []
    for (i, j), edge_type in sorted(edge_types.items()):
        edges.append({
            "FROM_PSGC": codes[i],
            "FROM_LOCATION": names[i],
            "TO_PSGC": codes[j],
            "TO_LOCATION": names[j],
            "EDGE_TYPE": edge_type,
            "DISTANCE_KM": round(haversine_km(points[i].y, points[i].x, points[j].y, points[j].x), 4),
        })
    return SpatialWeights(codes=codes, names=names, matrix=matrix, binary=binary, edges=edges)


def global_morans_i(values: np.ndarray, weights: sparse.csr_matrix) -> float:
    x = np.asarray(values, dtype=float)
    centered = x - np.nanmean(x)
    denominator = float(np.dot(centered, centered))
    s0 = float(weights.sum())
    if denominator <= 0 or s0 <= 0:
        return 0.0
    numerator = float(centered @ (weights @ centered))
    return float(len(x) / s0 * numerator / denominator)


def local_moran_clusters(values: np.ndarray, weights: sparse.csr_matrix) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray(values, dtype=float)
    std = float(np.nanstd(x))
    z = np.zeros_like(x) if std <= 0 else (x - np.nanmean(x)) / std
    lag = np.asarray(weights @ z).reshape(-1)
    local_i = z * lag
    cluster = np.full(len(x), "NOT_SIGNIFICANT", dtype=object)

    strong = np.abs(local_i) >= 0.35
    cluster[strong & (z >= 0) & (lag >= 0)] = "HIGH-HIGH"
    cluster[strong & (z < 0) & (lag < 0)] = "LOW-LOW"
    cluster[strong & (z >= 0) & (lag < 0)] = "HIGH-LOW"
    cluster[strong & (z < 0) & (lag >= 0)] = "LOW-HIGH"
    return local_i, lag, cluster


def getis_ord_gi_star(values: np.ndarray, binary_weights: sparse.csr_matrix) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < 3:
        return np.zeros(n), np.ones(n)
    mean = float(np.mean(x))
    variance_term = float(np.sum(x * x) / n - mean * mean)
    std = math.sqrt(max(variance_term, 0.0))
    if std <= 1e-12:
        return np.zeros(n), np.ones(n)


    w = binary_weights.copy().astype(float)
    w = w + sparse.identity(n, dtype=float, format="csr")
    sum_w = np.asarray(w.sum(axis=1)).reshape(-1)
    sum_w2 = np.asarray(w.power(2).sum(axis=1)).reshape(-1)
    numerator = np.asarray(w @ x).reshape(-1) - mean * sum_w
    denominator = std * np.sqrt(np.maximum((n * sum_w2 - sum_w * sum_w) / max(n - 1, 1), 1e-15))
    z = np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator > 0)
    p = 2.0 * norm.sf(np.abs(z))
    return z, p


def hotspot_class(z_score: float) -> str:
    if z_score >= 2.576:
        return "HOT_SPOT_99"
    if z_score >= 1.960:
        return "HOT_SPOT_95"
    if z_score >= 1.645:
        return "HOT_SPOT_90"
    if z_score <= -2.576:
        return "COLD_SPOT_99"
    if z_score <= -1.960:
        return "COLD_SPOT_95"
    if z_score <= -1.645:
        return "COLD_SPOT_90"
    return "NOT_SIGNIFICANT"


def connected_components(mask: np.ndarray, binary_weights: sparse.csr_matrix, minimum_size: int = 2) -> tuple[np.ndarray, np.ndarray]:
    active = np.asarray(mask, dtype=bool)
    component_ids = np.zeros(len(active), dtype=int)
    component_sizes = np.zeros(len(active), dtype=int)
    component = 0
    for start in range(len(active)):
        if not active[start] or component_ids[start] != 0:
            continue
        members: list[int] = []
        queue: deque[int] = deque([start])
        component_ids[start] = -1
        while queue:
            node = queue.popleft()
            members.append(node)
            begin, end = binary_weights.indptr[node], binary_weights.indptr[node + 1]
            for neighbor in binary_weights.indices[begin:end]:
                neighbor = int(neighbor)
                if active[neighbor] and component_ids[neighbor] == 0:
                    component_ids[neighbor] = -1
                    queue.append(neighbor)
        if len(members) >= minimum_size:
            component += 1
            for member in members:
                component_ids[member] = component
                component_sizes[member] = len(members)
        else:
            for member in members:
                component_ids[member] = 0
    return component_ids, component_sizes
