"""UI-neutral experience helpers for EcoSite AI V8.

Demo measurements are synthetic by design: never present them as GIS findings.
Preferred-site narrative is evidence-limited and cannot be used for permits.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isclose
from uuid import uuid4

from shapely.geometry import box, mapping

from model import NLCD_YEAR, acres_of, compare_sites, ensure_polygon, screening_flag, site_grade

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4, "N/A": 5}


def next_site_name(sites: list[dict]) -> str:
    """Name rectangles A-E; gaps are reused only if a middle site was removed."""
    used = {site.get("name", "") for site in sites}
    return next((f"Site {chr(65+i)}" for i in range(5) if f"Site {chr(65+i)}" not in used), "Site (limit reached)")


def wizard_step(sites: list[dict], results: dict) -> int:
    if results and len(sites) >= 2:
        return 3
    if len(sites) >= 2:
        return 2
    return 1


def _feature(cx: float, cy: float, dx: float = .00155, dy: float = .00150) -> dict:
    polygon = box(cx-dx/2, cy-dy/2, cx+dx/2, cy+dy/2)
    return {"type": "Feature", "geometry": mapping(polygon), "properties": {}}


def make_demo() -> tuple[list[dict], dict]:
    """Three *fictitious* footprints and hardcoded synthetic values.

    Coordinates are for illustrative drawing ONLY, not a statement about land
    use at the depicted places. The UI, CSV and PDF must label this clearly.
    """
    configs = [
        ("Site A", -92.466, 42.529, 1.0, 0., 420., 0.),
        ("Site B", -92.443, 42.548, 20., 0., 75., 0.),
        ("Site C", -92.417, 42.521, 63., 8., 0., .32),
    ]
    sites, results = [], {}
    for label, lon, lat, natural_pct, wetland_pct, distance_m, overlap in configs:
        feature = _feature(lon, lat)
        area = round(acres_of(ensure_polygon(feature)), 2)
        site = {"id": f"demo-{label[-1].lower()}", "name": label,
                "feature": feature, "demo": True}
        sites.append(site)
        natural_acres = round(area*(natural_pct+wetland_pct)/100., 2)
        land = {
            "natural_est_acres": natural_acres,
            "land_pct": {"natural": natural_pct, "wetland": wetland_pct},
            "already_developed_pct": max(0., 100-natural_pct-wetland_pct),
            "classes_pct": {"developed (synthetic)": max(0., 100-natural_pct-wetland_pct),
                            "natural (synthetic)": natural_pct, "wetland (synthetic)": wetland_pct},
            "sample_points": 0, "grid_spacing_m": None, "year": "synthetic",
        }
        wet = {"overlap_acres": overlap, "nearest_m": distance_m,
               "nearby_count": 1, "features": [],
               "message": "Synthetic data for user-interface demonstration; not queried from USFWS."}
        flag, reason = screening_flag(land, wet)
        results[site["id"]] = {
            "area_acres": area, "flag": flag, "reason": reason,
            "grade": site_grade(land, wet), "land": land, "wet": wet,
            "issues": {}, "demo": True,
            "analyzed_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "FICTITIOUS teaching example, not GIS measurements",
        }
    return sites, results


def best_preliminary_option(sites: list[dict], results: dict) -> dict:
    """Return a conservative, two-observation recommendation or no-leader note.

    Never rank when required data are absent. Never promote a RED site as best.
    A tie in grade and materially similar measurements is not a distinguishable
    best site simply because compare_sites has a stable sort order.
    """
    if len(sites) < 2 or any(site["id"] not in results for site in sites):
        return {"winner": None, "reason": "Compare at least two saved locations first."}
    completed = [(s, results[s["id"]]) for s in sites]
    if any(r.get("grade", {}).get("grade") == "N/A" or not r.get("land") or not r.get("wet") for _, r in completed):
        return {"winner": None, "reason": "A required land-cover or aquatic map layer was unavailable. Resolve missing data before selecting a site."}
    rows = [{"id": s["id"], "name": s["name"], "flag": r["flag"],
             "land": r["land"], "wet": r["wet"]} for s, r in completed]
    ranked = compare_sites(rows)
    if not ranked:
        return {"winner": None, "reason": "Every candidate has a major mapped concern. Investigate additional alternatives rather than selecting a winner."}
    candidate = ranked[0]
    winner_site, result = next((s, r) for s, r in completed if s["id"] == candidate["id"])
    runner_candidates = [r for s, r in completed if s["id"] != candidate["id"]]
    # A unique leader requires a difference in screening grade or material
    # landscape data; do not make up precision from a tiny tie-breaker.
    best_other_grade = min(GRADE_ORDER[r["grade"]["grade"]] for r in runner_candidates)
    candidate_grade = GRADE_ORDER[result["grade"]["grade"]]
    competitor = min(runner_candidates, key=lambda r: GRADE_ORDER[r["grade"]["grade"]])
    land1, land2 = result["land"], competitor["land"]
    near1, near2 = result["wet"].get("nearest_m"), competitor["wet"].get("nearest_m")
    close_scores = (
        candidate_grade == best_other_grade
        and result["flag"] == competitor["flag"]
        and abs(float(land1["natural_est_acres"])-float(land2["natural_est_acres"])) < .25
        and abs(float(land1["already_developed_pct"])-float(land2["already_developed_pct"])) < 3
        and (near1 is None or near2 is None or abs(float(near1)-float(near2)) < 50)
        and isclose(float(result["wet"]["overlap_acres"]), float(competitor["wet"]["overlap_acres"]), abs_tol=.01)
    )
    if close_scores:
        return {"winner": None, "reason": "The leading sites have similar mapped concerns. This screening cannot reliably distinguish a single best option."}
    natural = float(land1["natural_est_acres"])
    natural_pct = float(land1["land_pct"].get("natural", 0))+float(land1["land_pct"].get("wetland", 0))
    reasons = [f"About {natural:.2f} acres ({natural_pct:.1f}%) of the footprint are mapped as natural or wetland cover."]
    overlap = float(result["wet"]["overlap_acres"])
    if overlap == 0:
        if near1 is None:
            reasons.append("No mapped NWI aquatic feature was returned within the 500 m search area; this does not rule out unmapped wetlands.")
        else:
            reasons.append(f"No mapped aquatic overlap was found; the nearest mapped aquatic feature is approximately {near1:.0f} m away.")
    else:
        reasons.append(f"Mapped aquatic overlap was estimated at {overlap:.2f} acres.")
    return {"winner": winner_site, "result": result, "reasons": reasons,
            "reason": "A first location to investigate, not a finding that construction is safe or permitted."}


FRIENDLY_ERRORS = {
    "town": ("We couldn't find that community.", "Check the spelling and include a state, such as Cedar Falls, Iowa. If the search service is temporarily unavailable, try again."),
    "draw": ("The location was not saved.", "Draw a rectangle using the small square tool in the top-left of the map, then choose Add location."),
    "compare": ("The comparison couldn't finish.", "Check that two to five rectangles are saved, then try Compare my locations again. Online environmental data may be temporarily unavailable."),
    "restore": ("We couldn't analyze that restoration area.", "Choose a rectangle outside the construction footprint, check the selected restoration option, and try again."),
    "pdf": ("The printable report couldn't be created.", "Try the download again. Your comparison remains saved on this page."),
}


def friendly_error(kind: str) -> tuple[str, str]:
    return FRIENDLY_ERRORS.get(kind, ("That action couldn't finish.", "Try again or check the selected locations."))
