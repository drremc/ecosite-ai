"""EcoSite v0.1 — reproducible preliminary habitat/wetlands screening.

This is NOT a site approval or full biodiversity impact assessment.
The NLCD estimator samples a ~30 m raster; it is not an exact habitat survey.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone

import requests
from pyproj import Transformer
from shapely.geometry import Polygon, MultiPolygon, box, shape
from shapely.ops import transform, unary_union

NLCD_URL = "https://di-nlcd.img.arcgis.com/arcgis/rest/services/USA_NLCD_Annual_LandCover/ImageServer/getSamples"
NWI_URL = "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0/query"
NLCD_YEAR = 2024  # latest year exposed by this specific live ArcGIS image service in Nov 2026
AREA_TO_ACRES = 0.00024710538147
SEARCH_RADIUS_M = 500
TO_EQUAL = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True).transform
FROM_EQUAL = Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True).transform

COVER = {
    11: ("Open water", "water"),
    12: ("Perennial ice/snow", "other"),
    21: ("Developed open space", "developed_open"),
    22: ("Developed low intensity", "developed"),
    23: ("Developed medium intensity", "developed"),
    24: ("Developed high intensity", "developed"),
    31: ("Barren land", "other"),
    41: ("Deciduous forest", "natural"),
    42: ("Evergreen forest", "natural"),
    43: ("Mixed forest", "natural"),
    51: ("Dwarf scrub", "natural"),
    52: ("Shrub / scrub", "natural"),
    71: ("Grassland / herbaceous", "natural"),
    72: ("Sedge / herbaceous", "natural"),
    73: ("Lichens", "natural"),
    74: ("Moss", "natural"),
    81: ("Pasture / hay", "agriculture"),
    82: ("Cultivated crops", "agriculture"),
    90: ("Woody wetlands", "wetland"),
    95: ("Emergent herbaceous wetlands", "wetland"),
}


def requests_json(url: str, data: dict) -> dict:
    try:
        response = requests.post(url, data=data, timeout=35,
                                 headers={"User-Agent": "EcoSite-education-prototype/0.1"})
        response.raise_for_status()
        obj = response.json()
        if "error" in obj:
            raise ValueError(str(obj["error"]))
        return obj
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(f"Map service unavailable or invalid response: {exc}") from exc


def ensure_polygon(feature: dict):
    try:
        geom = shape(feature["geometry"] if feature.get("type") == "Feature" else feature)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid geometry: {exc}") from exc
    if not isinstance(geom, (Polygon, MultiPolygon)):
        raise ValueError("Please draw a polygon or rectangle (not a point or line).")
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.is_empty or not isinstance(geom, (Polygon, MultiPolygon)):
        raise ValueError("The drawn polygon is empty or invalid.")
    if not (-125 < geom.centroid.x < -66 and 24 < geom.centroid.y < 50):
        raise ValueError("This prototype currently supports the contiguous United States only.")
    acres = transform(TO_EQUAL, geom).area * AREA_TO_ACRES
    if acres < 0.25:
        raise ValueError("Please draw an area of at least 0.25 acres (larger than one NLCD pixel).")
    if acres > 2500:
        raise ValueError("Please draw an area under 2,500 acres for this first version.")
    return geom


def acres_of(geom):
    return transform(TO_EQUAL, geom).area * AREA_TO_ACRES


def esri_rings(geom):
    """Build Esri Polygon geometry. For a buffer in this app, no holes are expected."""
    rings = []
    geoms = [geom] if isinstance(geom, Polygon) else geom.geoms
    for sub in geoms:
        rings.append([list(pt) for pt in sub.exterior.coords])
        for hole in sub.interiors:
            rings.append([list(pt) for pt in hole.coords])
    return {"rings": rings, "spatialReference": {"wkid": 4326}}


def sample_grid(polygon, target=380):
    """Equal-area systematic sample points, excluding locations outside footprint.

    Target approximately 380 cells, no finer than 30 m, for honest NLCD resolution.
    The resulting land-cover percentages are estimates, not a pixel-exact acreage count.
    """
    projected = transform(TO_EQUAL, polygon)
    area = projected.area
    step = max(30.0, math.sqrt(area / target))
    minx, miny, maxx, maxy = projected.bounds
    points = []
    weights = []
    x = minx
    while x < maxx:
        y = miny
        while y < maxy:
            cell = box(x, y, min(x + step, maxx), min(y + step, maxy))
            intersection = projected.intersection(cell)
            if not intersection.is_empty and intersection.area > 0.0001:
                p = intersection.representative_point()
                points.append(list(FROM_EQUAL(p.x, p.y)))
                weights.append(intersection.area)
            y += step
        x += step
    if len(points) > 1000:
        # Very jagged geometry could produce extra boundary cells; avoid silently truncating.
        raise ValueError("Polygon geometry is too complex for the prototype; please simplify it.")
    return points, weights, step


def get_land_cover(polygon):
    points, weights, step = sample_grid(polygon)
    if not points:
        raise RuntimeError("No valid NLCD sample points were generated.")
    geom = {"points": points, "spatialReference": {"wkid": 4326}}
    payload = {
        "f": "json", "geometryType": "esriGeometryMultipoint", "geometry": json.dumps(geom),
        "mosaicRule": json.dumps({"mosaicMethod": "esriMosaicAttribute", "sortField": "Year",
                                  "sortValue": str(NLCD_YEAR), "where": f"Year = {NLCD_YEAR}"}),
        "interpolation": "RSP_NearestNeighbor", "returnFirstValueOnly": "true",
    }
    result = requests_json(NLCD_URL, payload)
    samples = result.get("samples", [])
    if not isinstance(samples, list) or not samples:
        raise RuntimeError("NLCD did not return land-cover samples for this site.")

    # ESRI may return locationId; if not, map projected response locations to the closest
    # original point. Assume one sample per requested position; reject ambiguous responses.
    from scipy.spatial import cKDTree
    xy = [TO_EQUAL(*pt) for pt in points]
    tree = cKDTree(xy)
    seen = set()
    groups = defaultdict(float)
    classes = defaultdict(float)
    valid_area = 0
    for s in samples:
        loc = s.get("location", {})
        x, y = loc.get("x"), loc.get("y")
        if x is None or y is None:
            continue
        # ArcGIS returns source coordinates as input SR for getSamples.
        sr = loc.get("spatialReference", {}).get("wkid", 4326)
        if sr in (4326, 4269):
            xx, yy = TO_EQUAL(x, y)
        elif sr in (3857, 102100):
            xx, yy = Transformer.from_crs("EPSG:3857", "EPSG:5070", always_xy=True).transform(x, y)
        else:
            raise RuntimeError(f"Unexpected sample spatial reference {sr}; cannot reliably locate pixels.")
        distance, i = tree.query((xx, yy))
        if distance > max(25, step * 0.8) or i in seen:
            continue
        seen.add(i)
        try:
            code = int(float(str(s.get("value", "")).split(",")[0]))
        except ValueError:
            continue
        if code not in COVER:
            continue
        label, category = COVER[code]
        groups[category] += weights[i]
        classes[label] += weights[i]
        valid_area += weights[i]
    area = transform(TO_EQUAL, polygon).area
    coverage = valid_area / area if area else 0
    if coverage < 0.80:
        raise RuntimeError(f"Land-cover samples covered only {coverage:.0%} of the footprint; insufficient for comparison.")
    estimates = {key: round(val / valid_area * 100, 1) for key, val in groups.items()}
    named = dict(sorted(((k, round(v / valid_area * 100, 1)) for k, v in classes.items()), key=lambda p: -p[1]))
    return {"year": NLCD_YEAR, "sample_points": len(seen), "grid_spacing_m": round(step),
            "coverage_pct": round(coverage * 100, 1), "land_pct": estimates,
            "classes_pct": named, "natural_est_acres": round(area * (groups.get("natural", 0) + groups.get("wetland", 0)) / valid_area * AREA_TO_ACRES, 2),
            "already_developed_pct": estimates.get("developed", 0),
            "method": "systematic grid samples of ~30 m categorical land-cover raster; approximate"}


def get_wetlands(polygon):
    site_xy = transform(TO_EQUAL, polygon)
    search_region = transform(FROM_EQUAL, site_xy.buffer(SEARCH_RADIUS_M))
    common = {
        "where": "1=1", "geometry": json.dumps(esri_rings(search_region)),
        "geometryType": "esriGeometryPolygon", "inSR": "4326", "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "returnGeometry": "true",
    }
    count = requests_json(NWI_URL, {**common, "returnCountOnly": "true", "f": "json"}).get("count")
    if not isinstance(count, int):
        raise RuntimeError("NWI did not confirm how many map features were found.")
    if count > 800:
        raise RuntimeError(f"More than 800 mapped aquatic features near site ({count}); refine footprint or use desktop GIS.")
    if count == 0:
        return {"overlap_acres": 0, "nearest_m": None, "nearby_count": 0, "features": [],
                "message": "No NWI aquatic features returned within 500 m; unmapped wetlands may exist."}
    result = requests_json(NWI_URL, {**common, "f": "geojson", "outFields": "*",
                                     "resultRecordCount": str(count + 1)})
    feats = result.get("features")
    if not isinstance(feats, list) or len(feats) < count:
        raise RuntimeError("NWI returned incomplete geometry; cannot establish wetland overlap reliably.")
    geom_xy = []
    features = []
    for f in feats:
        try:
            geom = shape(f["geometry"])
            if not geom.is_valid:
                geom = geom.buffer(0)
            if geom.is_empty:
                continue
            geom_xy.append(transform(TO_EQUAL, geom))
            props = f.get("properties") or {}
            wet_type = next((str(v) for k, v in props.items() if k.endswith("WETLAND_TYPE")), "NWI aquatic feature")
            features.append({"type": "Feature", "geometry": f["geometry"],
                             "properties": {"feature_type": wet_type}})
        except (TypeError, ValueError, KeyError):
            raise RuntimeError("NWI geometry could not be interpreted.")
    if not geom_xy:
        raise RuntimeError("NWI returned records but no usable aquatic geometry.")
    union = unary_union(geom_xy)
    overlap_acres = round(union.intersection(site_xy).area * AREA_TO_ACRES, 3)
    nearest = min(site_xy.distance(g) for g in geom_xy)
    return {"overlap_acres": overlap_acres, "nearest_m": round(nearest),
            "nearby_count": len(geom_xy), "features": features,
            "message": "NWI polygons are mapped aquatic features, including wetlands, ponds, lakes and rivers."}


def screening_flag(land: dict | None, wet: dict | None) -> tuple[str, str]:
    if land is None or wet is None:
        return "GRAY", "One or both required geographic datasets could not be verified."
    if wet["overlap_acres"] > 0:
        return "RED", "Proposed footprint overlaps a mapped NWI aquatic feature."
    if land["land_pct"].get("wetland", 0) > 1:
        return "RED", "USGS land cover identifies wetland pixels within the proposed footprint."
    if (land["land_pct"].get("natural", 0) + land["land_pct"].get("wetland", 0) >= 10
            or land.get("natural_est_acres", 0) >= 1):
        return "YELLOW", "Mapped natural vegetation would be affected; site-specific ecological review needed."
    if wet["nearest_m"] is not None and wet["nearest_m"] < 100:
        return "YELLOW", "A mapped aquatic feature is within 100 m; runoff and buffers need review."
    return "GREEN", "No major concern found in these two mapped layers; other ecological factors are NOT evaluated."



def site_grade(land: dict | None, wet: dict | None) -> dict:
    """Educational *absolute* grades for two-layer ecological screening.

    A/B/C/D/F classify modeled habitat conversion and mapped aquatic proximity,
    NOT overall biodiversity, site feasibility, or regulatory approval.
    Thresholds are transparent prototype choices, not validated ecological cutoffs.
    Never grade an incomplete data response.
    """
    if land is None or wet is None:
        return {
            "grade": "N/A", "label": "Not graded",
            "headline": "Environmental data incomplete",
            "explanation": "One or both required map layers could not be checked. No letter grade is assigned until both are available.",
            "reason_code": "missing_data",
        }

    pct_by_type = land.get("land_pct") or {}
    natural_pct = float(pct_by_type.get("natural", 0) or 0) + float(pct_by_type.get("wetland", 0) or 0)
    wetland_pct = float(pct_by_type.get("wetland", 0) or 0)
    natural_acres = float(land.get("natural_est_acres", 0) or 0)
    overlap_acres = float(wet.get("overlap_acres", 0) or 0)
    nearest_m = wet.get("nearest_m")
    nearest_m = float(nearest_m) if nearest_m is not None else None

    habitat = f"Approximately {natural_acres:.2f} acres ({natural_pct:.1f}%) of the footprint are mapped as natural or wetland cover."
    if overlap_acres > 0:
        return {
            "grade": "F", "label": "Major ecological concern",
            "headline": "Mapped aquatic habitat overlap",
            "explanation": f"The footprint overlaps approximately {overlap_acres:.2f} acres of mapped aquatic features. Consider alternative sites and seek an ecological review before proceeding.",
            "reason_code": "aquatic_overlap",
        }
    if wetland_pct > 1:
        return {
            "grade": "F", "label": "Major ecological concern",
            "headline": "Mapped wetland land cover",
            "explanation": f"USGS land-cover estimates indicate {wetland_pct:.1f}% wetland cover inside this footprint. Wetland conversion warrants specialist review and investigation of alternatives.",
            "reason_code": "wetland_landcover",
        }
    if natural_pct >= 60 or natural_acres >= 10:
        return {
            "grade": "F", "label": "Major ecological concern",
            "headline": "Extensive mapped habitat conversion",
            "explanation": f"{habitat} This degree of potential habitat conversion makes the site a poor option in this preliminary screening.",
            "reason_code": "extensive_natural_cover",
        }
    if natural_pct >= 30 or natural_acres >= 3:
        return {
            "grade": "D", "label": "High ecological concern",
            "headline": "Substantial potential habitat loss",
            "explanation": f"{habitat} A location requiring less natural cover disturbance would generally be preferable.",
            "reason_code": "substantial_natural_cover",
        }
    if natural_pct >= 10 or natural_acres >= 1:
        return {
            "grade": "C", "label": "Meaningful ecological concern",
            "headline": "Natural habitat disturbance",
            "explanation": f"{habitat} A site-specific review is needed to understand its ecological value before building.",
            "reason_code": "moderate_natural_cover",
        }
    if wetland_pct > 0:
        return {
            "grade": "C", "label": "Meaningful ecological concern",
            "headline": "Possible wetland habitat within footprint",
            "explanation": f"USGS samples suggest {wetland_pct:.1f}% wetland cover within the footprint, although NWI overlap was not identified. Check the wetland boundary and ecological significance on site.",
            "reason_code": "possible_wetland",
        }
    if nearest_m is not None and nearest_m < 100:
        return {
            "grade": "C", "label": "Meaningful ecological concern",
            "headline": "Near mapped aquatic habitat",
            "explanation": f"The nearest mapped aquatic feature is about {nearest_m:.0f} meters away. Investigate runoff, drainage and appropriate buffers even though the footprint has no mapped NWI overlap.",
            "reason_code": "near_aquatic",
        }
    if natural_pct >= 2 or natural_acres >= 0.25 or (nearest_m is not None and nearest_m < 250):
        if nearest_m is not None and nearest_m < 250:
            detail = f"The nearest mapped aquatic feature is about {nearest_m:.0f} meters away."
        else:
            detail = habitat
        return {
            "grade": "B", "label": "Relatively low mapped concern",
            "headline": "Promising, with some considerations",
            "explanation": f"{detail} The footprint has comparatively limited documented concerns in these two map layers, but field review is still needed.",
            "reason_code": "minor_concerns",
        }
    return {
        "grade": "A", "label": "Lowest mapped concern",
        "headline": "Promising location for further review",
        "explanation": f"Only about {natural_acres:.2f} acres ({natural_pct:.1f}%) are mapped as natural or wetland cover, with no mapped aquatic feature within 250 meters. This makes the site a strong candidate for the next screening stage.",
        "reason_code": "limited_mapped_impact",
    }


GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4, "N/A": 5}


def compare_sites(rows: list[dict]) -> list[dict]:
    """Sort with conservative 'screen first' rule, never a weighted biodiversity score."""
    eligible = [r for r in rows if r.get("flag") in ("GREEN", "YELLOW") and r.get("land") and r.get("wet")]
    return sorted(eligible, key=lambda r: (
        0 if r["flag"] == "GREEN" else 1,
        r["land"]["natural_est_acres"],
        -(r["wet"]["nearest_m"] or 0),
    ))


def analyze_site(feature: dict):
    geom = ensure_polygon(feature)
    issues = {}
    land, wet = None, None
    try:
        land = get_land_cover(geom)
    except Exception as e:
        issues["land_cover"] = str(e)
    try:
        wet = get_wetlands(geom)
    except Exception as e:
        issues["nwi"] = str(e)
    flag, reason = screening_flag(land, wet)
    grade = site_grade(land, wet)
    return {"area_acres": round(acres_of(geom), 2), "flag": flag, "grade": grade,
            "reason": reason, "land": land, "wet": wet, "issues": issues,
            "analyzed_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "NLCD land cover and mapped NWI aquatic features only; 5 other ecological factors unassessed"}
