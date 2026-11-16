"""Streamlit front end for EcoSite's first map-based comparison prototype."""
import csv
import io
import json
import uuid
from datetime import datetime

import folium
import requests
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import mapping
from streamlit_folium import st_folium

from model import analyze_site, ensure_polygon, compare_sites, NLCD_YEAR

st.set_page_config(page_title="EcoSite | Compare locations", page_icon="🌱", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 1.7rem; max-width: 1250px}
.main-title {font-size: 2.35rem; font-weight: 780; letter-spacing: -0.05rem; color: #155448}
.kicker {color: #377869; font-size: 0.76rem; letter-spacing: .12em; font-weight: 750}
.explainer {color: #555; max-width: 860px}
.smallnote {color: #666; font-size: .85rem}
</style>""", unsafe_allow_html=True)

if "sites" not in st.session_state:
    st.session_state.sites = []
if "results" not in st.session_state:
    st.session_state.results = {}
if "center" not in st.session_state:
    st.session_state.center = [42.5349, -92.4453]  # starting map view: Cedar Falls, IA
if "zoom" not in st.session_state:
    st.session_state.zoom = 12
if "community" not in st.session_state:
    st.session_state.community = "Cedar Falls, Iowa"

@st.cache_data(ttl=86400, show_spinner=False)
def geocode(place):
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place + ", USA", "format": "jsonv2", "limit": 1},
        headers={"User-Agent": "EcoSite educational demonstration (Streamlit mapping application)"}, timeout=15)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError("No matching community found. Try adding the state.")
    return [float(data[0]["lat"]), float(data[0]["lon"])]

with st.sidebar:
    st.subheader("1 · Choose your town")
    query = st.text_input("City and state", st.session_state.community,
                          help="The map initially opens in Cedar Falls, Iowa.")
    if st.button("Find town", use_container_width=True):
        try:
            st.session_state.center = geocode(query)
            st.session_state.community = query
            st.session_state.zoom = 12
            st.rerun()
        except Exception as exc:
            st.error(f"Could not search for this town: {exc}")
    st.divider()
    st.subheader("2 · Draw sites")
    st.write("Use the **rectangle** or **polygon** tool on the map to outline a proposed building footprint. Then click Add below.")
    proposed_label = st.text_input("Name for next site", value=f"Site {chr(65 + len(st.session_state.sites))}" if len(st.session_state.sites)<5 else "Site")
    st.caption(f"{len(st.session_state.sites)} of 5 possible locations added")
    st.divider()
    st.subheader("3 · Compare them")
    st.caption("Needs an internet connection to contact two public geographic datasets. The tool does not use a language model to invent scores.")
    run_analysis = st.button("Analyze selected sites", type="primary", use_container_width=True, disabled=len(st.session_state.sites) < 2)
    if st.session_state.sites:
        if st.button("Remove last site", use_container_width=True):
            removed = st.session_state.sites.pop()
            st.session_state.results.pop(removed["id"], None)
            st.rerun()
        if st.button("Clear all sites", use_container_width=True):
            st.session_state.sites = []
            st.session_state.results = {}
            st.rerun()

st.markdown('<div class="kicker">FIRST LEGO LEAGUE · INNOVATION PROTOTYPE</div>', unsafe_allow_html=True)
st.markdown('<div class="main-title">🌱 EcoSite · Location comparison</div>', unsafe_allow_html=True)
st.markdown('<div class="explainer">Compare proposed data-center footprints using real USGS land-cover samples and U.S. Fish & Wildlife Service mapped aquatic features. This is <b>an early ecological screen</b>, not a final biodiversity ranking or construction approval.</div>', unsafe_allow_html=True)

left, right = st.columns([1.85, 1], gap="large")

with left:
    m = folium.Map(location=st.session_state.center, zoom_start=st.session_state.zoom,
                   tiles="OpenStreetMap", control_scale=True, prefer_canvas=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, Maxar, Earthstar Geographics and the GIS User Community",
        name="Satellite", overlay=False).add_to(m)
    palette = ["#0b7d77", "#ff9a45", "#8b5cf6", "#2e6cd1", "#c65074"]
    for i, site in enumerate(st.session_state.sites):
        fg = folium.FeatureGroup(name=site["name"])
        folium.GeoJson(site["feature"], style_function=lambda _, c=palette[i]:
                       {"color": c, "weight": 3, "fillColor": c, "fillOpacity": 0.16},
                       tooltip=site["name"]).add_to(fg)
        fg.add_to(m)
    # Add only the NWI polygons obtained from actual successful live queries.
    wet_features = []
    for site in st.session_state.sites:
        wet = st.session_state.results.get(site["id"], {}).get("wet") or {}
        wet_features.extend(wet.get("features") or [])
    if wet_features:
        folium.GeoJson({"type": "FeatureCollection", "features": wet_features}, name="Mapped NWI aquatic features",
                       style_function=lambda _: {"color":"#3284cd", "weight":1, "fillColor":"#45b8de", "fillOpacity":.4},
                       tooltip=folium.GeoJsonTooltip(fields=["feature_type"], aliases=["NWI category:"])).add_to(m)
    Draw(export=False,
         draw_options={"polyline": False,"marker": False,"circle": False,"circlemarker": False,
                       "polygon": {"shapeOptions": {"color": "#155448"}},
                       "rectangle": {"shapeOptions": {"color": "#155448"}}},
         edit_options={"edit": False, "remove": False}).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    map_response = st_folium(m, height=515, use_container_width=True, key="ecosite_map",
                             returned_objects=["last_active_drawing"])
    drawn = (map_response or {}).get("last_active_drawing")
    if st.button("+ Add the drawn location", disabled=len(st.session_state.sites)>=5, use_container_width=True):
        if not drawn:
            st.warning("First draw a rectangle or polygon on the map.")
        elif not proposed_label.strip():
            st.warning("Give the location a name.")
        else:
            try:
                poly = ensure_polygon(drawn)
                feature = {"type":"Feature", "geometry":mapping(poly), "properties":{}}
                st.session_state.sites.append({"id": str(uuid.uuid4()),"name": proposed_label.strip(),"feature":feature})
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.caption("Map shapes are *hypothetical development footprints* until a real parcel boundary and project layout are supplied. Draw at least two locations. Works in the contiguous U.S.")

with right:
    st.subheader("Your candidate sites")
    if not st.session_state.sites:
        st.info("Start by drawing Site A and Site B on the map. You can compare up to five sites.")
    for i, site in enumerate(st.session_state.sites):
        result = st.session_state.results.get(site["id"])
        with st.container(border=True):
            st.markdown(f"**{site['name']}**")
            if result:
                st.caption(f"{result['area_acres']:.1f} acres · {result['flag']} screening flag")
                st.write(result["reason"])
            else:
                st.caption("Outline saved · Not analyzed yet")
    st.divider()
    st.subheader("What this first version measures")
    st.markdown("**Measured:**")
    st.markdown("- Approximate natural land-cover area within each footprint (USGS annual NLCD, **2024**).\n- Mapped wetland and other aquatic-feature overlap and distance (USFWS NWI, within **500 m**).")
    st.markdown("**Not yet measured:**")
    st.markdown("- Rare species and critical habitat\n- Habitat connectivity\n- Cooling water use\n- Supporting infrastructure impacts\n- Wildlife disturbance from light/noise")
    st.caption("Missing data are flagged as unknown—not treated as a low-impact result.")

if run_analysis:
    new_results={}
    progress=st.progress(0, text="Requesting live GIS measurements…")
    for i, site in enumerate(st.session_state.sites):
        with st.spinner(f"Analyzing {site['name']}…"):
            new_results[site["id"]] = analyze_site(site["feature"])
        progress.progress((i+1)/len(st.session_state.sites), text=f"Completed {i+1}/{len(st.session_state.sites)}")
    st.session_state.results=new_results
    st.rerun()

if st.session_state.results:
    st.divider()
    st.subheader("Preliminary comparison")
    site_rows=[]
    report=[]
    for site in st.session_state.sites:
        result=st.session_state.results.get(site["id"])
        if not result:
            continue
        land=result["land"]
        wet=result["wet"]
        site_rows.append({"id":site["id"],"name":site["name"],"flag":result["flag"],"land":land,"wet":wet})
        report.append({
            "Site":site["name"], "Footprint acres":result["area_acres"],
            "Screening flag (2 mapped layers only)":result["flag"],
            "Estimated natural/wetland land-cover acres": land["natural_est_acres"] if land else "Unknown",
            "Percent developed low-high intensity": land["already_developed_pct"] if land else "Unknown",
            "Mapped NWI aquatic overlap acres": wet["overlap_acres"] if wet else "Unknown",
            "Distance to nearest mapped NWI feature (m, within 500m)": (wet["nearest_m"] if wet and wet["nearest_m"] is not None else "None mapped within 500m" if wet else "Unknown"),
            "Explanation":result["reason"],
            "Data gaps": json.dumps(result["issues"]),
        })
    st.dataframe(report, use_container_width=True, hide_index=True)
    ranked = compare_sites(site_rows)
    valid = [x for x in site_rows if x["flag"] != "GRAY"]
    if len(ranked) >= 2 and len(valid) == len(site_rows):
        st.info(f"**First site to investigate, using only the two mapped layers:** {ranked[0]['name']}. "
                "This is a provisional screening order, not a determination of the site's overall biodiversity impact. "
                "The screening rules prioritize avoiding mapped aquatic-feature overlap, then lower mapped-natural-land-cover concern.")
    else:
        st.warning("The tool cannot make a complete map-based comparison because one or more sites have missing data, or mapped aquatic-feature conflicts require further review.")
    buf=io.StringIO()
    writer=csv.DictWriter(buf,fieldnames=list(report[0].keys()))
    writer.writeheader(); writer.writerows(report)
    st.download_button("Download comparison (CSV)", buf.getvalue(), file_name="ecosite_site_comparison.csv",mime="text/csv")
    for site in st.session_state.sites:
        r=st.session_state.results.get(site["id"])
        if not r: continue
        with st.expander(f"Evidence and caveats · {site['name']}"):
            st.write(r["reason"])
            if r["land"]:
                st.write("**USGS land cover (estimated percent by class)**")
                st.json(r["land"]["classes_pct"])
                st.caption(f"Based on {r['land']['sample_points']} sampling cells; grid spacing ~{r['land']['grid_spacing_m']} m. Classified cover is a proxy, not proof of native habitat or species occurrence.")
            if r["wet"]:
                st.write(f"**NWI aquatic features:** {r['wet']['nearby_count']} mapped polygons within 500 m search area. "
                         f"Footprint overlap: {r['wet']['overlap_acres']} acres.")
                st.caption(r["wet"]["message"])
            if r["issues"]:
                st.error("Data or service issues: " + json.dumps(r["issues"],indent=2))
            st.caption("Unassessed: threatened species, connectivity, water demand, utility infrastructure, light/noise. No site is considered approved or ecologically safe.")

st.divider()
st.markdown("**Data and methodology**")
st.caption("USGS Annual NLCD 2024 via ArcGIS ImageServer (30 m resolution); area proportions estimated by sampling. USFWS National Wetlands Inventory via ArcGIS REST (mapped wetlands, ponds, lakes, and rivers). Actual local species, unmapped waters, zoning, land ownership, utility capacity, and project engineering require additional review. A 100 m proximity warning and 10% / 1-acre natural-cover warning are educational prototype rules, NOT validated ecological standards.")
st.markdown("[USGS annual land cover](https://www.usgs.gov/centers/eros/science/annual-national-land-cover-database) · [USFWS wetlands service](https://www.fws.gov/program/national-wetlands-inventory/web-mapping-services) · [NatureServe biodiversity map](https://www.natureserve.org/map-biodiversity-importance)")
