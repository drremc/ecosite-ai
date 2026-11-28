"""EcoSite AI: accessible, transparent preliminary GIS comparison website."""
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

from model import NLCD_YEAR, analyze_site, ensure_polygon
from experience import make_demo, next_site_name, wizard_step, best_preliminary_option, friendly_error
from report_pdf import build_one_page_report
from restoration import (
    analyze_restoration_area, make_restoration_plan, plan_markdown,
    validate_restoration_area,
)

st.set_page_config(
    page_title="EcoSite AI | Biodiversity site comparison",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """<style>
    /* EcoSite V4 — contrast-first palette. Each ordinary text/background pair
       was chosen to exceed WCAG AA 4.5:1 (aiming for AAA 7:1). The styles
       live in app.py, so readability does not depend on uploading config.toml. */
    :root {
      --ink:#102c26; --text:#18392f; --muted:#28483e;
      --teal:#104f46; --pale:#e9f2eb; --paper:#ffffff;
      --canvas:#f5f8f5; --border:#9cb6a7;
      --primary-color:#104f46; --text-color:#102c26;
      --background-color:#f5f8f5; --secondary-background-color:#edf4ee;
    }
    html, body, .stApp, [data-testid="stAppViewContainer"] {
      background:var(--canvas) !important; color:var(--ink) !important;
      color-scheme:light !important;
    }
    .block-container {padding-top:1.45rem;padding-bottom:3.5rem;max-width:1480px;}
    [data-testid="stHeader"] {background:var(--canvas) !important;}
    [data-testid="stMain"] {color:var(--ink) !important;}
    [data-testid="stMain"] :is(h1,h2,h3,h4,h5,h6),
    [data-testid="stSidebar"] :is(h1,h2,h3,h4,h5,h6) {
      color:var(--ink); font-weight:750;
    }
    /* Built-in Streamlit paragraphs/labels/captions. Do not target arbitrary
       <p> or <span> globally or we would break the dark hero's white lettering. */
    [data-testid="stMain"] [data-testid="stMarkdownContainer"] > :is(p,ul,ol),
    [data-testid="stMain"] [data-testid="stMarkdownContainer"] > :is(p,ul,ol) :is(li,strong,em),
    [data-testid="stMain"] [data-testid="stWidgetLabel"],
    [data-testid="stMain"] [data-testid="stWidgetLabel"] p,
    [data-testid="stMain"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"],
    [data-testid="stMain"] [data-testid="stExpander"] summary,
    [data-testid="stMain"] [data-testid="stCaptionContainer"],
    [data-testid="stMain"] [data-testid="stCaptionContainer"] p,
    [data-testid="stMain"] [data-testid="stText"],
    [data-testid="stMain"] [data-testid="stAlertContent"] {
      color:var(--ink) !important; opacity:1 !important;
      font-size:1rem !important; line-height:1.6 !important;
    }
    [data-testid="stMain"] a,
    [data-testid="stSidebar"] a {color:#084b42 !important;text-decoration:underline;text-underline-offset:2px;}
    [data-testid="stMain"] a:hover,
    [data-testid="stSidebar"] a:hover {color:#07372f !important;}

    /* Sidebar: reliable dark lettering even if the viewer selected dark mode. */
    [data-testid="stSidebar"], [data-testid="stSidebarContent"],
    [data-testid="stSidebarUserContent"] {
      background:#e9f2eb !important;color:var(--ink) !important;
    }
    [data-testid="stSidebar"] {border-right:2px solid #b2cabb !important;}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] > :is(p,ul,ol),
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] [data-testid="stTooltipIcon"] {
      color:var(--ink) !important;opacity:1 !important;
      font-size:1rem !important;line-height:1.58 !important;
    }
    [data-testid="stSidebar"] h3 {font-size:1.14rem !important;line-height:1.38; margin-bottom:.65rem;}
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {font-weight:750 !important;}
    [data-testid="stSidebar"] [data-testid="stDivider"] {color:#b2cabb !important;}

    /* All standard native inputs: white field, dark text, visible placeholder. */
    .stApp input, .stApp textarea,
    .stApp [data-baseweb="input"],.stApp [data-baseweb="textarea"],
    .stApp [data-baseweb="select"] > div,
    .stApp [data-testid="stNumberInput"] [data-baseweb="input"] {
      background:#ffffff !important; color:var(--ink) !important;
      border-color:#648476 !important;
    }
    .stApp input, .stApp textarea, .stApp [data-baseweb="select"] input {
      -webkit-text-fill-color:var(--ink) !important;
      font-size:1.03rem !important;font-weight:600 !important;
    }
    .stApp input::placeholder,.stApp textarea::placeholder {
      color:#39574a !important;-webkit-text-fill-color:#39574a !important;opacity:1 !important;
    }
    .stApp [data-baseweb="select"] :is(span,div) {color:var(--ink) !important;}
    .stApp [data-baseweb="popover"] {color:var(--ink) !important;background:#fff !important;}

    /* Buttons, including sidebar, are legible independently of default theme. */
    .stApp button[kind="primary"],
    .stApp [data-testid="stBaseButton-primary"] {
      background:#104f46 !important;border:2px solid #104f46 !important;
      color:#fff !important;font-size:1rem !important;font-weight:750 !important;
      min-height:2.75rem;
    }
    .stApp button[kind="primary"] :is(p,span,svg),
    .stApp [data-testid="stBaseButton-primary"] :is(p,span,svg) {
      color:#fff !important;fill:currentColor;
    }
    .stApp button[kind="secondary"],
    .stApp [data-testid="stBaseButton-secondary"],
    .stApp [data-testid="stDownloadButton"] button {
      color:var(--ink) !important;background:#fff !important;
      border:2px solid #648476 !important;font-size:1rem !important;
      font-weight:750 !important;min-height:2.75rem;
    }
    .stApp button[kind="secondary"] :is(p,span),
    .stApp [data-testid="stBaseButton-secondary"] :is(p,span) {color:var(--ink) !important;}
    .stApp button:disabled,.stApp button:disabled :is(p,span) {
      background:#e7eee9 !important;color:#425c50 !important;
      -webkit-text-fill-color:#425c50 !important;opacity:1 !important;
    }
    .stApp :is(button,input,textarea):focus-visible,
    .stApp [role="button"]:focus-visible {outline:3px solid #c26b0e !important;outline-offset:2px;}

    /* Streamlit alerts / expanders / data tables must remain readable too. */
    [data-testid="stAlert"] {background:#edf3ef !important;border:1px solid #91aea0 !important;}
    [data-testid="stAlert"] :is(p,span,div) {color:#16352b !important;opacity:1 !important;}
    [data-testid="stExpander"] {background:#fff !important;color:var(--ink) !important;border:1px solid #b5cbbd !important;}
    [data-testid="stExpander"] summary :is(p,span,svg) {color:var(--ink) !important;}
    [data-testid="stDataFrame"] {background:#fff !important;}
    /* This also covers the native markdown grading table at the page bottom. */
    [data-testid="stMain"] table {background:#fff;color:var(--ink);}
    [data-testid="stMain"] table th {background:#e8f1ea;color:var(--ink) !important;}
    [data-testid="stMain"] table td {background:#fff;color:var(--ink) !important;}
    [data-testid="stMain"] table :is(th,td) {border-color:#a8bfb1 !important;}

    /* Restoration planner — high contrast, compatible with light/dark browser settings. */
    .restore-hero {background:#e5f2e9;border:2px solid #9fbea9;
      border-radius:16px;padding:21px 23px;margin:14px 0 18px;color:#15372a !important;}
    .restore-hero .kicker {font-size:.9rem;letter-spacing:.09em;text-transform:uppercase;
      font-weight:850;color:#19503b !important;margin-bottom:8px;}
    .restore-hero h3 {font-size:1.42rem;color:#13382b !important;margin:0 0 8px;}
    .restore-hero p {font-size:1.05rem;line-height:1.65;color:#244438 !important;margin:0;}
    .restoration-stat {background:#ffffff;border:1px solid #9ebcad;border-radius:15px;
      padding:16px 18px;min-height:140px;}
    .restoration-stat .value {font-size:2.15rem;font-weight:850;color:#134b36 !important;}
    .restoration-stat .label {font-size:1.02rem;font-weight:800;color:#1a3c2b !important;}
    .restoration-stat .description {font-size:.95rem;line-height:1.55;color:#2e4a3d !important;}
    .restoration-action {background:#fff;border:1px solid #adbeae;border-radius:12px;
      padding:16px 17px;margin:11px 0;}
    .restoration-action .small-badge {font-size:.85rem;font-weight:850;color:#164935 !important;
      background:#dcece0;border-radius:20px;padding:4px 9px;display:inline-block;margin-bottom:8px;}
    .restoration-action h4 {font-size:1.1rem;color:#15362b !important;margin:0 0 6px;}
    .restoration-action p {font-size:1.01rem;line-height:1.62;color:#263c32 !important;margin:0 0 7px;}
    .restoration-action .verify {font-size:.98rem;color:#30483d !important;line-height:1.6;}
    /* Custom UI: explicit foreground colors on every surface. */
    h1,h2,h3,p {overflow-wrap:anywhere;}
    h2 {font-size:1.5rem !important;letter-spacing:-.025em;color:var(--ink);}
    [data-testid="stVerticalBlockBorderWrapper"] {border-color:#acbfaf !important;}
    .hero {position:relative;overflow:hidden;
      background:linear-gradient(116deg,#102f33 0%,#14584f 69%,#246453 100%);
      color:#fff !important;border-radius:22px;padding:34px 40px 38px;
      margin:4px 0 20px;box-shadow:0 12px 40px rgba(11,65,53,.10);}
    .hero:after {content:"";position:absolute;width:280px;height:280px;
      border:1px solid rgba(255,255,255,.20);border-radius:50%;right:-72px;top:-84px;
      box-shadow:0 0 0 50px rgba(255,255,255,.025),0 0 0 102px rgba(255,255,255,.025);
      pointer-events:none;}
    .hero .eyebrow {font-size:.92rem;font-weight:800;letter-spacing:.12em;
      text-transform:uppercase;color:#e5fff0 !important;margin-bottom:11px;}
    .hero h1 {font-size:clamp(2.2rem,4vw,3.45rem);font-weight:810;
      letter-spacing:-.065em;line-height:1.08;margin:0 0 12px;color:#fff !important;}
    .hero h1 em {font-style:normal;color:#eeffcc !important;}
    .hero p,.hero .hero-lead,.hero .hero-support {color:#fff !important;opacity:1 !important;}
    .hero p {max-width:930px;font-size:1.08rem;line-height:1.7;margin:0 0 13px;}
    .hero .hero-lead {font-size:1.21rem;line-height:1.6;font-weight:700;
      max-width:980px;margin:0 0 15px;}
    .hero .hero-support {max-width:920px;line-height:1.74;margin-bottom:18px;}
    .hero strong,.hero .chip {color:#fff !important;}
    .hero strong {font-weight:800;}
    .chips {display:flex;flex-wrap:wrap;gap:9px;}
    .chip {border-radius:30px;border:1px solid rgba(255,255,255,.64);
      font-size:.94rem;font-weight:750;padding:7px 13px;background:rgba(0,0,0,.12);}
    .meta-strip {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:21px;}
    .meta {background:#fff;border:1px solid #afc8b8;border-radius:14px;
      padding:14px 18px;box-shadow:0 2px 6px rgba(16,59,47,.035);}
    .meta .caption {font-size:.91rem;font-weight:800;color:#29483d;
      letter-spacing:.025em;text-transform:uppercase;}
    .meta .value {font-size:1.4rem;font-weight:800;color:#153a31;margin-top:3px;line-height:1.28;}
    .section-head {display:flex;justify-content:space-between;align-items:center;gap:12px;
      margin-bottom:12px;margin-top:10px;}
    .section-head h2 {margin:0;font-size:1.45rem!important;color:var(--ink) !important;}
    .section-head p {margin:4px 0 0;font-size:1.05rem;color:#28483e !important;line-height:1.6;}
    .section-pill {color:#124737 !important;background:#d9ecdf;border-radius:30px;
      padding:7px 12px;white-space:nowrap;font-size:.92rem;font-weight:800;}
    .site-list {display:grid;gap:10px;margin:10px 0;}
    .site-mini {background:#fff;border:1px solid #acc4b3;border-radius:13px;
      padding:14px 16px;display:flex;gap:12px;align-items:start;}
    .site-dot {width:12px;height:12px;min-width:12px;border-radius:50%;margin-top:6px;}
    .site-title {color:#102e28 !important;font-size:1.08rem;font-weight:800;margin-bottom:4px;}
    .site-sub {color:#28463c !important;font-size:1rem;line-height:1.6;}
    .grade-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:14px 0 22px;}
    .grade-card {background:#fff;border:1px solid #acc4b3;border-top:5px solid var(--grade-accent);
      border-radius:16px;padding:21px 20px 20px;min-width:0;
      box-shadow:0 6px 22px rgba(23,64,56,.045);}
    .grade-card .top {display:flex;justify-content:space-between;gap:6px;
      align-items:center;margin-bottom:12px;}
    .grade-card .site {font-weight:800;font-size:1.06rem;color:#102e28 !important;}
    .grade-card .grade {font-size:3.7rem;letter-spacing:-.075em;
      font-weight:850;color:var(--grade-accent) !important;line-height:1.05;}
    .grade-card .tag {background:var(--grade-bg);color:var(--grade-accent) !important;
      font-weight:800;font-size:.96rem;padding:6px 10px;border-radius:99px;}
    .grade-card .heading {color:#142f28 !important;font-size:1.05rem;
      font-weight:800;margin:14px 0 7px;}
    .grade-card .reason {color:#233d33 !important;font-size:1.04rem;
      line-height:1.68;margin:0;min-height:84px;}
    .grade-card .measure {margin-top:16px;padding-top:13px;border-top:1px solid #b8cdbf;
      color:#27463c !important;font-size:.96rem;line-height:1.6;}
    .comparison-banner {display:flex;gap:15px;align-items:center;background:#e5f1e8;
      border:2px solid #a6c4b0;padding:18px 21px;border-radius:13px;
      margin:10px 0 18px;color:#133b2e !important;}
    .comparison-banner strong {font-weight:820;color:#12372c !important;}
    .comparison-banner span {display:block;margin-top:4px;font-size:1.02rem;
      color:#224335 !important;line-height:1.6;}
    .notice {background:#fff5df;border:1px solid #d1b789;border-radius:12px;
      padding:14px 16px;color:#4b3112 !important;font-size:1.04rem;line-height:1.65;margin:12px 0;}
    .notice strong {color:#4b3112 !important;}
    .brand {padding:10px 0 4px;font-size:1.39rem;color:#0f4335 !important;
      font-weight:850;letter-spacing:-.035em;}
    .brand-caption {font-size:.96rem;letter-spacing:.06em;color:#2b493d !important;
      font-weight:790;text-transform:uppercase;margin-bottom:24px;}
    .sidebar-help {font-size:1.03rem;line-height:1.65;color:#213e32 !important;
      margin:.42rem 0 1rem;}
    .sidebar-help strong {color:#12372c !important;}
    .sidebar-version {font-size:.94rem;line-height:1.58;color:#274438 !important;
      font-weight:780;letter-spacing:.025em;margin:.6rem 0;}
    .foot {color:#26463a !important;font-size:1.03rem;line-height:1.67;}
    @media(max-width:780px) {
      .hero {padding:24px 21px;} .hero .hero-lead{font-size:1.11rem;}
      .meta-strip{grid-template-columns:1fr 1fr;}
      .grade-card .reason{min-height:0;}
    }
    @media(max-width:520px) {
      .meta-strip{grid-template-columns:1fr;}
      .section-pill{white-space:normal;}
    }
    /* Version 6: explicit accessible controls; these selectors also cover the
       optional restoration planner. Avoid inheriting dark browser themes. */
    .stApp [data-testid="stRadio"] [role="radiogroup"] label,
    .stApp [data-testid="stRadio"] [role="radiogroup"] label > div,
    .stApp [data-testid="stRadio"] [role="radiogroup"] label p,
    .stApp [data-testid="stRadio"] [role="radiogroup"] label span {
      color:#102c26 !important;-webkit-text-fill-color:#102c26 !important;
      opacity:1 !important;
    }
    .stApp [data-testid="stRadio"] [role="radiogroup"] label {
      background:#ffffff !important;border:1px solid #7e9c8a !important;
      padding:8px 12px !important;border-radius:9px !important;
    }
    .stApp [data-testid="stCheckbox"] label,
    .stApp [data-testid="stCheckbox"] label :is(p,span),
    .stApp [data-testid="stToggle"] label,
    .stApp [data-testid="stToggle"] label :is(p,span),
    .stApp [data-testid="stSelectbox"] label,
    .stApp [data-testid="stSelectbox"] label :is(p,span),
    .stApp [data-testid="stBaseButton-secondary"] :is(p,span),
    .stApp [data-testid="stDownloadButton"] button :is(p,span) {
      color:#102c26 !important;-webkit-text-fill-color:#102c26 !important;
      opacity:1 !important;
    }
    .stApp [data-testid="stToggle"] [role="switch"][aria-checked="true"] {
      background-color:#104f46 !important;
    }
    .stApp [data-testid="stToggle"] [role="switch"][aria-checked="false"] {
      background-color:#c8d5ce !important;
    }
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] input,
    [data-baseweb="popover"] [role="listbox"],
    [data-baseweb="popover"] [role="option"] {
      background-color:#ffffff !important;color:#102c26 !important;
      -webkit-text-fill-color:#102c26 !important;
    }
    [data-baseweb="popover"] [role="option"]:hover,
    [data-baseweb="popover"] [aria-selected="true"] {
      background-color:#e4efe7 !important;color:#102c26 !important;
    }
    .stApp [data-testid="stBaseButton-primary"] :is(p,span),
    .stApp button[kind="primary"] :is(p,span) {
      color:#fff !important;-webkit-text-fill-color:#fff !important;
    }
    .plant-guidance {background:#ecf4ed;border:2px solid #a5beae;
      border-radius:12px;padding:14px 16px;margin:13px 0;color:#173a2c !important;
      font-size:1.05rem;line-height:1.65;}
    .plant-guidance strong {color:#123a2e !important;}
    .plant-header {font-size:1.09rem;font-weight:800;color:#19392d !important;
      margin:16px 0 8px;line-height:1.5;}
    .plant-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:11px;margin:12px 0 22px;}
    .plant-entry {background:#fff;border:1px solid #9ab7a3;border-left:4px solid #267352;
      border-radius:12px;padding:15px 16px;color:#18392f !important;}
    .plant-entry .plant-name {font-size:1.05rem;font-weight:850;color:#153b2b !important;}
    .plant-entry .plant-scientific {font-size:.98rem;font-style:italic;color:#244b3c !important;
      margin:3px 0 8px;}
    .plant-entry .plant-role {font-size:1rem;color:#27483a !important;line-height:1.5;}
    /* Version 7: eliminate dark-on-dark error and exception UI.
       These tokens are independently readable, including when the viewer uses
       a dark Streamlit preference. Use a light error surface consistently. */
    :root {
      --error-ink:#3b1b18; --error-bg:#fff7f5;
      --error-outline:#b23e34; --error-title:#782018;
      --status-ink:#18382e; --status-bg:#ffffff;
    }
    /* Neutral, legible surfaces for all native status notifications, without
       falsely coloring informational or success messages red. */
    [data-testid="stAlert"],
    [data-testid="stAlert"] [data-baseweb="notification"],
    [data-testid="stAlertContent"],
    [data-testid="stNotification"],
    [data-testid="stToast"],
    [data-baseweb="toast"] {
      background-color:var(--status-bg) !important;
      color:var(--status-ink) !important;
      border-color:#8ca99a !important;
      color-scheme:light !important;
      opacity:1 !important;
    }
    /* Unhandled Streamlit errors/tracebacks use the error palette. */
    [data-testid="stException"],
    [data-testid="stExceptionDetails"],
    [data-testid="stExceptionMessage"] {
      background-color:var(--error-bg) !important;
      color:var(--error-ink) !important;
      border-color:var(--error-outline) !important;
      color-scheme:light !important;
      opacity:1 !important;
    }
    /* Explicit foregrounds, including Markdown wrappers, expandable traceback
       details, and text in floating notifications. */
    :is([data-testid="stAlert"], [data-testid="stToast"],
        [data-testid="stNotification"], [data-baseweb="toast"])
        :is(p,span,div,strong,em,small,summary,label,pre,code,button),
    :is([data-testid="stAlert"], [data-testid="stToast"],
        [data-testid="stNotification"], [data-baseweb="toast"])
        [data-testid="stMarkdownContainer"] * {
      color:var(--status-ink) !important;
      -webkit-text-fill-color:var(--status-ink) !important;
      opacity:1 !important;
    }
    :is([data-testid="stException"], [data-testid="stExceptionDetails"],
        [data-testid="stExceptionMessage"])
        :is(p,span,div,strong,em,small,summary,label,pre,code,button),
    [data-testid="stException"] [data-testid="stMarkdownContainer"] * {
      color:var(--error-ink) !important;
      -webkit-text-fill-color:var(--error-ink) !important;
      opacity:1 !important;
    }
    /* Code and stack-trace panels must not inherit the dark code theme. */
    :is([data-testid="stException"], [data-testid="stExceptionDetails"],
        [data-testid="stAlert"]) :is(pre,code) {
      background:#ffffff !important;
      color:var(--error-ink) !important;
      -webkit-text-fill-color:var(--error-ink) !important;
      border:1px solid #d9b4af !important;
      white-space:pre-wrap !important;
      overflow-wrap:anywhere !important;
    }
    [data-testid="stException"] svg {
      color:var(--error-title) !important;
    }
    /* Modal/dialog surfaces, if Streamlit presents a runtime detail window. */
    [data-testid="stDialog"],
    [role="alertdialog"],
    [data-baseweb="modal"] [role="dialog"] {
      background:#ffffff !important;
      color:#172f27 !important;
      color-scheme:light !important;
    }
    :is([data-testid="stDialog"], [role="alertdialog"],
        [data-baseweb="modal"] [role="dialog"]) :is(p,span,strong,summary,pre,code) {
      color:#172f27 !important;
      -webkit-text-fill-color:#172f27 !important;
      opacity:1 !important;
    }
    /* App-generated, intentionally accessible errors. These don't depend on
       Streamlit internal test IDs and work in sidebar and main content. */
    .ecosite-error {
      background:var(--error-bg) !important;
      color:var(--error-ink) !important;
      border:2px solid var(--error-outline) !important;
      border-left:7px solid var(--error-outline) !important;
      border-radius:12px !important;
      padding:16px 18px !important;
      margin:11px 0 16px !important;
      box-shadow:none !important;
      color-scheme:light !important;
    }
    .ecosite-error .ecosite-error-title {
      display:block;font-size:1.06rem;font-weight:850;
      color:var(--error-title) !important;
      -webkit-text-fill-color:var(--error-title) !important;
      margin-bottom:5px;
    }
    .ecosite-error .ecosite-error-body {
      display:block;font-size:1.02rem;line-height:1.65;
      color:var(--error-ink) !important;
      -webkit-text-fill-color:var(--error-ink) !important;
      white-space:pre-wrap;overflow-wrap:anywhere;
    }
    /* Version 8: guided workflow, accessible visible progress and demo warning. */
    .step-strip {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;
      margin:5px 0 22px;}
    .step-tile {border:2px solid #a5bbae;border-radius:13px;background:#fff;
      color:#16372c !important;padding:13px 15px;min-height:100px;}
    .step-tile.active {background:#e0f0e5;border-color:#15584b;
      box-shadow:inset 0 0 0 1px #15584b;}
    .step-tile.done {background:#f0f5f0;border-color:#a5bbae;}
    .step-tile .step-number {font-size:.85rem;font-weight:850;letter-spacing:.06em;
      color:#245346 !important;margin-bottom:6px;}
    .step-tile .step-name {font-size:1.09rem;font-weight:850;color:#133a2f !important;}
    .step-tile .step-detail {font-size:.9rem;line-height:1.4;color:#28493b !important;margin-top:4px;}
    .sample-notice {background:#fff0ce;border:2px solid #ac791b;border-radius:12px;
      padding:15px 19px;color:#473113 !important;line-height:1.6;font-weight:700;margin:13px 0;}
    .sample-notice :is(strong,span) {color:#473113 !important;}
    .begin-tip {background:#edf5ee;border:1px solid #b1c6b6;padding:12px 15px;
      border-radius:12px;color:#17382c !important;line-height:1.6;margin:8px 0 14px;}
    @media(max-width:760px){.step-strip{grid-template-columns:1fr;}
      .step-tile{min-height:72px;}}
    </style>""",
    unsafe_allow_html=True,
)

def show_error(message: object) -> None:
    """Display a reliably legible error on a light surface, without HTML injection.

    Used for caught app errors. Uncaught exceptions still use Streamlit's
    native error UI, covered by the CSS rules above.
    """
    details = escape(str(message))
    st.markdown(
        '<div class="ecosite-error" role="alert">'
        '<span class="ecosite-error-title">Unable to complete that step</span>'
        f'<span class="ecosite-error-body">{details}</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def show_helpful_error(kind: str, error: Exception | None = None) -> None:
    """Plain-language instruction first; sensitive developer detail stays collapsed."""
    heading, instruction = friendly_error(kind)
    st.markdown(
        '<div class="ecosite-error" role="alert">'
        '<span class="ecosite-error-title">' + escape(heading) + '</span>'
        '<span class="ecosite-error-body">' + escape(instruction) + '</span>'
        '</div>', unsafe_allow_html=True,
    )
    if error is not None:
        with st.expander('Technical details (for support)'):
            st.code(f'{type(error).__name__}: {error}')




for key, default in (
    ("restoration_geometry", None),
    ("restoration_plan", None),
    ("restoration_analysis", None),
    ("restoration_source_name", None),
    ("restoration_reuse_id", None),
    ("restoration_enabled", False),
    ("sites", []),
    ("is_demo", False),
    ("demo_return", None),
    ("results", {}),
    ("center", [42.5349, -92.4453]),
    ("zoom", 12),
    ("community", "Cedar Falls, Iowa"),
    ("state", "Iowa"),
):
    if key not in st.session_state:
        st.session_state[key] = default


@st.cache_data(ttl=86400, show_spinner=False)
def geocode(place: str):
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place + ", USA", "format": "jsonv2", "addressdetails": 1, "limit": 1},
        headers={"User-Agent": "EcoSite educational demonstration (Streamlit mapping application)"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError("No matching community found. Include city and state.")
    address = data[0].get("address") or {}
    return [float(data[0]["lat"]), float(data[0]["lon"])], address.get("state")


@st.cache_data(ttl=86400, show_spinner=False)
def state_at_coordinates(lat: float, lon: float):
    """Check the actual proposed restoration area rather than assuming a map pan
    or town name establishes its state. Optional lookup; failure stays explicit.
    """
    response = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={"lat": round(lat, 6), "lon": round(lon, 6),
                "format": "jsonv2", "zoom": 5, "addressdetails": 1},
        headers={"User-Agent": "EcoSite educational demonstration (Streamlit mapping application)"},
        timeout=12,
    )
    response.raise_for_status()
    return ((response.json().get("address") or {}).get("state") or None)


def clear_restoration_plan_only():
    """Preserve drawn restoration geography when light or soil choices change."""
    st.session_state.restoration_plan = None


def clear_restoration():
    """Discard stale restoration output if a site or target location changes."""
    for name in ("restoration_geometry", "restoration_plan", "restoration_analysis",
                 "restoration_source_name", "restoration_reuse_id"):
        st.session_state[name] = None


PALETTE = ["#107b6b", "#e99649", "#6d67bf", "#2c74bd", "#c45e8c"]
GRADE_STYLE = {
    "A": ("#09573e", "#e1f4e7"),
    "B": ("#0a5358", "#e0f2f2"),
    "C": ("#704006", "#fff1d7"),
    "D": ("#873714", "#feebde"),
    "F": ("#952737", "#fae7e8"),
    "N/A": ("#30474a", "#eff1f1"),
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
    st.markdown('<div class="brand">🌿 EcoSite AI</div><div class="brand-caption">Biodiversity site explorer</div>', unsafe_allow_html=True)
    st.markdown('### Find a community')
    query = st.text_input('City and state', st.session_state.community,
        help='Start with a U.S. city, such as Cedar Falls, Iowa.')
    if st.button('Find community', use_container_width=True):
        try:
            new_center, new_state = geocode(query.strip())
            st.session_state.sites = []
            st.session_state.results = {}
            st.session_state.is_demo = False
            st.session_state.demo_return = None
            clear_restoration()
            st.session_state.center, st.session_state.state = new_center, new_state
            st.session_state.community = query.strip()
            st.session_state.zoom = 12
            st.rerun()
        except Exception as exc:
            show_helpful_error('town', exc)
    st.divider()
    st.markdown('### How it works')
    st.markdown('**1. Choose locations:** Draw 2–5 rectangles on the map.')
    st.markdown('**2. Compare biodiversity:** Review preliminary A–F grades and source data.')
    st.markdown('**3. Explore restoration (optional):** Investigate habitat improvements.')
    st.divider()
    st.markdown('<p class="sidebar-help">Only two layers are currently analyzed: USGS land cover and USFWS mapped aquatic habitats. The tool does not certify safe building locations.</p>', unsafe_allow_html=True)
    st.markdown('<p class="sidebar-version">FIRST LEGO LEAGUE · RESEARCH PROTOTYPE · VERSION 8</p>', unsafe_allow_html=True)

st.markdown(
    '''<div class="hero">
      <div class="eyebrow">Environmental intelligence / Site selection</div>
      <h1>Build smarter.<br><em>Protect more nature.</em></h1>
      <p class="hero-lead">Compare potential data-center locations using real environmental map layers—and understand what each choice could mean for local wildlife and habitats.</p>
      <p class="hero-support"><strong>Why it matters:</strong> Data centers need space and supporting infrastructure. Building in the wrong place can remove natural habitat and affect wetlands or waterways. Choosing locations carefully can help communities avoid unnecessary damage to biodiversity.</p>
      <p class="hero-support"><strong>How EcoSite AI helps:</strong> Draw two to five possible building sites on the map. The tool compares public land-cover and mapped aquatic-habitat data, then gives each location a preliminary <strong>A–F environmental grade</strong> and a short explanation of its strengths and risks. It's a starting point for better questions—not a final construction approval.</p>
      <div class="chips"><span class="chip">✓ Compare 2–5 sites</span><span class="chip">✓ A–F preliminary grades</span><span class="chip">✓ Optional restoration planner</span></div>
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

# One-click sample demonstration uses invented values, not external GIS calls.
if st.session_state.is_demo:
    st.markdown('''<div class="sample-notice"><strong>FICTIONAL EXAMPLE:</strong> These three rectangles and every grade, acreage and environmental measurement in the demonstration are invented to explain how the website works. They are NOT findings about actual Cedar Falls properties.</div>''', unsafe_allow_html=True)
    if st.button('↶ Leave example and choose my own locations', key='leave_demo'):
        st.session_state.sites = []
        st.session_state.results = {}
        st.session_state.is_demo = False
        previous = st.session_state.demo_return or {}
        st.session_state.community = previous.get('community','Cedar Falls, Iowa')
        st.session_state.center = previous.get('center',[42.5349,-92.4453])
        st.session_state.zoom = previous.get('zoom',12)
        st.session_state.state = previous.get('state','Iowa')
        st.session_state.demo_return = None
        clear_restoration()
        st.rerun()
else:
    if st.button('▶ Try an example — explore three fictional sites instantly', key='load_demo'):
        st.session_state.demo_return = {
            'community':st.session_state.community,
            'center':st.session_state.center,
            'zoom':st.session_state.zoom,
            'state':st.session_state.state,
        }
        st.session_state.sites, st.session_state.results = make_demo()
        st.session_state.is_demo = True
        st.session_state.center = [42.5349, -92.4453]
        st.session_state.zoom = 12
        st.session_state.community = 'Cedar Falls area — fictional example'
        st.session_state.state = 'Iowa'
        clear_restoration()
        st.rerun()

current_step = wizard_step(st.session_state.sites, st.session_state.results)
steps = [
    ('Choose locations', 'Draw and save 2–5 rectangles'),
    ('Compare biodiversity', 'Review mapped concerns and grades'),
    ('Explore restoration', 'Optional next step'),
]
step_html=[]
for index,(name,detail) in enumerate(steps,1):
    stage='active' if index==current_step else ('done' if index<current_step else '')
    label='CURRENT STEP' if index==current_step else ('DONE' if index<current_step else 'UP NEXT')
    step_html.append(f'<div class="step-tile {stage}"><div class="step-number">{index} / {label}</div>'
        f'<div class="step-name">{name}</div><div class="step-detail">{detail}</div></div>')
st.markdown('<div class="step-strip">'+''.join(step_html)+'</div>',unsafe_allow_html=True)

analyze = False
left, right = st.columns([1.8, 1], gap="large")
with left:
    st.markdown('''<div class="section-head"><div><h2>Explore & select sites</h2>
        <p>Draw a footprint for each potential data-center location.</p></div>
        <span class="section-pill">Interactive map</span></div>''', unsafe_allow_html=True)
    m = folium.Map(
        location=st.session_state.center,
        zoom_start=st.session_state.zoom,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
    )
    folium.TileLayer("OpenStreetMap", name="Street map", overlay=False, show=True).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, Maxar, Earthstar Geographics and the GIS User Community",
        name="Satellite", overlay=False, show=False,
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
            "polygon": False,
            "rectangle": {"shapeOptions": {"color": "#145f56"}},
        },
        edit_options={"edit": False, "remove": False},
    ).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    map_response = st_folium(
        m, height=510, use_container_width=True,
        key=f"ecosite_map_{len(st.session_state.sites)}_{int(st.session_state.is_demo)}",
        returned_objects=["last_active_drawing"],
    )
    drawn = (map_response or {}).get("last_active_drawing")
    st.markdown('<div class="begin-tip"><strong>Step 1:</strong> Choose the rectangle icon on the map, drag to outline a possible site, then click the button below. EcoSite names it automatically.</div>', unsafe_allow_html=True)
    new_label = next_site_name(st.session_state.sites)
    if st.button(f"＋ Add location as {new_label}", use_container_width=True,
                 disabled=len(st.session_state.sites) >= 5 or st.session_state.is_demo):
        if not drawn:
            st.warning("Select the rectangle tool at the top-left of the map and draw a possible location first.")
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
                show_helpful_error('draw', exc)
    st.caption("Draw hypothetical footprints, not just map pins. The site map covers the contiguous U.S.; real-world construction would require parcel, zoning and engineering checks.")

with right:
    st.markdown('''<div class="section-head"><div><h2>Your locations</h2>
      <p>Choose 2–5 places to compare side by side.</p></div></div>''', unsafe_allow_html=True)
    if not st.session_state.sites:
        st.info("Start with the rectangle icon on the map. Draw your first location, then click **Add location as Site A** below the map. Repeat for Site B.")
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
    if not st.session_state.is_demo:
        if len(st.session_state.sites) >= 2:
            st.success('Your locations are ready. Select **Compare my locations** below.')
        else:
            st.caption('Add at least two rectangles before comparing.')
        analyze = st.button('Compare my locations', type='primary', use_container_width=True,
            disabled=len(st.session_state.sites) < 2, key='compare_my_locations')
        if st.session_state.sites:
            a,b = st.columns(2)
            with a:
                if st.button('Remove last', use_container_width=True):
                    removed=st.session_state.sites.pop()
                    st.session_state.results.pop(removed['id'],None)
                    st.session_state.results={}
                    clear_restoration()
                    st.rerun()
            with b:
                if st.button('Clear all', use_container_width=True):
                    st.session_state.sites=[]
                    st.session_state.results={}
                    clear_restoration()
                    st.rerun()
    else:
        st.info('Sample comparison loaded. Leave example mode above to analyze real user-drawn rectangles.')
    st.markdown("#### What the current screening checks")
    st.markdown("**USGS land cover:** estimates natural or wetland cover inside each footprint.")
    st.markdown("**USFWS wetlands inventory:** checks mapped aquatic overlap and nearby features (within 500 m).")
    st.markdown('''<div class="notice"><strong>Research preview:</strong> The A–F grades are based only on these two mapped layers. They do not assess threatened species, connectivity, water use, utilities or noise, and do not establish whether construction is safe or permitted.</div>''', unsafe_allow_html=True)

if analyze:
    new_results = {}
    progress = st.progress(0, text="Requesting live environmental map data…")
    for i, site in enumerate(st.session_state.sites):
        with st.spinner(f"Checking environmental layers for {site['name']}…"):
            try:
                new_results[site["id"]] = analyze_site(site["feature"])
            except Exception as exc:
                progress.empty()
                show_helpful_error('compare',exc)
                st.stop()
        progress.progress((i + 1) / len(st.session_state.sites),
                          text=f"Completed {i + 1} of {len(st.session_state.sites)}")
    st.session_state.results = new_results
    clear_restoration()
    st.rerun()

if st.session_state.results:
    st.divider()
    st.markdown('''<div class="section-head"><div><h2>Comparison results</h2>
       <p>Each site receives a preliminary environmental letter grade and an explanation.</p>
       </div><span class="section-pill">A = lower concern · F = higher concern</span></div>''', unsafe_allow_html=True)
    completed = [(s, st.session_state.results[s["id"]]) for s in st.session_state.sites
                 if s["id"] in st.session_state.results]
    conclusion = best_preliminary_option(st.session_state.sites,st.session_state.results)
    if conclusion.get('winner'):
        preferred = conclusion['winner']
        preferred_grade = conclusion['result']['grade']['grade']
        notes_html = ''.join('<span>• '+escape(note)+'</span>' for note in conclusion['reasons'][:2])
        st.markdown(
            f'<div class="comparison-banner"><div style="font-size:2rem">✓</div>'
            f'<div><strong>Best preliminary option: {escape(preferred["name"])} · Grade {escape(preferred_grade)}</strong>'
            f'{notes_html}<span>Not proof of ecological safety or construction feasibility. Five important factors remain unassessed.</span>'
            '</div></div>',unsafe_allow_html=True)
    else:
        st.warning('No clear preliminary winner: '+conclusion['reason'])
    if st.session_state.is_demo:
        st.warning('DEMONSTRATION ONLY: the following grades and measurements are synthetic, not live environmental evidence.')
    st.markdown('<div class="grade-grid">' + ''.join(site_card(s, r) for s, r in completed) + '</div>',unsafe_allow_html=True)

    report=[]
    for site,result in completed:
        land = result['land']
        wet = result['wet']
        grade = result['grade']
        report.append({
            'Site':site['name'],
            'Preliminary grade':grade['grade'],
            'Why this grade':grade['explanation'],
            'Footprint (acres)':result['area_acres'],
            'Estimated mapped natural / wetland cover (acres)':land['natural_est_acres'] if land else 'Unknown',
            'Developed cover (%)':land['already_developed_pct'] if land else 'Unknown',
            'NWI aquatic overlap (acres)':wet['overlap_acres'] if wet else 'Unknown',
            'Nearest mapped NWI feature (meters)':(
                (wet['nearest_m'] if wet['nearest_m'] is not None else 'None mapped within 500 m') if wet else 'Unknown'),
            'Screening flag':result['flag'],
            'Data gaps':json.dumps(result['issues']),
            'Data type':'SYNTHETIC EXAMPLE — not GIS measurements' if st.session_state.is_demo else 'Live GIS screening',
        })

    st.markdown("### Detailed comparison")
    st.dataframe(report, use_container_width=True, hide_index=True)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(report[0].keys()))
    writer.writeheader()
    writer.writerows(report)
    st.download_button(
        "↓ Download report (CSV)", output.getvalue(),
        file_name="ecosite_biodiversity_comparison_v8.csv",
        mime="text/csv", use_container_width=False,
    )
    try:
        pdf_bytes=build_one_page_report(st.session_state.sites, st.session_state.results,
            community=st.session_state.community,
            restoration_plan=st.session_state.restoration_plan,
            demo=st.session_state.is_demo)
        st.download_button('↓ Download one-page printable PDF (with footprint map)',
            pdf_bytes,file_name='ecosite_one_page_community_brief.pdf',
            mime='application/pdf',use_container_width=True,key='pdf_download')
    except Exception as exc:
        show_helpful_error('pdf',exc)
    st.caption('PDF map shows relative site boundaries only; street and ecological map tiles are not included. Synthetic example reports are prominently labeled.')
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
            if result['issues']:
                st.warning('One or more environmental map services did not return usable data. Try comparing again later.')
                with st.expander('Technical map-service details (for support)'):
                    st.json(result['issues'])
            st.caption("Unassessed: threatened species, fragmentation, water demand, infrastructure and wildlife disturbance.")


# Optional second stage: potential restoration on a distinct patch of land. This
# never changes the A–F construction-site grading and never certifies offsets.
if st.session_state.results and st.session_state.is_demo:
    st.markdown('### Optional next step: restore habitat')
    st.info('In a real comparison, the Restoration Planner can examine land near the construction site or another candidate property, and suggest conditional native plants. Leave the fictional example to try it with actual mapped sites.')

if st.session_state.results and len(st.session_state.sites) >= 2 and not st.session_state.is_demo:
    st.divider()
    st.markdown('''<div class="restore-hero"><div class="kicker">Optional / Phase 2</div>
       <h3>Explore a biodiversity restoration plan</h3>
       <p>After comparing places to build, investigate how your community could protect or restore habitat on nearby land or on one of the other candidate sites. The planner uses mapped land cover to suggest actions to investigate — it does <strong>not</strong> calculate a certified biodiversity offset or erase damage from building.</p></div>''', unsafe_allow_html=True)
    st.toggle('Open the optional Restoration Planner', key='restoration_enabled')
    if st.session_state.restoration_enabled:
        with st.container(border=True):
            sites_by_id = {site['id']: site for site in st.session_state.sites}
            options = [site['id'] for site in st.session_state.sites
                       if site['id'] in st.session_state.results]
            if st.session_state.get('restoration_build_site') not in options:
                st.session_state['restoration_build_site'] = options[0]
            st.markdown('### 1 · Choose the data-center development site')
            development_id = st.selectbox(
                'Which compared location would be developed?', options,
                format_func=lambda sid: sites_by_id[sid]['name'],
                key='restoration_build_site', on_change=clear_restoration,
            )
            development = sites_by_id[development_id]
            build_grade = st.session_state.results[development_id]['grade']['grade']
            st.caption(f'This development site retains its original grade ({build_grade}). Restoration ideas cannot change that construction grade.')

            st.markdown('### 2 · Choose where to explore restoration')
            modes = {
                'nearby': 'Restore land near my building',
                'alternate': 'Restore land at another candidate site',
            }
            if st.session_state.get('restoration_mode') not in (None,*modes):
                st.session_state['restoration_mode'] = None
            st.markdown('**Choose one restoration approach to see the relevant controls.**')
            mode = st.radio('Where would you like to explore restoration?', list(modes),
                            format_func=lambda k: modes[k],
                            key='restoration_mode', on_change=clear_restoration,
                            index=None, horizontal=True)
            if mode is None:
                st.info("Choose one of the two options above to continue. Planting and map details will appear after you choose.")
            else:
                alternative = None
                if mode == 'alternate':
                    alternate_ids = [sid for sid in options if sid != development_id]
                    if st.session_state.get('restoration_alternate') not in alternate_ids:
                        st.session_state['restoration_alternate'] = alternate_ids[0]
                    alt_id = st.selectbox(
                        'Unused candidate property', alternate_ids,
                        format_func=lambda sid: sites_by_id[sid]['name'],
                        key='restoration_alternate', on_change=clear_restoration,
                    )
                    alternative = sites_by_id[alt_id]
                    st.caption('Choose the whole unused candidate for a preliminary review, or draw a smaller part of it. Ownership and availability are not confirmed.')
                    if st.button('Use the whole unused candidate area',
                                 use_container_width=True, key='restoration_entire_candidate'):
                        try:
                            validate_restoration_area(development['feature'], alternative['feature'],
                                                      'alternate', alternative['feature'])
                            st.session_state.restoration_geometry = alternative['feature']
                            st.session_state.restoration_source_name = alternative['name']
                            st.session_state.restoration_reuse_id = alt_id
                            st.session_state.restoration_analysis = None
                            st.session_state.restoration_plan = None
                            st.rerun()
                        except ValueError as exc:
                            show_helpful_error('restore', exc)
                else:
                    st.caption('Draw a separate potential planting area outside the building footprint, within 500 m. It could be landscaping on the same parcel or nearby land, but parcel boundaries and ownership are not verified. To plan landscaping inside the current outline, first redraw that outline as the actual construction footprint.')

                with st.expander('Optional planting details: sun and soil moisture', expanded=False):
                    st.markdown('Planting choices are optional. Open the settings below for an Iowa native-plant shortlist.')
                    st.caption('Choose conditions observed on the potential planting area. The map does not measure shade, soil moisture or actual planting suitability.')
                    light_label = {'unknown':'Not checked yet', 'sun':'Mostly full sun',
                                   'shade':'Part shade or shade'}
                    moisture_label = {'unknown':'Not checked yet', 'dry':'Dry or well drained',
                                      'average':'Average / moderately moist', 'wet':'Moist to wet'}
                    lcol, scol = st.columns(2)
                    with lcol:
                        plant_light = st.selectbox('Sun exposure',list(light_label),
                            format_func=lambda v: light_label[v],key='plant_light',
                            on_change=clear_restoration_plan_only)
                    with scol:
                        plant_moisture = st.selectbox('Typical soil moisture',list(moisture_label),
                            format_func=lambda v: moisture_label[v],key='plant_moisture',
                            on_change=clear_restoration_plan_only)
                    if (st.session_state.state or '').casefold() != 'iowa':
                        st.info('Curated species examples currently cover Iowa only. Plant recommendations use a location check on the selected restoration rectangle when you analyze it; other states require local species guidance.')
                    elif plant_light == 'unknown' or plant_moisture == 'unknown':
                        st.info('To see suggested Iowa native species, select both sun exposure and soil moisture. The suggestions will still require an on-site check.')
                    confirm_iowa = st.checkbox(
                        'I confirm this potential restoration area is in Iowa (backup if map location lookup fails)',
                        value=False, key='plant_iowa_confirmation',
                        on_change=clear_restoration_plan_only,
                        help='A user confirmation is used only if the automatic state lookup is unavailable. A confirmed non-Iowa state takes precedence.',
                    )

                st.markdown('### 4 · Outline land to restore')
                center_geom = ensure_polygon(development['feature'])
                restoration_map = folium.Map(location=[center_geom.centroid.y, center_geom.centroid.x],
                                             zoom_start=14, tiles=None, control_scale=True)
                folium.TileLayer('OpenStreetMap', name='Street map', overlay=False, show=True).add_to(restoration_map)
                folium.TileLayer(
                    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                    attr='Esri, Maxar, Earthstar Geographics and the GIS User Community',
                    name='Satellite', overlay=False, show=False,
                ).add_to(restoration_map)
                # Distinct outline colors, labels and explanatory controls improve clarity.
                folium.GeoJson(development['feature'], name='Proposed construction footprint',
                               style_function=lambda _: {'color':'#a32d3c','weight':4,
                                                         'fillColor':'#d95161','fillOpacity':.22},
                               tooltip=f"Building footprint: {development['name']}").add_to(restoration_map)
                bounds = list(center_geom.bounds)
                if alternative:
                    alt_geom = ensure_polygon(alternative['feature'])
                    folium.GeoJson(alternative['feature'], name='Other candidate for restoration',
                                   style_function=lambda _: {'color':'#2265a0','weight':4,
                                                             'fillColor':'#3383c4','fillOpacity':.16},
                                   tooltip=f"Potential restoration site: {alternative['name']}").add_to(restoration_map)
                    ab = alt_geom.bounds
                    bounds = [min(bounds[0], ab[0]), min(bounds[1], ab[1]),
                              max(bounds[2], ab[2]), max(bounds[3], ab[3])]
                if st.session_state.restoration_geometry:
                    restore_geom = ensure_polygon(st.session_state.restoration_geometry)
                    folium.GeoJson(st.session_state.restoration_geometry, name='Selected restoration area',
                                   style_function=lambda _: {'color':'#0b6e48','weight':4,
                                                             'fillColor':'#24a46c','fillOpacity':.35},
                                   tooltip='Restoration area for preliminary review').add_to(restoration_map)
                    rb = restore_geom.bounds
                    bounds = [min(bounds[0], rb[0]), min(bounds[1], rb[1]),
                              max(bounds[2], rb[2]), max(bounds[3], rb[3])]
                restoration_map.fit_bounds([[bounds[1],bounds[0]],[bounds[3],bounds[2]]], padding=(40,40))
                Draw(export=False, draw_options={
                    'polyline':False,'marker':False,'circle':False,'circlemarker':False,
                    'polygon':False,
                    'rectangle':{'shapeOptions':{'color':'#0b6e48'}},
                }, edit_options={'edit':False,'remove':False}).add_to(restoration_map)
                folium.LayerControl(collapsed=True).add_to(restoration_map)
                restore_map_response = st_folium(restoration_map, height=390,
                                                 use_container_width=True,
                                                 key=f'restoration_map_v8_{mode}_{development_id}_{len(options)}',
                                                 returned_objects=['last_active_drawing'])
                restored_drawn = (restore_map_response or {}).get('last_active_drawing')
                b1,b2 = st.columns([2,1])
                with b1:
                    if st.button('✓ Use drawn restoration area', use_container_width=True,
                                 key='confirm_restoration_rectangle'):
                        if not restored_drawn:
                            st.warning('Use the rectangle tool in the top-left of the map before clicking this button.')
                        else:
                            try:
                                polygon = ensure_polygon(restored_drawn)
                                feature = {'type':'Feature','geometry':mapping(polygon),'properties':{}}
                                validate_restoration_area(
                                    development['feature'], feature, mode,
                                    alternative['feature'] if alternative else None)
                                st.session_state.restoration_geometry = feature
                                st.session_state.restoration_source_name = (
                                    f"Part of {alternative['name']}" if alternative else
                                    f"Nearby land by {development['name']}")
                                st.session_state.restoration_reuse_id = None
                                st.session_state.restoration_plan = None
                                st.session_state.restoration_analysis = None
                                st.rerun()
                            except ValueError as exc:
                                show_helpful_error('restore', exc)
                with b2:
                    if st.button('Clear restoration area', use_container_width=True,
                                 key='clear_restoration_area'):
                        clear_restoration()
                        st.rerun()
                st.caption('Red = proposed building footprint · Blue = alternate compared site · Green = restoration area. New plantings must be planned outside the building footprint; the map does not verify property ownership.')

                area_feature = st.session_state.restoration_geometry
                if area_feature:
                    try:
                        placement = validate_restoration_area(
                            development['feature'], area_feature, mode,
                            alternative['feature'] if alternative else None)
                        st.success(f"Restoration rectangle selected: {placement['area_acres']:.2f} acres · approximately {placement['distance_from_build_m']} m from the construction footprint")
                        if st.button('Analyze restoration opportunities', type='primary',
                                     use_container_width=True, key='analyze_restoration'):
                            with st.spinner('Checking the mapped vegetation and aquatic features…'):
                                reuse_id = st.session_state.restoration_reuse_id
                                if reuse_id and reuse_id == (alternative or {}).get('id'):
                                    previous = st.session_state.results[reuse_id]
                                    assessment = {
                                        'area_acres': previous['area_acres'],
                                        'land': previous['land'], 'wet': previous['wet'],
                                        'issues': previous['issues'],
                                        'analyzed_utc': previous['analyzed_utc'],
                                    }
                                else:
                                    assessment = analyze_restoration_area(area_feature)
                                # The actual selected restoration polygon can be far from
                                # the searched town; reverse geocode its center for plant state.
                                # If unavailable, do not attribute Iowa plant nativity to it.
                                restoration_polygon = ensure_polygon(area_feature)
                                try:
                                    plant_state = state_at_coordinates(
                                        restoration_polygon.centroid.y,
                                        restoration_polygon.centroid.x)
                                except (requests.RequestException, ValueError):
                                    plant_state = None
                                if plant_state is None and confirm_iowa:
                                    plant_state = 'Iowa'  # explicit user-confirmed fallback
                                plan = make_restoration_plan(
                                    st.session_state.results[development_id], assessment,
                                    placement, development_name=development['name'],
                                    location_name=st.session_state.restoration_source_name,
                                    plant_context={'state': plant_state,
                                                   'sunlight':plant_light, 'soil_moisture':plant_moisture},
                                )
                                st.session_state.restoration_analysis = assessment
                                st.session_state.restoration_plan = plan
                            st.rerun()
                        # A remote request or unexpected parsing problem is not a
                        # user mistake; report what to try, not a raw traceback.
                    except Exception as exc:
                        show_helpful_error('restore', exc)

                plan = st.session_state.restoration_plan
                if plan:
                    st.divider()
                    st.markdown('### 5 · Your preliminary restoration opportunity plan')
                    acreage = f"{plan['restoration_acres']:.2f} acres"
                    potential = (f"~{plan['estimated_modifiable_cover_acres']:.2f} acres" if
                                 plan['estimated_modifiable_cover_acres'] is not None else 'Unknown')
                    st.markdown(f'''<div class="meta-strip">
                      <div class="restoration-stat"><div class="value">{escape(acreage)}</div><div class="label">Area explored</div><div class="description">User-selected restoration rectangle</div></div>
                      <div class="restoration-stat"><div class="value">{escape(potential)}</div><div class="label">Potentially modifiable mapped cover</div><div class="description">Estimated turf/open developed + agricultural cover — not verified plantable area</div></div>
                      <div class="restoration-stat"><div class="value">Not calculated</div><div class="label">Verified biodiversity offset</div><div class="description">Requires specialist evaluation and ecological equivalence</div></div>
                    </div>''',unsafe_allow_html=True)
                    st.markdown('**Possible actions to investigate**')
                    if plan['development_mapped_natural_acres'] is not None:
                        st.info(
                            f"The construction footprint for **{plan['development_name']}** includes about "
                            f"**{plan['development_mapped_natural_acres']:.2f} acres** of mapped natural/wetland cover. "
                            'This cannot be directly balanced against potential planting acres: "acres restored" do not equal "acres of biodiversity loss offset."'
                        )
                    cards = []
                    for action in plan['actions']:
                        cards.append(f'''<article class="restoration-action"><span class="small-badge">{escape(action['step'])}</span>
                            <h4>{escape(action['title'])}</h4><p>{escape(action['rationale'])}</p>
                            <div class="verify"><strong>Check first:</strong> {escape(action['verify'])}</div></article>''')
                    st.markdown(''.join(cards), unsafe_allow_html=True)
                    st.markdown('### Native plants to investigate')
                    planting = plan['native_plant_guidance']
                    st.markdown(f'<div class="plant-guidance"><strong>Planting guidance:</strong> {escape(planting["note"])}</div>',unsafe_allow_html=True)
                    if planting['items']:
                        st.markdown('<div class="plant-header">Iowa native-plant shortlist · verify locally before buying seed or planting</div>',unsafe_allow_html=True)
                        plants_html=[]
                        for plant in planting['items']:
                            plants_html.append(
                                f'<article class="plant-entry"><div class="plant-name">{escape(plant["common"])}</div>'
                                f'<div class="plant-scientific">{escape(plant["scientific"])}</div>'
                                f'<div class="plant-role">{escape(plant["role"])}</div></article>')
                        st.markdown('<div class="plant-grid">'+''.join(plants_html)+'</div>',unsafe_allow_html=True)
                    if planting['sources']:
                        with st.expander('Plant sources and verification guidance'):
                            for source in planting['sources']:
                                st.markdown(f'- [{source["title"]}]({source["url"]})')
                            st.caption('Use locally sourced native seed, protect intact ecosystems, and ask a local land manager or conservation biologist to approve the final species mix.')
                    st.warning('Important limits: ' + ' '.join(plan['warnings']))
                    if plan['issues']:
                        st.warning('Some map services were unavailable. Restoration actions are preliminary and may be incomplete.')
                        with st.expander('Technical map-service details (for support)'):
                            st.json(plan['issues'])
                    st.download_button('↓ Download restoration plan (.md)', plan_markdown(plan),
                                       file_name='ecosite_restoration_opportunity_plan.md',
                                       mime='text/markdown', use_container_width=True)
                    st.caption('Sources: USGS annual land cover, USFWS aquatic map, Society for Ecological Restoration (2026), and IUCN mitigation hierarchy. No ecological equivalence, cost or suitability is certified.')
    else:
        st.caption('Restoration planning is optional. Open it only after comparing potential construction locations.')

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
