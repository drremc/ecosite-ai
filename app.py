"""EcoSite AI: polished, transparent preliminary GIS comparison website."""
from __future__ import annotations

import csv
from html import escape
import io
import json
import uuid

import folium
import requests
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import mapping
from streamlit_folium import st_folium

from model import NLCD_YEAR, analyze_site, compare_sites, ensure_polygon

st.set_page_config(
    page_title="EcoSite AI | Biodiversity site comparison",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """<style>
    :root {--ink:#142f34;--teal:#146256;--pale:#e9f5ef;--gold:#eaa452;--muted:#5f7477;}
    .stApp {background:#f7faf8;}
    .block-container {padding-top:1.45rem; padding-bottom:3.5rem; max-width:1480px;}
    [data-testid="stSidebar"] {background: #eef5f0; border-right:1px solid #d9e7df;}
    h1,h2,h3,p {overflow-wrap:anywhere;}
    h2 {font-size:1.45rem !important; letter-spacing:-.03em; color:var(--ink);}
    [data-testid="stVerticalBlockBorderWrapper"] {border-color:#dce9e2 !important;}
    .hero {position:relative;overflow:hidden;background:linear-gradient(116deg,#102f33 0%,#14584f 69%,#277a65 100%);color:#fff;border-radius:22px;padding:34px 40px 38px;margin:4px 0 20px;box-shadow:0 12px 40px rgba(11,65,53,.10);}
    .hero:after {content:"";position:absolute;width:280px;height:280px;border:1px solid rgba(255,255,255,.15);border-radius:50%;right:-72px;top:-84px;box-shadow:0 0 0 50px rgba(255,255,255,.025),0 0 0 102px rgba(255,255,255,.025);pointer-events:none;}
    .hero .eyebrow {font-size:.71rem;font-weight:780;letter-spacing:.19em;text-transform:uppercase;color:#bfe8d5;margin-bottom:11px;}
    .hero h1 {font-size:clamp(2.2rem,4vw,3.45rem);font-weight:810;letter-spacing:-.065em;line-height:1.06;margin:0 0 12px;color:white;}
    .hero h1 em {font-style:normal;color:#d9f4b2;}
    .hero p {max-width:780px;color:#ddede6;font-size:1.02rem;line-height:1.6;margin:0 0 19px;}
    .chips {display:flex;flex-wrap:wrap;gap:9px;}
    .chip {border-radius:30px;border:1px solid rgba(255,255,255,.26);font-size:.77rem;font-weight:650;padding:6px 12px;color:#eaf8ef;}
    .meta-strip {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:21px;}
    .meta {background:#fff;border:1px solid #dfeae3;border-radius:14px;padding:14px 18px;box-shadow:0 2px 6px rgba(16,59,47,.02)}
    .meta .caption {font-size:.74rem;font-weight:670;color:#667e7a;letter-spacing:.03em;text-transform:uppercase;}
    .meta .value {font-size:1.4rem;font-weight:800;color:#1a4c46;margin-top:2px;line-height:1.25;}
    .section-head {display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px;margin-top:10px;}
    .section-head h2 {margin:0;font-size:1.38rem!important;}
    .section-head p {margin:3px 0 0;font-size:.86rem;color:#6c807b;}
    .section-pill {color:#1e6557;background:#e1f1e6;border-radius:30px;padding:6px 10px;white-space:nowrap;font-size:.75rem;font-weight:700;}
    .site-list {display:grid;gap:10px;margin:10px 0;}
    .site-mini {background:#fff;border:1px solid #dfeae4;border-radius:13px;padding:14px 16px;display:flex;gap:12px;align-items:start;}
    .site-dot {width:12px;height:12px;min-width:12px;border-radius:50%;margin-top:5px;}
    .site-title {color:#143a38;font-size:.95rem;font-weight:730;margin-bottom:3px;}
    .site-sub {color:#697d78;font-size:.8rem;line-height:1.45;}
    .grade-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:14px 0 22px;}
    .grade-card {background:white;border:1px solid #dce8e1;border-top:5px solid var(--grade-accent);border-radius:16px;padding:20px 20px 18px;min-width:0;box-shadow:0 6px 22px rgba(23,64,56,.045);}
    .grade-card .top {display:flex;justify-content:space-between;gap:6px;align-items:center;margin-bottom:11px;}
    .grade-card .site {font-weight:800;font-size:1rem;color:#183a39;}
    .grade-card .grade {font-size:3.5rem;letter-spacing:-.09em;font-weight:840;color:var(--grade-accent);line-height:1;}
    .grade-card .tag {background:var(--grade-bg);color:var(--grade-accent);font-weight:770;font-size:.72rem;padding:5px 9px;border-radius:99px;}
    .grade-card .heading {color:#203b39;font-size:.98rem;font-weight:780;margin:13px 0 6px;}
    .grade-card .reason {color:#596d6b;font-size:.86rem;line-height:1.58;margin:0;min-height:85px;}
    .grade-card .measure {margin-top:15px;padding-top:12px;border-top:1px solid #e6eee8;color:#627571;font-size:.75rem;line-height:1.55;}
    .comparison-banner {display:flex;gap:15px;align-items:center;background:#e9f5ee;border:1px solid #c3dfd0;padding:17px 20px;border-radius:13px;margin:10px 0 18px;color:#154d41;}
    .comparison-banner strong {font-weight:800;}
    .comparison-banner span {display:block;margin-top:3px;font-size:.85rem;line-height:1.5;}
    .notice {background:#fff9ec;border:1px solid #eeddb9;border-radius:12px;padding:12px 15px;color:#6b562f;font-size:.84rem;line-height:1.55;margin:12px 0;}
    .brand {padding:10px 0 3px;font-size:1.28rem;color:#174d42;font-weight:800;letter-spacing:-.035em;}
    .brand-caption {font-size:.73rem;letter-spacing:.12em;color:#66867a;font-weight:700;text-transform:uppercase;margin-bottom:25px;}
    .foot {color:#6a7c76;font-size:.82rem;line-height:1.6;}
    @media(max-width:780px) { .hero{padding:24px 21px}.meta-strip{grid-template-columns:1fr 1fr}.grade-card .reason{min-height:0;} }
    </style>""",
    unsafe_allow_html=True,
)

for key, default in (
    ("sites", []),
    ("results", {}),
    ("center", [42.5349, -92.4453]),
    ("zoom", 12),
    ("community", "Cedar Falls, Iowa"),
):
    if key not in st.session_state:
        st.session_state[key] = default


@st.cache_data(ttl=86400, show_spinner=False)
def geocode(place: str):
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place + ", USA", "format": "jsonv2", "limit": 1},
        headers={"User-Agent": "EcoSite educational demonstration (Streamlit mapping application)"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError("No matching community found. Include city and state.")
    return [float(data[0]["lat"]), float(data[0]["lon"])]


PALETTE = ["#107b6b", "#e99649", "#6d67bf", "#2c74bd", "#c45e8c"]
GRADE_STYLE = {
    "A": ("#138260", "#e0f5e9"),
    "B": ("#268e93", "#e0f2f2"),
    "C": ("#b47927", "#fff2d8"),
    "D": ("#c16a35", "#feebde"),
    "F": ("#ba4650", "#fae7e8"),
    "N/A": ("#758589", "#eff1f1"),
}


def site_card(site: dict, result: dict) -> str:
    g = result["grade"]
    letter = g["grade"]
    ink, pale = GRADE_STYLE[letter]
    name = escape(site["name"])
    headline = escape(g["headline"])
    reason = escape(g["explanation"])
    label = escape(g["label"])
    size = float(result["area_acres"])
    return f'''<article class="grade-card" style="--grade-accent:{ink};--grade-bg:{pale}">
       <div class="top"><div class="site">{name}</div><span class="tag">{label}</span></div>
       <div class="grade">{'—' if letter == 'N/A' else letter}</div>
       <div class="heading">{headline}</div>
       <p class="reason">{reason}</p>
       <div class="measure">{size:.1f} acre footprint · 2 mapped layers only<br>Grade: {escape(letter)} · Not a development approval</div>
       </article>'''


with st.sidebar:
    st.markdown('<div class="brand">🌿 EcoSite AI</div><div class="brand-caption">Site comparison studio</div>', unsafe_allow_html=True)
    st.markdown("### 01 / Find your community")
    query = st.text_input("City and state", st.session_state.community, help="The map initially opens in Cedar Falls, Iowa.")
    if st.button("Find town", use_container_width=True):
        try:
            st.session_state.center = geocode(query)
            st.session_state.community = query
            st.session_state.zoom = 12
            st.rerun()
        except Exception as exc:
            st.error(f"Could not search for this town: {exc}")
    st.divider()
    st.markdown("### 02 / Outline a location")
    st.caption("On the map, use the rectangle or polygon drawing tool. Then add that footprint below the map.")
    new_label = st.text_input(
        "Site name",
        value=f"Site {chr(65 + len(st.session_state.sites))}" if len(st.session_state.sites) < 5 else "New site",
    )
    st.caption(f"{len(st.session_state.sites)} of 5 locations added")
    st.divider()
    st.markdown("### 03 / Run comparison")
    analyze = st.button(
        "Analyze selected sites", type="primary", use_container_width=True,
        disabled=len(st.session_state.sites) < 2,
    )
    st.caption("Select at least 2 sites. Live GIS layers require an internet connection.")
    if st.session_state.sites:
        if st.button("Remove last site", use_container_width=True):
            removed = st.session_state.sites.pop()
            st.session_state.results.pop(removed["id"], None)
            st.rerun()
        if st.button("Clear all", use_container_width=True):
            st.session_state.sites = []
            st.session_state.results = {}
            st.rerun()
    st.divider()
    st.caption("FIRST LEGO LEAGUE · RESEARCH PROTOTYPE · VERSION 2")

st.markdown(
    '''<div class="hero">
      <div class="eyebrow">Environmental intelligence / Site selection</div>
      <h1>Build smarter.<br><em>Protect more nature.</em></h1>
      <p>Compare potential data-center locations using real environmental map layers. See a preliminary letter grade for each site and an easy-to-understand explanation of the ecological concerns.</p>
      <div class="chips"><span class="chip">✓ Map-based evidence</span><span class="chip">✓ A–F site grades</span><span class="chip">✓ Transparent methods</span></div>
    </div>''',
    unsafe_allow_html=True,
)

num_done = sum(1 for s in st.session_state.sites if s["id"] in st.session_state.results)
community = escape(st.session_state.community)
st.markdown(
    f'''<div class="meta-strip">
      <div class="meta"><div class="caption">Current community</div><div class="value">{community}</div></div>
      <div class="meta"><div class="caption">Saved candidate sites</div><div class="value">{len(st.session_state.sites)} / 5</div></div>
      <div class="meta"><div class="caption">Locations analyzed</div><div class="value">{num_done} / {len(st.session_state.sites)}</div></div>
    </div>''',
    unsafe_allow_html=True,
)

left, right = st.columns([1.8, 1], gap="large")
with left:
    st.markdown('''<div class="section-head"><div><h2>Explore & select sites</h2>
        <p>Draw a footprint for each potential data-center location.</p></div>
        <span class="section-pill">Interactive map</span></div>''', unsafe_allow_html=True)
    m = folium.Map(
        location=st.session_state.center,
        zoom_start=st.session_state.zoom,
        tiles="OpenStreetMap",
        control_scale=True,
        prefer_canvas=True,
    )
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, Maxar, Earthstar Geographics and the GIS User Community",
        name="Satellite", overlay=False,
    ).add_to(m)
    for i, site in enumerate(st.session_state.sites):
        group = folium.FeatureGroup(name=site["name"])
        folium.GeoJson(
            site["feature"],
            style_function=lambda _feature, color=PALETTE[i]: {
                "color": color, "weight": 3, "fillColor": color, "fillOpacity": .16,
            },
            tooltip=site["name"],
        ).add_to(group)
        group.add_to(m)
    mapped = []
    for site in st.session_state.sites:
        result = st.session_state.results.get(site["id"], {})
        mapped.extend((result.get("wet") or {}).get("features") or [])
    if mapped:
        folium.GeoJson(
            {"type": "FeatureCollection", "features": mapped},
            name="Mapped NWI aquatic features",
            style_function=lambda _: {"color": "#288fcb", "weight": 1,
                                       "fillColor": "#61b6d6", "fillOpacity": .38},
            tooltip=folium.GeoJsonTooltip(fields=["feature_type"], aliases=["NWI category:"]),
        ).add_to(m)
    Draw(
        export=False,
        draw_options={
            "polyline": False, "marker": False, "circle": False, "circlemarker": False,
            "polygon": {"shapeOptions": {"color": "#145f56"}},
            "rectangle": {"shapeOptions": {"color": "#145f56"}},
        },
        edit_options={"edit": False, "remove": False},
    ).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    map_response = st_folium(
        m, height=510, use_container_width=True, key="ecosite_map",
        returned_objects=["last_active_drawing"],
    )
    drawn = (map_response or {}).get("last_active_drawing")
    if st.button("＋ Add drawn location", use_container_width=True,
                 disabled=len(st.session_state.sites) >= 5):
        if not drawn:
            st.warning("First draw a rectangle or polygon on the map using the top-left toolbar.")
        elif not new_label.strip():
            st.warning("Enter a name for the location in the sidebar.")
        elif any(s["name"].casefold() == new_label.strip().casefold()
                 for s in st.session_state.sites):
            st.warning("Each site needs a different name. Change the site name in the sidebar.")
        else:
            try:
                polygon = ensure_polygon(drawn)
                feature = {"type": "Feature", "geometry": mapping(polygon), "properties": {}}
                st.session_state.sites.append({
                    "id": str(uuid.uuid4()), "name": new_label.strip(), "feature": feature,
                })
                st.session_state.results = {}  # old comparisons are stale after a new site
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.caption("Draw hypothetical footprints, not just map pins. The site map covers the contiguous U.S.; real-world construction would require parcel, zoning and engineering checks.")

with right:
    st.markdown('''<div class="section-head"><div><h2>Your locations</h2>
      <p>Choose 2–5 places to compare side by side.</p></div></div>''', unsafe_allow_html=True)
    if not st.session_state.sites:
        st.info("To begin: use the rectangle or polygon icon on the map, outline Site A, then click **Add drawn location**. Repeat for Site B.")
    else:
        entries = []
        for i, site in enumerate(st.session_state.sites):
            result = st.session_state.results.get(site["id"])
            if result:
                label = f"Grade {result['grade']['grade']} · {result['area_acres']:.1f} acres"
            else:
                label = "Footprint saved · Ready to analyze"
            entries.append(
                f'<div class="site-mini"><span class="site-dot" style="background:{PALETTE[i]}"></span>'
                f'<div><div class="site-title">{escape(site["name"])}</div>'
                f'<div class="site-sub">{escape(label)}</div></div></div>'
            )
        st.markdown('<div class="site-list">' + ''.join(entries) + '</div>', unsafe_allow_html=True)
    st.markdown("#### What the first version checks")
    st.markdown("**USGS land cover:** estimates natural or wetland cover inside each footprint.")
    st.markdown("**USFWS wetlands inventory:** checks mapped aquatic overlap and nearby features (within 500 m).")
    st.markdown('''<div class="notice"><strong>Research preview:</strong> The A–F grades are based only on these two mapped layers. They do not assess threatened species, connectivity, water use, utilities or noise, and do not establish whether construction is safe or permitted.</div>''', unsafe_allow_html=True)

if analyze:
    new_results = {}
    progress = st.progress(0, text="Requesting live environmental map data…")
    for i, site in enumerate(st.session_state.sites):
        with st.spinner(f"Analyzing {site['name']}…"):
            new_results[site["id"]] = analyze_site(site["feature"])
        progress.progress((i + 1) / len(st.session_state.sites),
                          text=f"Completed {i + 1} of {len(st.session_state.sites)}")
    st.session_state.results = new_results
    st.rerun()

if st.session_state.results:
    st.divider()
    st.markdown('''<div class="section-head"><div><h2>Comparison results</h2>
       <p>Each site receives a preliminary environmental letter grade and an explanation.</p>
       </div><span class="section-pill">A = lower concern · F = higher concern</span></div>''', unsafe_allow_html=True)
    completed = [(s, st.session_state.results[s["id"]]) for s in st.session_state.sites
                 if s["id"] in st.session_state.results]
    st.markdown('<div class="grade-grid">' + ''.join(site_card(s, r) for s, r in completed) + '</div>',
                unsafe_allow_html=True)

    rows_for_ranking = []
    report = []
    for site, result in completed:
        land = result["land"]
        wet = result["wet"]
        grade = result["grade"]
        rows_for_ranking.append({"id": site["id"], "name": site["name"],
                                 "flag": result["flag"], "land": land, "wet": wet})
        report.append({
            "Site": site["name"],
            "Preliminary grade": grade["grade"],
            "Why this grade": grade["explanation"],
            "Footprint (acres)": result["area_acres"],
            "Estimated mapped natural / wetland cover (acres)":
                land["natural_est_acres"] if land else "Unknown",
            "Developed cover (%)": land["already_developed_pct"] if land else "Unknown",
            "NWI aquatic overlap (acres)": wet["overlap_acres"] if wet else "Unknown",
            "Nearest mapped NWI feature (meters)":
                (wet["nearest_m"] if wet["nearest_m"] is not None
                 else "None mapped within 500 m") if wet else "Unknown",
            "Screening flag": result["flag"],
            "Data gaps": json.dumps(result["issues"]),
        })

    complete = all(r["grade"]["grade"] != "N/A" for _, r in completed)
    ranked = compare_sites(rows_for_ranking)
    if complete and ranked:
        preferred = ranked[0]
        preferred_grade = next(r["grade"]["grade"] for s, r in completed
                               if s["id"] == preferred["id"])
        st.markdown(
            f'''<div class="comparison-banner"><div style="font-size:2rem">↗</div>
              <div><strong>First location to investigate: {escape(preferred['name'])} (Grade {escape(preferred_grade)})</strong>
              <span>This has the lowest mapped concerns among the screened candidates eligible for preliminary comparison. The result is not a finding that the site is environmentally safe or technically feasible.</span></div></div>''',
            unsafe_allow_html=True,
        )
    elif not complete:
        st.warning("At least one site could not be graded because a required map service failed. Fix the data gaps before choosing a preferred site.")
    else:
        st.warning("All evaluated sites have major mapped conflicts. Investigate other locations rather than automatically selecting a winner.")

    st.markdown("### Detailed comparison")
    st.dataframe(report, use_container_width=True, hide_index=True)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(report[0].keys()))
    writer.writeheader()
    writer.writerows(report)
    st.download_button(
        "↓ Download report (CSV)", output.getvalue(),
        file_name="ecosite_biodiversity_comparison_v2.csv",
        mime="text/csv", use_container_width=False,
    )
    for site, result in completed:
        with st.expander(f"View geographic evidence & uncertainties · {site['name']}"):
            st.markdown(f"**Grade {result['grade']['grade']}** — {result['grade']['headline']}")
            st.write(result["grade"]["explanation"])
            st.write(f"**Screening flag:** {result['flag']} · {result['reason']}")
            if result["land"]:
                st.markdown("**USGS land-cover estimates by class (%)**")
                st.json(result["land"]["classes_pct"])
                st.caption(
                    f"{result['land']['sample_points']} sampling cells; grid spacing about "
                    f"{result['land']['grid_spacing_m']} m. Land cover is a proxy, "
                    "not a species survey or proof of native habitat."
                )
            if result["wet"]:
                wet = result["wet"]
                st.write(
                    f"**Mapped NWI aquatic features:** {wet['nearby_count']} within the "
                    f"500 m search zone; {wet['overlap_acres']:.3f} acres overlap the footprint."
                )
                st.caption(wet["message"])
            if result["issues"]:
                st.error("Unavailable data: " + json.dumps(result["issues"], indent=2))
            st.caption("Unassessed: threatened species, fragmentation, water demand, infrastructure and wildlife disturbance.")

st.divider()
with st.expander("How the letter grades work · Read before using results"):
    st.markdown(
        """Grades are **provisional educational thresholds**, not calibrated or scientifically validated ecological-impact ratings.
        Every grade uses **two datasets only**: USGS land-cover estimates and mapped USFWS aquatic features.

        | Grade | Preliminary meaning | Example trigger |
        |---|---|---|
        | **A** | Lowest mapped concern | Less than 2% and 0.25 acre mapped natural cover; no mapped aquatic feature within 250 m |
        | **B** | Relatively low mapped concern | Small natural-cover disturbance or aquatic feature 100–250 m away |
        | **C** | Meaningful concern | At least 10% or 1 acre natural cover, possible wetland pixels, or mapped aquatic feature within 100 m |
        | **D** | High concern | At least 30% or 3 acres of mapped natural cover |
        | **F** | Major concern | Mapped aquatic overlap, more than 1% wetland land cover, at least 60% or 10 acres natural cover |
        | **Not graded** | Required data missing | Either GIS layer unavailable |

        **Stricter triggers take precedence.** A high-concern aquatic or habitat finding cannot be averaged away by other favorable results. These are *absolute screening categories*, so a town may have no A-rated candidates. Proximity bands are pragmatic classroom heuristics, **not regulatory setback distances** or species-specific impact boundaries.
        """
    )

st.markdown("### Sources & scientific limitations")
st.markdown(
    f'<div class="foot">USGS Annual NLCD {NLCD_YEAR} (approximate 30 m land-cover sampling); '
    'U.S. Fish & Wildlife Service National Wetlands Inventory (NWI) mapped aquatic polygons. '
    'Wetlands may be absent from the inventory; species and critical habitat, watershed impacts, '
    'infrastructure requirements, land ownership, zoning and engineering remain unassessed. '
    'All ratings are preliminary and must be reviewed by qualified specialists before real development decisions.</div>',
    unsafe_allow_html=True,
)
st.markdown(
    "[USGS annual land cover](https://www.usgs.gov/centers/eros/science/annual-national-land-cover-database) · "
    "[USFWS National Wetlands Inventory](https://www.fws.gov/program/national-wetlands-inventory/web-mapping-services) · "
    "[NatureServe biodiversity mapping (future phase)](https://www.natureserve.org/map-biodiversity-importance)"
)
