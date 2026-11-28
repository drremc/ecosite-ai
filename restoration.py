"""Evidence-limited habitat restoration *opportunity* screening for EcoSite AI.

This module does not calculate biodiversity credits, replacement ratios, ecosystem
condition, or proof of ecological equivalence. It separates physically available
mapped cover from site-specific ecological suitability, which requires fieldwork.
"""
from __future__ import annotations

from datetime import datetime, timezone

from shapely.ops import transform
from model import TO_EQUAL, acres_of, ensure_polygon, get_land_cover, get_wetlands

# An explicit geometric screening definition, not an ecological setback requirement.
NEAR_SITE_MAX_M = 500.0
# Allow a one-square-meter sliver for rounding/topology errors, never material overlap.
GEOMETRY_TOLERANCE_SQM = 1.0


def validate_restoration_area(
    build_feature: dict,
    restoration_feature: dict,
    mode: str,
    alternate_feature: dict | None = None,
) -> dict:
    """Validate placement of a *separate* restoration polygon.

    mode='nearby' requires proximity to a development footprint and no overlap.
    mode='alternate' requires restoration area within a different unused candidate.
    Regardless of mode, land already counted as converted cannot be counted again.
    """
    if mode not in ('nearby', 'alternate'):
        raise ValueError('Choose a valid restoration option.')
    build = transform(TO_EQUAL, ensure_polygon(build_feature))
    restore = transform(TO_EQUAL, ensure_polygon(restoration_feature))
    overlap = build.intersection(restore).area
    if overlap > GEOMETRY_TOLERANCE_SQM:
        raise ValueError(
            'The restoration area overlaps the proposed construction footprint. '
            'Draw a separate area outside the construction footprint, or revise the construction footprint.'
        )
    distance_m = build.distance(restore)
    if mode == 'nearby':
        if distance_m > NEAR_SITE_MAX_M:
            raise ValueError('For the nearby option, draw the restoration area within 500 meters of the building footprint.')
    else:
        if alternate_feature is None:
            raise ValueError('Choose one of the other candidate sites for restoration.')
        alternate = transform(TO_EQUAL, ensure_polygon(alternate_feature))
        outside_area = restore.difference(alternate).area
        if outside_area > max(GEOMETRY_TOLERANCE_SQM, restore.area * 0.01):
            raise ValueError('For this option, draw the restoration area inside the selected unused candidate site.')
    return {
        'area_acres': round(acres_of(ensure_polygon(restoration_feature)), 2),
        'distance_from_build_m': round(distance_m),
        'mode': mode,
        'separate_from_construction': True,
    }


def analyze_restoration_area(feature: dict) -> dict:
    """Use map services for the restoration polygon without assigning a build-site grade."""
    polygon = ensure_polygon(feature)
    issues = {}
    land = wet = None
    try:
        land = get_land_cover(polygon)
    except Exception as exc:
        issues['land_cover'] = str(exc)
    try:
        wet = get_wetlands(polygon)
    except Exception as exc:
        issues['aquatic_layer'] = str(exc)
    return {
        'area_acres': round(acres_of(polygon), 2),
        'land': land,
        'wet': wet,
        'issues': issues,
        'analyzed_utc': datetime.now(timezone.utc).isoformat(),
    }


def _action(title: str, rationale: str, verify: str, step: str = 'Restore') -> dict:
    return {'title': title, 'rationale': rationale, 'verify': verify, 'step': step}


def make_restoration_plan(development: dict, restoration: dict, context: dict, *,
                          development_name: str, location_name: str) -> dict:
    """Conservative, conditional guidance based on actual mapped class percentages.

    NWI features may also include open water: do not call all NWI features wetlands.
    Potentially modifiable mapped cover is not proven restorable land or credits.
    """
    land = restoration.get('land')
    wet = restoration.get('wet')
    acres = float(context['area_acres'])
    actions = []
    warnings = []
    potential_area = None
    cover = (land or {}).get('land_pct') or {}
    developed_open_pct = max(0.0, float(cover.get('developed_open', 0) or 0))
    ag_pct = max(0.0, float(cover.get('agriculture', 0) or 0))
    natural_pct = max(0.0, float(cover.get('natural', 0) or 0))
    wetland_pct = max(0.0, float(cover.get('wetland', 0) or 0))
    hard_pct = max(0.0, float(cover.get('developed', 0) or 0))

    if land is None:
        warnings.append('Land-cover service unavailable: no mapped planting-opportunity area can be estimated.')
        actions.append(_action(
            'Survey the restoration polygon before choosing plants',
            'Identify actual pavement, mowed turf, crops, native vegetation, drainage, and invasive species first.',
            'On-site walk-through, landowner consent, and a local ecological reference habitat.',
            'Assess',
        ))
    else:
        # This is NOT a planting target; it can include occupied land and non-native pasture.
        modifiable_pct = min(100.0, developed_open_pct + ag_pct)
        potential_area = round(acres * modifiable_pct / 100, 2)
        if developed_open_pct >= 2:
            actions.append(_action(
                'Investigate converting suitable lawn or open developed space to native habitat',
                f'Approximately {developed_open_pct:.1f}% of this polygon is mapped as developed open space. '
                'Appropriate portions of managed turf could support locally suitable native flowering plants and grasses.',
                'Confirm it is actually turf or nonessential maintained open space; check buried utilities, safety setbacks, soils and sunlight.',
            ))
        if ag_pct >= 2:
            actions.append(_action(
                'Evaluate habitat enhancement on agricultural or pasture cover',
                f'Approximately {ag_pct:.1f}% is mapped as cropland or pasture/hay. '
                'Some portions might support native plant communities where land use and site conditions permit.',
                'Identify whether land is cultivated, pasture, or valuable existing grassland; confirm landowner permission, soils, hydrology and plant-community fit.',
            ))
        if hard_pct >= 10:
            actions.append(_action(
                'Explore selective depaving and green infrastructure',
                f'Approximately {hard_pct:.1f}% is mapped as developed land. In suitable areas, removing unnecessary hard surfaces may enable habitat and runoff improvements.',
                'Check infrastructure, contaminants, safety access, engineering feasibility and actual available area. Do not assume paved acres are plantable.',
                'Minimize',
            ))
        if natural_pct + wetland_pct >= 2:
            actions.append(_action(
                'Protect existing natural vegetation instead of replacing it',
                f'Approximately {natural_pct + wetland_pct:.1f}% is mapped as natural or wetland land cover. '
                'Protecting these areas and preventing fragmentation should come before new planting.',
                'Determine actual habitat quality and whether rare species or sensitive communities are present. Avoid converting native prairie to trees.',
                'Avoid',
            ))
        if not any(a['step'] == 'Restore' for a in actions):
            actions.append(_action(
                'Identify restoration opportunities through a site visit',
                'The available land-cover categories do not establish a clear area for new native planting.',
                'Map actual turf, degraded soil, fill, disturbed land, and any habitats worth protecting.',
                'Assess',
            ))

    if wet is None:
        warnings.append('USFWS aquatic layer unavailable: the site has not been cleared for wetland or stream conflicts.')
    else:
        near = wet.get('nearest_m')
        if float(wet.get('overlap_acres', 0) or 0) > 0 or (near is not None and near < 100):
            actions.append(_action(
                'Investigate streamside or wetland-adjacent protection',
                'Mapped aquatic habitat overlaps the restoration area or lies close to it. Carefully designed buffers and runoff controls may be beneficial.',
                'Confirm hydrology, mapped-feature type and applicable permits before earthwork or planting in or near wetlands and waters.',
                'Avoid',
            ))
            warnings.append('A mapped aquatic feature is within or very near the restoration area; planting or grading may require specialist review and permits.')
        elif near is not None and near < 500:
            actions.append(_action(
                'Consider runoff and watershed-friendly native landscaping',
                'A mapped aquatic feature lies within the surrounding 500 m screening zone. Native planting and runoff management may help where properly located.',
                'Trace actual drainage flow and check stormwater plans before identifying a vegetated buffer.',
                'Minimize',
            ))

    actions.append(_action(
        'Use locally appropriate native species and commit to long-term management',
        'Restoration should target a suitable local reference ecosystem, not an arbitrary tree or wildflower mix. '
        'Monitor establishment and ecological condition instead of counting planting alone as success.',
        'Have a local ecologist or extension specialist select species, plan establishment and invasive-species management, and set a multi-year monitoring schedule.',
        'Restore',
    ))
    actions.append(_action(
        'Avoid or shrink the construction footprint before relying on restoration',
        'Restoration does not erase the impact of developing intact habitats, and ecological equivalence has not been established.',
        'Revisit site alternatives and quantify residual impacts with qualified conservation professionals.',
        'Avoid',
    ))

    # Preserve the original construction screening findings for context.
    build_grade = ((development.get('grade') or {}).get('grade') or 'N/A')
    build_land = development.get('land')
    build_natural_acres = (build_land.get('natural_est_acres') if build_land else None)
    if build_grade in ('D', 'F'):
        warnings.append(f'The selected development site received grade {build_grade}. Restoration is not a reason to disregard a high-impact alternative-location warning.')
    warnings.append('Potentially modifiable mapped cover is not verified available acreage, biodiversity gain, or a certified offset.')
    warnings.append('Land ownership, permissions, soil contamination, hydrology, invasive species, establishment success, and long-term protection have not been verified.')
    # Use the mitigation hierarchy in the presentation order; no action or plant mix
    # is intended as an automatic compensation or construction approval.
    sequence = {'Avoid': 0, 'Minimize': 1, 'Assess': 2, 'Restore': 3}
    actions.sort(key=lambda action: sequence.get(action['step'], 4))

    return {
        'development_name': development_name,
        'development_grade': build_grade,
        'development_mapped_natural_acres': build_natural_acres,
        'restoration_location': location_name,
        'mode': context['mode'],
        'restoration_acres': acres,
        'distance_from_build_m': context['distance_from_build_m'],
        'estimated_modifiable_cover_acres': potential_area,
        'estimated_modifiable_cover_pct': round(min(100.0, developed_open_pct + ag_pct), 1) if land else None,
        'mapped_existing_natural_or_wetland_pct': round(natural_pct + wetland_pct, 1) if land else None,
        'actions': actions,
        'warnings': warnings,
        'issues': restoration.get('issues') or {},
        'land_cover_year': (land or {}).get('year'),
        'nwi_status': 'checked' if wet is not None else 'unavailable',
        'net_biodiversity_gain': None,
        'verified_offset': False,
        'basis': 'USGS NLCD categorical land cover, USFWS NWI aquatic layer, conditional ecological practice guidance',
    }


def plan_markdown(plan: dict) -> str:
    """Downloadable, human-readable report with all data gaps and no net-gain claims."""
    label = ('Adjacent / nearby restoration land' if plan['mode'] == 'nearby'
             else 'Different candidate site')
    mod = (f"~{plan['estimated_modifiable_cover_acres']:.2f} acres "
           if plan['estimated_modifiable_cover_acres'] is not None else 'Unavailable')
    lines = [
        '# EcoSite AI — Restoration Opportunity Report',
        '',
        f"**Development location:** {plan['development_name']}",
        f"**Construction screening grade:** {plan['development_grade']}",
        ('**Mapped natural/wetland cover within building footprint:** '
         + (f"~{plan['development_mapped_natural_acres']:.2f} acres"
            if plan['development_mapped_natural_acres'] is not None else 'Unavailable')),

        f"**Restoration location:** {plan['restoration_location']}",
        f'**Approach:** {label}',
        f"**Area examined:** {plan['restoration_acres']:.2f} acres (mapped polygon)",
        f'**Potentially modifiable mapped land cover:** {mod}',
        '',
        '> This is only an area estimate using coarse land-cover categories, not an estimate of '
        'actual feasible planting acreage or an ecological offset.',
        '',
        '## Proposed steps to investigate',
    ]
    for n, item in enumerate(plan['actions'], 1):
        lines.extend([
            f"### {n}. {item['title']} ({item['step']})", item['rationale'],
            f"**What to verify:** {item['verify']}", '',
        ])
    lines.extend(['## Key limitations / warnings', *[f'- {x}' for x in plan['warnings']], ''])
    if plan['issues']:
        lines.extend(['## Map service issues', *[f'- {k}: {v}' for k, v in plan['issues'].items()], ''])
    lines.extend([
        '## Scientific framework and sources',
        '- Society for Ecological Restoration, International Principles and Standards, 3rd ed. (2026): https://www.ser.org/page/serstandards',
        '- IUCN, Biodiversity Offsets and the mitigation hierarchy: https://iucn.org/resources/issues-brief/biodiversity-offsets',
        '- USGS Annual NLCD: https://www.usgs.gov/centers/eros/science/annual-national-land-cover-database',
        '- USFWS NWI: https://www.fws.gov/program/national-wetlands-inventory/web-mapping-services',
        '',
        '**Not a mitigation credit, regulatory determination, engineering plan, or approved offset.**',
    ])
    return '\n'.join(lines)
