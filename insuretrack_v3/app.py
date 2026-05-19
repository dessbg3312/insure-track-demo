"""
InsureTrack — Insurance Portfolio Manager
Single-file Streamlit app. Works on Streamlit Cloud without extra config.
"""
import json, os, base64, subprocess, tempfile
from pathlib import Path
from datetime import date, datetime

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# ── PAGE CONFIG ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InsureTrack",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── PATHS ──────────────────────────────────────────────────────────────
_ROOT         = Path(__file__).parent
_DATA_DIR     = _ROOT / "data"
_CLIENTS_FILE = _ROOT / "clients.json"

# ══════════════════════════════════════════════════════════════════════
# DATA LAYER
# ══════════════════════════════════════════════════════════════════════
def _use_supabase():
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"))

def _sb():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def load_clients():
    if _use_supabase():
        rows = _sb().table("clients").select("*").execute().data
        return {r["id"]: {"name": r["name"], "password": r["password"]} for r in rows}
    if _CLIENTS_FILE.exists():
        return json.loads(_CLIENTS_FILE.read_text())
    return {}

def load_portfolio(client_id):
    if _use_supabase():
        rows = _sb().table("portfolios").select("*").eq("client_id", client_id).execute().data
        if rows:
            r = rows[0]
            return {"portfolio_name": r["portfolio_name"],
                    "properties":    r["properties"]    or [],
                    "policies":      r["policies"]      or [],
                    "auto_policies": r["auto_policies"] or []}
    else:
        path = _DATA_DIR / client_id / "portfolio.json"
        if path.exists():
            return json.loads(path.read_text())
    return {"portfolio_name": client_id, "properties": [], "policies": [], "auto_policies": []}

def save_portfolio(client_id, data):
    if _use_supabase():
        _sb().table("portfolios").upsert({
            "client_id":      client_id,
            "portfolio_name": data.get("portfolio_name", client_id),
            "properties":     data.get("properties",    []),
            "policies":       data.get("policies",      []),
            "auto_policies":  data.get("auto_policies", []),
        }).execute()
    else:
        path = _DATA_DIR / client_id / "portfolio.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))

def save_pdf(client_id, filename, content_bytes):
    if _use_supabase():
        sb = _sb(); fpath = f"{client_id}/{filename}"
        try:
            sb.storage.from_("pdfs").upload(fpath, content_bytes, {"content-type":"application/pdf"})
        except Exception:
            try: sb.storage.from_("pdfs").update(fpath, content_bytes, {"content-type":"application/pdf"})
            except Exception: return ""
        return sb.storage.from_("pdfs").get_public_url(fpath)
    else:
        d = _DATA_DIR / client_id / "pdfs"; d.mkdir(parents=True, exist_ok=True)
        (d / filename).write_bytes(content_bytes)
        return str(d / filename)

# ══════════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── BASE ── */
.stApp { background: #F0F4FF !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem !important; max-width: 1400px !important; }

/* ── SIDEBAR ── */
[data-testid="stSidebar"] { background: #1A1F3C !important; border-right: 1px solid #2D3561; }
[data-testid="stSidebar"], [data-testid="stSidebar"] p,
[data-testid="stSidebar"] span, [data-testid="stSidebar"] div,
[data-testid="stSidebar"] label { color: #D4DCF5 !important; }
[data-testid="stSidebar"] hr { border-color: #2D3561 !important; margin: 10px 0 !important; }
[data-testid="stSidebar"] .stButton > button {
  border-radius: 8px !important; font-size: 13px !important; font-weight: 500 !important;
  text-align: left !important; padding: 9px 14px !important; margin: 2px 0 !important;
  width: 100% !important; transition: all 0.15s !important; border: none !important;
}
[data-testid="stSidebar"] .stButton > button[kind="secondary"],
[data-testid="stSidebar"] .stButton > button[kind="secondary"] p,
[data-testid="stSidebar"] .stButton > button[kind="secondary"] span {
  background: rgba(255,255,255,0.05) !important; color: #D4DCF5 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
  background: #252C52 !important; color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[kind="primary"] p,
[data-testid="stSidebar"] .stButton > button[kind="primary"] span {
  background: #4F6EF7 !important; color: #FFFFFF !important;
}

/* ── ALL LABELS & INPUTS ── */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label { color: #374151 !important; font-size:12px !important; font-weight:600 !important; }
.stTextInput input, .stNumberInput input, .stTextArea textarea {
  background:#FFFFFF !important; color:#1A1F3C !important;
  border:1px solid #CBD5E1 !important; border-radius:8px !important;
}
.stTextInput label, .stNumberInput label, .stTextArea label,
.stSelectbox label, .stDateInput label, .stMultiSelect label, .stFileUploader label {
  color:#374151 !important; font-size:12px !important; font-weight:600 !important;
}
.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div {
  background:#FFFFFF !important; color:#1A1F3C !important;
  border:1px solid #CBD5E1 !important; border-radius:8px !important;
}
.stDateInput [data-baseweb="input"] > div {
  background:#FFFFFF !important; color:#1A1F3C !important; border-radius:8px !important;
}
.stRadio div[role="radiogroup"] label,
.stRadio div[role="radiogroup"] label span,
.stRadio div[role="radiogroup"] label p { color:#1A1F3C !important; font-size:13px !important; }
.stCheckbox label span, .stCheckbox label p { color:#1A1F3C !important; font-size:13px !important; }
[data-testid="stMetricLabel"] p { color:#8896B3 !important; font-size:11px !important; font-weight:600 !important; text-transform:uppercase; letter-spacing:.05em; }
[data-testid="stMetricValue"] { color:#1A1F3C !important; }
[data-testid="stForm"] {
  background:#FFFFFF !important; border:1px solid #E4EAF8 !important;
  border-radius:12px !important; padding:16px !important;
}
[data-testid="stForm"] h5 { color:#4F6EF7 !important; font-size:13px !important; }
[data-testid="stFileUploader"] { background:#F8FAFF !important; border:1px dashed #CBD5E1 !important; border-radius:8px !important; }
.stTabs [data-baseweb="tab"] { color:#374151 !important; font-weight:600 !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { color:#4F6EF7 !important; }

/* ── DATAFRAME ── */
[data-testid="stDataFrame"] { border-radius:10px !important; border:1px solid #E4EAF8 !important; overflow:hidden !important; }
[data-testid="stDataFrame"] > div { background:#FFFFFF !important; }

/* ── CONTAINER WITH BORDER ── */
[data-testid="stVerticalBlockBorderWrapper"] {
  background:#FFFFFF !important; border-radius:14px !important; border:1px solid #E4EAF8 !important;
}

/* ══════════════════════════════════════════════════════
   FILTER PANEL BUTTONS
   (inside st.container(border=True) = stVerticalBlockBorderWrapper)
   ══════════════════════════════════════════════════════ */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stButton"] > button {
  background: transparent !important;
  border: 1px solid transparent !important;
  color: #374151 !important;
  justify-content: flex-start !important;
  text-align: left !important;
  padding: 7px 10px !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  border-radius: 8px !important;
  margin: 1px 0 !important;
  line-height: 1.3 !important;
  min-height: 36px !important;
  transition: all 0.1s !important;
  width: 100% !important;
}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stButton"] > button:hover {
  background: rgba(79,110,247,0.06) !important;
}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stButton"] > button[kind="primary"] {
  background: #EEF2FF !important;
  border: 1px solid #C7D2FE !important;
  color: #4F6EF7 !important;
  font-weight: 700 !important;
}

/* ══════════════════════════════════════════════════════
   LIST ROW DAYS BUTTON  (4th column of each row)
   ══════════════════════════════════════════════════════ */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(4) [data-testid="stButton"] > button {
  background: transparent !important;
  border: none !important;
  padding: 2px 4px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  justify-content: flex-end !important;
  text-align: right !important;
  line-height: 1.2 !important;
}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(4) [data-testid="stButton"] > button:hover {
  background: rgba(0,0,0,0.04) !important;
  border-radius: 6px !important;
}

/* ── KPI CARDS ── */
.kpi-card { background:#fff; border:1px solid #E4EAF8; border-radius:14px; padding:18px 20px; position:relative; overflow:hidden; }
.kpi-card::before { content:""; position:absolute; top:0; left:0; right:0; height:4px; border-radius:14px 14px 0 0; }
.kpi-card.blue::before   { background:#4F6EF7; }
.kpi-card.green::before  { background:#10B981; }
.kpi-card.orange::before { background:#F59E0B; }
.kpi-card.purple::before { background:#8B5CF6; }
.kpi-icon  { font-size:20px; margin-bottom:6px; display:block; }
.kpi-label { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.07em; color:#8896B3; }
.kpi-value { font-size:24px; font-weight:700; color:#1A1F3C; margin-top:2px; }
.kpi-sub   { font-size:11px; color:#A0AECE; margin-top:3px; }
.section-hdr { font-size:11px; font-weight:700; color:#4F6EF7; letter-spacing:.08em; text-transform:uppercase; border-bottom:2px solid #E4EAF8; padding-bottom:6px; margin:24px 0 14px; }
.flag-amber { background:#FFFBEB; border-left:3px solid #F59E0B; padding:7px 14px; border-radius:0 8px 8px 0; margin:4px 0; font-size:13px; color:#78350F; }
.flag-red   { background:#FEF2F2; border-left:3px solid #EF4444; padding:7px 14px; border-radius:0 8px 8px 0; margin:4px 0; font-size:13px; color:#7F1D1D; }
.flag-green { background:#F0FDF4; border-left:3px solid #10B981; padding:7px 14px; border-radius:0 8px 8px 0; margin:4px 0; font-size:13px; color:#14532D; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# DETAIL CARD CSS  (injected per-page that needs it)
# ══════════════════════════════════════════════════════════════════════
_DET_CSS = """<style>
/* ── Filter panel helpers ── */
.fpanel-hdr { font-size:11px; font-weight:800; letter-spacing:.10em; color:#374151; text-transform:uppercase; margin-bottom:12px; }
.fpanel-sec { font-size:10px; font-weight:700; letter-spacing:.07em; color:#9CA3AF; text-transform:uppercase; margin:14px 0 4px; }

/* ── Icon badges for list rows ── */
.pol-badge {
  width:38px; height:38px; min-width:38px; border-radius:10px;
  display:flex; align-items:center; justify-content:center;
  font-size:16px; flex-shrink:0; margin-top:3px;
}
.badge-warn  { background:#FFF7ED; border:1.5px solid #FED7AA; }
.badge-quote { background:#EDE9FE; border:1.5px solid #DDD6FE; }
.badge-res   { background:#DCFCE7; border:1.5px solid #BBF7D0; }
.badge-umb   { background:#EEF2FF; border:1.5px solid #C7D2FE; }
.badge-exp   { background:#FEF2F2; border:1.5px solid #FECACA; }
.badge-comm  { background:#EFF6FF; border:1.5px solid #BFDBFE; }
.badge-auto  { background:#FFFBEB; border:1.5px solid #FDE68A; }
.badge-prop  { background:#F0FDF4; border:1.5px solid #BBF7D0; }

/* ── Detail card ── */
.det-card { background:#fff; border:1px solid #E4EAF8; border-radius:14px; padding:24px 28px; margin-top:16px; }
.det-hdr { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:16px; gap:12px; }
.det-title { font-size:18px; font-weight:700; color:#1A1F3C; line-height:1.2; }
.det-meta { font-size:12px; color:#8896B3; margin-top:4px; line-height:1.5; }
.det-divider { border:none; border-top:1px solid #E4EAF8; margin:14px 0; }
.det-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(145px,1fr)); gap:14px 18px; margin-bottom:14px; }
.det-field .dk { font-size:10px; text-transform:uppercase; letter-spacing:.06em; color:#8896B3; font-weight:700; margin-bottom:3px; }
.det-field .dv { font-size:13px; color:#1A1F3C; font-weight:600; line-height:1.3; }
/* Status pills */
.status-pill { font-size:11px; font-weight:700; padding:4px 14px; border-radius:20px; white-space:nowrap; display:inline-block; }
.pill-active  { background:#DCFCE7; color:#166534; }
.pill-quote   { background:#EDE9FE; color:#4C1D95; }
.pill-expired { background:#FEF2F2; color:#991B1B; }
.pill-auto    { background:#FFF7ED; color:#9A3412; }
.pill-prop    { background:#EEF2FF; color:#3730A3; }
/* Tags */
.tag-row { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
.tag { display:inline-block; font-size:11px; font-weight:600; padding:3px 10px; border-radius:20px; background:#EEF2FF; color:#4338CA; }
.tag.urgent { background:#FEF2F2; color:#991B1B; }
.tag.amber  { background:#FFFBEB; color:#92400E; }
.tag.green  { background:#F0FDF4; color:#166534; }
.tag.purple { background:#EDE9FE; color:#4C1D95; }
.tag.gray   { background:#F1F5F9; color:#475569; }
/* Alert banners */
.alert-banner { display:flex; align-items:flex-start; gap:10px; padding:10px 16px; border-radius:10px; margin-top:12px; font-size:13px; }
.alert-red   { background:#FEF2F2; border-left:4px solid #EF4444; color:#991B1B; }
.alert-amber { background:#FFFBEB; border-left:4px solid #F59E0B; color:#92400E; }
.alert-blue  { background:#EFF6FF; border-left:4px solid #3B82F6; color:#1E40AF; }
.alert-green { background:#F0FDF4; border-left:4px solid #10B981; color:#166534; }
.alert-icon { font-size:15px; flex-shrink:0; margin-top:1px; }
.alert-text { line-height:1.5; }
.alert-text strong { display:block; font-weight:700; margin-bottom:1px; }
/* Notes */
.notes-box { background:#FAFBFF; border:1px solid #E4EAF8; border-radius:8px; padding:10px 14px; margin-top:10px; font-size:12px; color:#374151; line-height:1.6; }
.notes-lbl { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:#8896B3; margin-bottom:4px; }
/* Follow-up chip */
.followup-chip { display:inline-flex; align-items:center; gap:6px; background:#FFF7ED; border:1px solid #FED7AA; border-radius:8px; padding:5px 10px; font-size:12px; color:#92400E; font-weight:600; margin-top:10px; }
/* Select hint */
.sel-hint { text-align:center; padding:32px 20px; color:#8896B3; font-size:13px; background:#FAFBFF; border-radius:12px; margin-top:16px; border:1.5px dashed #CBD5E1; }
.sel-hint-icon { font-size:28px; margin-bottom:8px; }
/* Page titles */
.pg-title { font-size:22px; font-weight:700; color:#1A1F3C; margin-bottom:2px; }
.pg-sub   { font-size:13px; color:#8896B3; margin-bottom:20px; }
</style>"""

# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════
def parse_date(val):
    if not val: return None
    if isinstance(val, date): return val
    try: return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except: return None

def days_to(val):
    d = parse_date(val)
    return (d - date.today()).days if d else None

def is_umbrella(p):
    t = (p.get("policy_type") or "").lower()
    return "umbrella" in t or "excess" in t

def is_residential(p):
    t = (p.get("policy_type") or "").lower()
    return any(x in t for x in ["ho-3","ho-6","homeowner","condo","cea","earthquake","rental"])

def _dc(d):
    if d is None or d < 0: return "#EF4444"
    if d < 30: return "#EF4444"
    if d < 90: return "#D97706"
    return "#6B7A99"

def _dl(d):
    if d is None: return "—"
    if d < 0: return f"Expired {abs(d)}d ago"
    return f"{d}d left"

def _days_btn_label(d):
    """Label for the days selection button with emoji color indicator."""
    if d is None: return "—"
    if d < 0:  return "🔴 EXPIRED"
    if d < 30: return f"🔴 {d}d"
    if d < 90: return f"🟡 {d}d"
    return f"{d}d"

# ══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════
_ALERT_LEVELS = ["— None —","🔴 Urgent","🟡 Follow Up","🔵 Info","✅ Resolved"]
_ALERT_CSS    = {"🔴 Urgent":"alert-red","🟡 Follow Up":"alert-amber","🔵 Info":"alert-blue","✅ Resolved":"alert-green"}
_ALERT_ICONS  = {"🔴 Urgent":"🔴","🟡 Follow Up":"🟡","🔵 Info":"🔵","✅ Resolved":"✅"}
_POL_TAGS     = ["Renewal Pending","Inspection Required","Payment Due","Quote to Bind","Under Review","In Progress","Complete","Priority"]
_PROP_TAGS    = ["Missing Units","Missing Sq Ft","Lender Update Needed","Under Review","Complete","Priority"]

def _tag_html(tags):
    if not tags: return ""
    colors = {"Urgent":"urgent","Priority":"urgent","Inspection Required":"amber",
               "Payment Due":"amber","Renewal Pending":"amber","Quote to Bind":"purple",
               "Under Review":"purple","In Progress":"purple","Complete":"green",
               "Missing Units":"urgent","Missing Sq Ft":"amber"}
    chips = "".join(f'<span class="tag {colors.get(t,"gray")}">{t}</span>' for t in tags)
    return f'<div class="tag-row">{chips}</div>'

def _pol_classify(p):
    if is_umbrella(p): return "Umbrella"
    if is_residential(p): return "Residential"
    t = (p.get("policy_type") or "").lower()
    if "auto" in t: return "Auto"
    return "Commercial"

def _pol_badge(p):
    """Return (icon_emoji, badge_css_class) for a policy row."""
    alert = p.get("alert") or ""
    insp  = (p.get("inspection") or "").lower()
    if "required" in insp or ("Urgent" in alert):
        return "⚠", "badge-warn"
    s = p.get("status") or "Active"
    if s == "Expired": return "✕", "badge-exp"
    if s == "Quote":   return "◷", "badge-quote"
    tc = _pol_classify(p)
    if tc == "Residential": return "🏠", "badge-res"
    if tc == "Umbrella":    return "☂", "badge-umb"
    if tc == "Auto":        return "🚗", "badge-auto"
    return "🏢", "badge-comm"

# ══════════════════════════════════════════════════════════════════════
# FILTER PANEL helper  (reusable sidebar widget for pages)
# ══════════════════════════════════════════════════════════════════════
def _filter_section(title):
    st.markdown(f'<div class="fpanel-sec">{title}</div>', unsafe_allow_html=True)

def _filter_btn(label, key, active):
    return st.button(label, key=key, use_container_width=True,
                     type="primary" if active else "secondary")

# ══════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════
def page_dashboard(data):
    policies   = data.get("policies",   [])
    auto       = data.get("auto_policies", [])
    properties = data.get("properties", [])
    name       = data.get("portfolio_name","Portfolio")

    col_t, col_s = st.columns([1.4, 2])
    with col_t:
        st.markdown(f"""
        <div style="font-size:22px;font-weight:700;color:#1A1F3C;">📊 Dashboard</div>
        <div style="font-size:13px;color:#8896B3;">{name} · {date.today().strftime('%B %d, %Y')}</div>
        """, unsafe_allow_html=True)
    with col_s:
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        query = st.text_input("s", placeholder="🔍  Search by policy #, carrier, address, Prop ID…",
                              label_visibility="collapsed", key="gsearch")

    if query and query.strip():
        q = query.lower().strip()
        results = []
        for prop in properties:
            fields = " ".join(str(v) for v in [prop.get("prop_id",""),prop.get("nickname",""),
                prop.get("address",""),prop.get("city",""),prop.get("owner","")]).lower()
            if q in fields:
                results.append(("🏠 Property","background:#EEF2FF;color:#4338CA",
                    prop.get("nickname") or prop.get("address","—"),
                    f"{prop.get('prop_id','')} · {prop.get('address','')} · {prop.get('units','?')} units"))
        seen_p = set()
        for pol in policies:
            pno = pol.get("policy_number","")
            if pno in seen_p: continue
            seen_p.add(pno)
            fields = " ".join(str(v) for v in [pno,pol.get("carrier",""),
                pol.get("policy_type",""),pol.get("prop_id",""),pol.get("status","")]).lower()
            if q in fields:
                exp = parse_date(pol.get("expiration_date"))
                results.append(("📋 Policy","background:#F0FDF4;color:#166534",
                    f"{pno} — {pol.get('carrier','—')}",
                    f"{pol.get('policy_type','—')} · Expires {exp.strftime('%b %d, %Y') if exp else '—'} · ${pol.get('premium',0):,.0f} · {pol.get('status','—')}"))
        for a in auto:
            fields = " ".join(str(v) for v in [a.get("policy_number",""),a.get("carrier",""),
                a.get("insured",""),a.get("vehicles","")]).lower()
            if q in fields:
                exp = parse_date(a.get("expiration_date"))
                results.append(("🚗 Auto","background:#FFF7ED;color:#9A3412",
                    f"{a.get('policy_number','—')} — {a.get('carrier','—')}",
                    f"Auto · {a.get('insured','—')} · Expires {exp.strftime('%b %d, %Y') if exp else '—'} · ${a.get('premium',0):,.0f}"))
        if not results:
            st.info(f"No results for \"{query}\"")
        else:
            st.markdown(f"<div style='font-size:13px;color:#8896B3;margin-bottom:8px;'><b style='color:#1A1F3C;'>{len(results)}</b> result{'s' if len(results)!=1 else ''} for <b style='color:#4F6EF7;'>\"{query}\"</b></div>", unsafe_allow_html=True)
            for badge, bstyle, title, sub in results:
                st.markdown(f"""<div style="background:#fff;border:1px solid #E4EAF8;border-radius:10px;padding:12px 16px;margin:5px 0;">
                  <span style="font-size:11px;font-weight:600;padding:2px 10px;border-radius:20px;{bstyle}">{badge}</span>
                  <div style="font-size:14px;font-weight:600;color:#1A1F3C;margin-top:5px;">{title}</div>
                  <div style="font-size:12px;color:#6B7A99;margin-top:2px;">{sub}</div>
                </div>""", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#E4EAF8;margin:16px 0'>", unsafe_allow_html=True)

    if not policies and not properties:
        st.info("No data yet. Go to **Upload / Add** to add your first policy.")
        return

    seen = set(); comm=res=umb=quote=0; comm_cnt=res_cnt=quote_cnt=0
    for p in policies:
        pno=p.get("policy_number",""); prem=p.get("premium") or 0
        if pno in seen: continue
        seen.add(pno)
        if p.get("status","Active")=="Quote": quote+=prem; quote_cnt+=1
        elif is_umbrella(p): umb+=prem
        elif is_residential(p): res+=prem; res_cnt+=1
        else: comm+=prem; comm_cnt+=1
    auto_total = sum((a.get("premium") or 0) for a in auto)
    total_bound = comm+umb+res+auto_total

    c1,c2,c3,c4 = st.columns(4)
    for col,color,icon,label,value,sub in [
        (c1,"blue","🏢","Commercial",f"${comm+umb:,.0f}",f"{comm_cnt} policies · {len(properties)} props"),
        (c2,"green","🏡","Residential",f"${res:,.0f}",f"{res_cnt} policies"),
        (c3,"orange","🚗","Auto",f"${auto_total:,.0f}",f"{len(auto)} policies"),
        (c4,"purple","📄","Quote / Pending",f"${quote:,.0f}",f"{quote_cnt} quotes"),
    ]:
        col.markdown(f"""<div class="kpi-card {color}">
          <span class="kpi-icon">{icon}</span>
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{value}</div>
          <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    today = date.today()
    all_pols = list({p["policy_number"]:p for p in policies}.values()) + auto
    col_tl, col_pie = st.columns([2.2,1])
    with col_tl:
        st.markdown('<div class="section-hdr">Renewal Timeline — next 18 months</div>', unsafe_allow_html=True)
        tl = []
        for p in all_pols:
            exp=parse_date(p.get("expiration_date"))
            if not exp: continue
            days=(exp-today).days
            if days<-30 or days>548: continue
            color="#EF4444" if days<0 else "#F59E0B" if days<60 else "#4F6EF7" if days<180 else "#10B981"
            tl.append({"Policy":p.get("policy_number","—"),"Expires":exp.strftime("%b %d, %Y"),
                       "Days":days,"Premium":p.get("premium") or 0,"_c":color})
        if tl:
            df=pd.DataFrame(tl).sort_values("Days"); fig=go.Figure()
            for _,row in df.iterrows():
                fig.add_trace(go.Bar(x=[row["Days"]],y=[row["Policy"]],orientation="h",
                    marker_color=row["_c"],marker_line_width=0,
                    text=row["Expires"],textposition="outside",textfont=dict(size=10),
                    hovertemplate=f"<b>{row['Policy']}</b><br>Expires: {row['Expires']}<br>Premium: ${row['Premium']:,.0f}<extra></extra>",
                    showlegend=False))
            fig.update_layout(xaxis_title="Days from today",
                margin=dict(l=10,r=90,t=10,b=30),height=max(220,len(df)*34),
                plot_bgcolor="#FAFBFF",paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(gridcolor="#EEF2FF",zerolinecolor="#CBD5E1"),
                yaxis=dict(autorange="reversed"),
                font=dict(family="Arial,sans-serif",size=11,color="#1A1F3C"))
            fig.add_vline(x=0,line_color="#CBD5E1",line_dash="dot")
            fig.add_vline(x=90,line_color="#F59E0B",line_dash="dash",
                annotation_text="90d",annotation_font_size=10,annotation_position="top right")
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        else:
            st.markdown('<div class="flag-green">✅ No renewals in next 18 months.</div>', unsafe_allow_html=True)
    with col_pie:
        st.markdown('<div class="section-hdr">Premium Mix</div>', unsafe_allow_html=True)
        slices=[(l,v,c) for l,v,c in [("Commercial",comm+umb,"#4F6EF7"),
            ("Residential",res,"#10B981"),("Auto",auto_total,"#F59E0B"),("Quote",quote,"#8B5CF6")] if v>0]
        if slices:
            labels,values,colors=zip(*slices)
            fig2=go.Figure(go.Pie(labels=labels,values=values,hole=0.58,
                marker_colors=list(colors),textinfo="label+percent",
                textfont=dict(size=11),hovertemplate="%{label}: $%{value:,.0f}<extra></extra>"))
            fig2.update_layout(
                annotations=[dict(text=f"<b>${total_bound:,.0f}</b>",x=0.5,y=0.5,
                    font_size=13,font_color="#1A1F3C",showarrow=False)],
                showlegend=True,legend=dict(orientation="h",x=0,y=-0.15,font_size=10),
                margin=dict(l=0,r=0,t=10,b=20),height=290,paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2,use_container_width=True,config={"displayModeBar":False})

    expiring=sorted([p for p in all_pols if 0<=(days_to(p.get("expiration_date")) or 999)<90],
        key=lambda p: days_to(p.get("expiration_date")) or 999)
    st.markdown('<div class="section-hdr">⚠️ Expiring Within 90 Days</div>', unsafe_allow_html=True)
    if expiring:
        rows=[]
        for p in expiring:
            d=days_to(p.get("expiration_date")); dt=parse_date(p.get("expiration_date"))
            rows.append({" ":"🔴" if d<30 else "🟡","Policy #":p.get("policy_number","—"),
                "Carrier":p.get("carrier","—"),"Type":(p.get("policy_type") or "—")[:32],
                "Expires":dt.strftime("%m/%d/%Y") if dt else "—",
                "Days Left":d,"Premium":f"${p.get('premium',0):,.0f}"})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True,
            column_config={"Days Left":st.column_config.NumberColumn(format="%d days")})
    else:
        st.markdown('<div class="flag-green">✅ No policies expiring within 90 days.</div>', unsafe_allow_html=True)

    flags=[]
    for p in policies:
        if "required" in (p.get("inspection") or "").lower():
            flags.append(("red",f"Inspection required — {p.get('policy_number')} ({p.get('carrier','')})"))
        if (p.get("status") or "")=="Quote":
            flags.append(("amber",f"Unbound quote — {p.get('policy_number')} · ${p.get('premium',0):,.0f}"))
    for prop in properties:
        if not prop.get("units") or prop.get("units") in (0,None,"Not Found"):
            flags.append(("amber",f"Unit count missing — {prop.get('nickname') or prop.get('address','?')}"))
    st.markdown('<div class="section-hdr">🚩 Action Items</div>', unsafe_allow_html=True)
    if flags:
        for sev,msg in flags[:12]:
            css="flag-red" if sev=="red" else "flag-amber"
            ico="🔴" if sev=="red" else "🟡"
            st.markdown(f'<div class="{css}">{ico} {msg}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="flag-green">✅ No outstanding action items.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SHARED: Render one policy/auto row (4-column layout)
# ══════════════════════════════════════════════════════════════════════
def _render_row(i, icon, badge_cls, title, subtitle, premium, d, sel_idx, btn_key):
    """Render a single list row. Returns True if this row was clicked."""
    is_sel = (sel_idx == i)
    sel_bg  = "#EEF2FF" if is_sel else "transparent"
    sel_bdr = "border-left:3px solid #4F6EF7;padding-left:8px;" if is_sel else "border-left:3px solid transparent;padding-left:8px;"

    c0, c1, c2, c3 = st.columns([0.45, 4.5, 1.6, 1.3])
    with c0:
        st.markdown(f'<div class="pol-badge {badge_cls}">{icon}</div>', unsafe_allow_html=True)
    with c1:
        st.markdown(f"""
        <div style="min-height:44px;padding:4px 0;{sel_bdr}background:{sel_bg};border-radius:0 8px 8px 0;">
          <div style="font-size:14px;font-weight:700;color:#1A1F3C;line-height:1.25;padding:0 6px;">{title}</div>
          <div style="font-size:11px;color:#8896B3;padding:2px 6px 4px;">{subtitle}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div style="text-align:right;padding:4px 0;min-height:44px;display:flex;
                    align-items:center;justify-content:flex-end;background:{sel_bg};">
          <span style="font-size:14px;font-weight:700;color:#1A1F3C;">${premium:,.0f}</span>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        clicked = st.button(_days_btn_label(d), key=btn_key, use_container_width=True)
    # Divider
    st.markdown('<div style="height:1px;background:#F0F4FF;margin:0 0 2px;"></div>', unsafe_allow_html=True)
    return clicked


# ══════════════════════════════════════════════════════════════════════
# POLICIES PAGE
# ══════════════════════════════════════════════════════════════════════
def page_policies(data, save_fn):
    policies = data.get("policies", [])
    st.markdown(_DET_CSS, unsafe_allow_html=True)

    # ── deduplicate: one row per policy_number ──
    seen = {}
    for p in policies:
        pno = p.get("policy_number", "")
        if pno not in seen:
            seen[pno] = p
    unique_pols = list(seen.values())

    # ── page header ──
    col_t, col_s = st.columns([1.8, 3])
    with col_t:
        n_active = sum(1 for p in unique_pols if (p.get("status") or "Active") == "Active")
        st.markdown(f"""
        <div class="pg-title">📋 Policies</div>
        <div class="pg-sub">{n_active} active · {len(unique_pols)} total policies</div>
        """, unsafe_allow_html=True)
    with col_s:
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
        srch = st.text_input("q", placeholder="🔍  Search carrier, policy #, property...",
                             key="pol_srch", label_visibility="collapsed")

    if not unique_pols:
        st.info("No policies yet. Go to Upload / Add to add one.")
        return

    # ── compute counts for filters ──
    status_counts = {}
    for p in unique_pols:
        s = p.get("status") or "Active"
        status_counts[s] = status_counts.get(s, 0) + 1

    n30 = sum(1 for p in unique_pols if (d := days_to(p.get("expiration_date"))) is not None and 0 <= d < 30)
    n90 = sum(1 for p in unique_pols if (d := days_to(p.get("expiration_date"))) is not None and 0 <= d < 90)

    type_counts = {}
    for p in unique_pols:
        tc = _pol_classify(p)
        type_counts[tc] = type_counts.get(tc, 0) + 1

    # ── filter state ──
    fs = st.session_state.get("pf_s", "All")
    fu = st.session_state.get("pf_u", "All")
    ft = st.session_state.get("pf_t", "All")
    total = len(unique_pols)

    col_f, col_l = st.columns([1, 3.2])

    # ── FILTER PANEL ──
    with col_f:
        with st.container(border=True):
            st.markdown('<div class="fpanel-hdr">FILTER BY</div>', unsafe_allow_html=True)

            _filter_section("STATUS")
            for val, emoji in [("All","⚪"),("Active","🟢"),("Quote","🟣"),("Expired","🔴")]:
                cnt = status_counts.get(val, total) if val != "All" else total
                if _filter_btn(f"{emoji}  {val}  ({cnt})", f"pfs_{val}", fs == val):
                    st.session_state["pf_s"] = val; st.rerun()

            _filter_section("URGENCY")
            for val, emoji, cnt in [("All","⚪",total),("Expires <30d","🔴",n30),("Expires <90d","🟡",n90)]:
                if _filter_btn(f"{emoji}  {val}  ({cnt})", f"pfu_{val}", fu == val):
                    st.session_state["pf_u"] = val; st.rerun()

            _filter_section("TYPE")
            for val, emoji in [("All","⚪"),("Commercial","🔵"),("Residential","🟢"),("Auto","🟠"),("Umbrella","🟣")]:
                cnt = type_counts.get(val, total) if val != "All" else total
                if cnt == 0 and val != "All": continue
                if _filter_btn(f"{emoji}  {val}  ({cnt})", f"pft_{val}", ft == val):
                    st.session_state["pf_t"] = val; st.rerun()

            st.markdown("---")
            active_prem = sum((p.get("premium") or 0) for p in unique_pols if (p.get("status") or "Active") == "Active")
            st.metric("Active Premium", f"${active_prem:,.0f}")
            if n30:
                st.markdown(f'<div style="background:#FEF2F2;border-radius:8px;padding:7px 10px;font-size:12px;color:#991B1B;margin-top:8px;">🔴 {n30} expiring in &lt;30 days</div>', unsafe_allow_html=True)

    # ── apply filters ──
    q = (srch or "").lower().strip()
    filtered = []
    for p in unique_pols:
        s  = p.get("status") or "Active"
        if fs != "All" and s != fs: continue
        d  = days_to(p.get("expiration_date"))
        if fu == "Expires <30d" and (d is None or not (0 <= d < 30)): continue
        if fu == "Expires <90d" and (d is None or not (0 <= d < 90)): continue
        tc = _pol_classify(p)
        if ft != "All" and tc != ft: continue
        if q:
            hay = " ".join(str(v) for v in [p.get("carrier",""),p.get("policy_number",""),
                p.get("prop_id",""),p.get("policy_type","")]).lower()
            if q not in hay: continue
        filtered.append(p)

    # ── LIST ──
    with col_l:
        n_active_f = sum(1 for p in filtered if (p.get("status") or "Active") == "Active")
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="font-size:15px;font-weight:700;color:#1A1F3C;">{n_active_f} active policies</span>
          <span style="font-size:12px;color:#8896B3;">{len(filtered)} shown</span>
        </div>
        """, unsafe_allow_html=True)

        if not filtered:
            st.warning("No policies match the current filters.")
        else:
            sel_idx = st.session_state.get("sel_pol_idx")
            for i, pol in enumerate(filtered):
                icon, badge_cls = _pol_badge(pol)
                carrier  = pol.get("carrier", "—")
                pno      = pol.get("policy_number", "—")
                prop     = pol.get("prop_id") or "ALL"
                ptype    = (pol.get("policy_type") or "—")[:28]
                prem     = pol.get("premium") or 0
                d        = days_to(pol.get("expiration_date"))
                subtitle = f"{pno} · {prop} · {ptype}"

                if _render_row(i, icon, badge_cls, carrier, subtitle, prem, d, sel_idx, f"ps_{i}"):
                    new_idx = None if sel_idx == i else i
                    st.session_state["sel_pol_idx"] = new_idx
                    st.session_state.pop("editing_pol", None)
                    st.rerun()

    # ── DETAIL PANEL ──
    sel_idx = st.session_state.get("sel_pol_idx")
    if sel_idx is not None and filtered and sel_idx < len(filtered):
        p   = filtered[sel_idx]
        d   = days_to(p.get("expiration_date"))
        exp = parse_date(p.get("expiration_date"))
        eff = parse_date(p.get("effective_date"))
        s   = p.get("status","Active")
        pill = {"Active":"pill-active","Quote":"pill-quote","Expired":"pill-expired"}.get(s,"pill-active")
        bldg = p.get("building_limit")
        prem = p.get("premium") or 0
        pno  = p.get("policy_number","")
        insp = p.get("inspection") or ""
        notes     = p.get("notes","") or ""
        alert_lvl = p.get("alert","") or ""
        alert_msg = p.get("alert_msg","") or ""
        tags      = p.get("tags") or []
        followup  = p.get("follow_up_date","")

        alert_html = ""
        if "required" in insp.lower():
            alert_html = f'<div class="alert-banner alert-amber"><span class="alert-icon">⚠️</span><div class="alert-text"><strong>Inspection Required</strong>{insp}</div></div>'
        elif alert_lvl and alert_lvl != "— None —":
            css = _ALERT_CSS.get(alert_lvl,"alert-amber")
            ico = _ALERT_ICONS.get(alert_lvl,"⚠️")
            alert_html = f'<div class="alert-banner {css}"><span class="alert-icon">{ico}</span><div class="alert-text"><strong>{alert_lvl}</strong>{alert_msg}</div></div>'

        followup_html = ""
        if followup:
            fd = parse_date(followup)
            d_left = (fd - date.today()).days if fd else None
            color = "#92400E" if d_left is not None and d_left < 7 else "#374151"
            followup_html = f'<div class="followup-chip" style="color:{color}">📅 Follow-up: {fd.strftime("%b %d, %Y") if fd else followup}{f" · {d_left}d" if d_left is not None else ""}</div>'

        exp_disp = exp.strftime("%b %d, %Y") if exp else "—"
        exp_color = _dc(d)
        if d is not None:
            exp_disp += f" · <span style='color:{exp_color};font-weight:700'>{_dl(d)}</span>"

        st.markdown(f"""
        <div class="det-card">
          <div class="det-hdr">
            <div>
              <div class="det-title">{p.get("carrier","—")}</div>
              <div class="det-meta">{pno} &nbsp;·&nbsp; Prop: {p.get("prop_id","MULTI") or "MULTI"} &nbsp;·&nbsp; {p.get("agency","") or "No agency listed"}</div>
            </div>
            <span class="status-pill {pill}">{s}</span>
          </div>
          <div class="det-grid">
            <div class="det-field"><div class="dk">Policy Type</div><div class="dv">{p.get("policy_type","—")}</div></div>
            <div class="det-field"><div class="dk">Effective</div><div class="dv">{eff.strftime("%b %d, %Y") if eff else "—"}</div></div>
            <div class="det-field"><div class="dk">Expires</div><div class="dv">{exp_disp}</div></div>
            <div class="det-field"><div class="dk">Premium</div><div class="dv">${prem:,.0f}</div></div>
            <div class="det-field"><div class="dk">Building Limit</div><div class="dv">{f"${bldg:,.0f}" if bldg else "—"}</div></div>
            <div class="det-field"><div class="dk">AOP Deductible</div><div class="dv">{p.get("ded_aop","—") or "—"}</div></div>
            <div class="det-field"><div class="dk">Water Ded</div><div class="dv">{p.get("ded_water","—") or "—"}</div></div>
            <div class="det-field"><div class="dk">Liability</div><div class="dv">{p.get("liability","—") or "—"}</div></div>
            <div class="det-field"><div class="dk">Biz Income</div><div class="dv">{p.get("business_income","—") or "—"}</div></div>
            <div class="det-field"><div class="dk">Habitability</div><div class="dv">{p.get("habitability","—") or "—"}</div></div>
          </div>
          {_tag_html(tags)}
          {alert_html}
          {followup_html}
          {f'<div class="notes-box"><div class="notes-lbl">📝 Notes</div>{notes}</div>' if notes else ''}
        </div>
        """, unsafe_allow_html=True)

        ca, cb = st.columns([1,4])
        if ca.button("✏️ Edit Policy", key=f"edit_pol_{pno}", type="secondary"):
            st.session_state["editing_pol"] = pno

        if st.session_state.get("editing_pol") == pno:
            st.markdown("---")
            POL_TYPES = ["Commercial Package – Apartment","Apartment Owners","Apartment Owners Premier",
                         "HO-3 Homeowners","Rental Condo – Unitowners","CEA Earthquake",
                         "Commercial Liability Umbrella","Other"]
            with st.form(f"pol_edit_{pno}"):
                st.markdown("##### ✏️ Edit Policy")
                c1,c2 = st.columns(2)
                e_pid    = c1.text_input("Prop ID", value=p.get("prop_id","") or "")
                e_carrier= c2.text_input("Carrier *", value=p.get("carrier",""))
                c1,c2 = st.columns(2)
                e_agency = c1.text_input("Agency", value=p.get("agency","") or "")
                cur_type = p.get("policy_type","Other")
                e_type   = c2.selectbox("Policy Type", POL_TYPES,
                               index=POL_TYPES.index(cur_type) if cur_type in POL_TYPES else len(POL_TYPES)-1)
                c1,c2 = st.columns(2)
                e_status = c1.selectbox("Status", ["Active","Quote","Expired"],
                               index=["Active","Quote","Expired"].index(s) if s in ["Active","Quote","Expired"] else 0)
                e_prem   = c2.number_input("Premium ($)", min_value=0.0, step=100.0, format="%.2f", value=float(prem))
                c1,c2 = st.columns(2)
                e_eff    = c1.date_input("Effective", value=eff or date.today(), key="pol_eff")
                e_exp    = c2.date_input("Expiration", value=exp or date.today().replace(year=date.today().year+1), key="pol_exp")
                c1,c2 = st.columns(2)
                e_bldg   = c1.number_input("Building Limit ($)", min_value=0, step=10000, value=int(bldg) if bldg else 0)
                e_liab   = c2.text_input("Liability", value=p.get("liability","") or "")
                c1,c2,c3 = st.columns(3)
                e_aop    = c1.text_input("AOP Ded", value=p.get("ded_aop","") or "")
                e_water  = c2.text_input("Water Ded", value=p.get("ded_water","") or "")
                e_sewer  = c3.text_input("Sewer Ded", value=p.get("ded_sewer","") or "")
                c1,c2 = st.columns(2)
                e_bi     = c1.text_input("Biz Income", value=p.get("business_income","") or "")
                e_hab    = c2.text_input("Habitability", value=p.get("habitability","") or "")
                e_insp   = st.text_input("Inspection", value=p.get("inspection","") or "")
                st.markdown("##### 📋 Tracking")
                c1,c2 = st.columns(2)
                e_alert  = c1.selectbox("Alert Level", _ALERT_LEVELS,
                               index=_ALERT_LEVELS.index(alert_lvl) if alert_lvl in _ALERT_LEVELS else 0)
                raw_fu   = p.get("follow_up_date","")
                e_fu     = c2.date_input("Follow-up Date", value=parse_date(raw_fu) if raw_fu else date.today(), key="pol_fu")
                e_amsg   = st.text_input("Alert Message", value=alert_msg, placeholder="What needs attention?")
                e_tags   = st.multiselect("Tags", _POL_TAGS, default=[t for t in tags if t in _POL_TAGS], key="pol_tags_edit")
                e_notes  = st.text_area("Notes / Endorsements", value=notes, height=90)
                c1,c2 = st.columns([1,3])
                saved   = c1.form_submit_button("💾 Save", type="primary", use_container_width=True)
                cancel  = c2.form_submit_button("✕ Cancel", use_container_width=True)

            if saved:
                updated = {**p,
                    "prop_id":e_pid.strip() or None, "carrier":e_carrier.strip(),
                    "agency":e_agency.strip(), "policy_type":e_type, "status":e_status,
                    "premium":float(e_prem), "effective_date":str(e_eff), "expiration_date":str(e_exp),
                    "building_limit":int(e_bldg) if e_bldg else None, "liability":e_liab.strip(),
                    "ded_aop":e_aop.strip() or "Not Found", "ded_water":e_water.strip() or "Not Found",
                    "ded_sewer":e_sewer.strip() or "Not Covered", "business_income":e_bi.strip(),
                    "habitability":e_hab.strip() or "N/A", "inspection":e_insp.strip() or "Not Found",
                    "alert":e_alert if e_alert != "— None —" else "",
                    "alert_msg":e_amsg.strip(), "follow_up_date":str(e_fu),
                    "tags":e_tags, "notes":e_notes.strip()}
                pol_list = data.get("policies",[])
                idx = next((i for i,x in enumerate(pol_list) if x.get("policy_number")==pno), None)
                if idx is not None: pol_list[idx] = updated
                data["policies"] = pol_list; save_fn(data)
                st.session_state.pop("editing_pol", None)
                st.success(f"✅ Policy {pno} updated."); st.rerun()
            if cancel:
                st.session_state.pop("editing_pol", None); st.rerun()
    elif filtered:
        st.markdown("""
        <div class="sel-hint">
          <div class="sel-hint-icon">↑</div>
          Click any policy row (days indicator) to see full details, edit, and add notes or alerts
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# PROPERTIES PAGE
# ══════════════════════════════════════════════════════════════════════
def page_properties(data, save_fn):
    props = data.get("properties", [])
    st.markdown(_DET_CSS, unsafe_allow_html=True)

    col_t, col_s = st.columns([1.8, 3])
    with col_t:
        st.markdown(f"""
        <div class="pg-title">🏠 Properties</div>
        <div class="pg-sub">{len(props)} properties in portfolio</div>
        """, unsafe_allow_html=True)
    with col_s:
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
        srch = st.text_input("q", placeholder="🔍  Search address, ID, nickname...",
                             key="prop_srch", label_visibility="collapsed")

    if not props:
        st.info("No properties yet. Go to Upload / Add to add one.")
        return

    # ── counts for filters ──
    all_cities  = sorted(set(p.get("city","")  for p in props if p.get("city")))
    all_types   = sorted(set(p.get("type","")  for p in props if p.get("type")))
    n_missing   = sum(1 for p in props if not p.get("units") or p.get("units") in (0,None,"Not Found"))
    n_alerts    = sum(1 for p in props if p.get("alert") and p.get("alert") != "— None —")

    city_counts = {}
    for p in props:
        c = p.get("city","")
        if c: city_counts[c] = city_counts.get(c, 0) + 1

    type_counts_p = {}
    for p in props:
        t = p.get("type","")
        if t: type_counts_p[t] = type_counts_p.get(t, 0) + 1

    # ── filter state ──
    pfc = st.session_state.get("ppc", "All")
    pft = st.session_state.get("ppt", "All")
    pfm = st.session_state.get("ppm", False)

    col_f, col_l = st.columns([1, 3.2])

    # ── FILTER PANEL ──
    with col_f:
        with st.container(border=True):
            st.markdown('<div class="fpanel-hdr">FILTER BY</div>', unsafe_allow_html=True)

            _filter_section("CITY")
            for val in ["All"] + all_cities:
                cnt = city_counts.get(val, len(props)) if val != "All" else len(props)
                dot = "⚪" if val == "All" else "🔵"
                if _filter_btn(f"{dot}  {val}  ({cnt})", f"ppc_{val}", pfc == val):
                    st.session_state["ppc"] = val; st.rerun()

            _filter_section("TYPE")
            for val in ["All"] + all_types:
                cnt = type_counts_p.get(val, len(props)) if val != "All" else len(props)
                dot = "⚪" if val == "All" else "🟢"
                if _filter_btn(f"{dot}  {val[:22]}  ({cnt})", f"ppt_{val}", pft == val):
                    st.session_state["ppt"] = val; st.rerun()

            _filter_section("FLAGS")
            if _filter_btn(f"⚠️  Missing units/sqft  ({n_missing})", "ppm_miss", pfm == "missing"):
                st.session_state["ppm"] = "missing" if pfm != "missing" else False; st.rerun()
            if _filter_btn(f"🔴  Has alert  ({n_alerts})", "ppm_alert", pfm == "alert"):
                st.session_state["ppm"] = "alert" if pfm != "alert" else False; st.rerun()

            st.markdown("---")
            confirmed_units = sum((p.get("units") or 0) for p in props
                                  if isinstance(p.get("units"),int) and p.get("units") not in (0,None))
            st.metric("Total Properties", len(props))
            st.metric("Units Confirmed", confirmed_units)
            if n_missing:
                st.markdown(f'<div style="background:#FFFBEB;border-radius:8px;padding:7px 10px;font-size:12px;color:#92400E;margin-top:8px;">⚠️ {n_missing} missing unit count</div>', unsafe_allow_html=True)

    # ── apply filters ──
    q = (srch or "").lower().strip()
    filtered = []
    for p in props:
        if pfc != "All" and p.get("city","") != pfc: continue
        if pft != "All" and p.get("type","") != pft: continue
        if pfm == "missing":
            u = p.get("units"); s = p.get("sqft")
            if u and u not in (0,"Not Found") and isinstance(s,int) and s: continue
        if pfm == "alert":
            if not p.get("alert") or p.get("alert") == "— None —": continue
        if q:
            hay = " ".join(str(v) for v in [p.get("address",""),p.get("nickname",""),
                p.get("prop_id",""),p.get("city",""),p.get("owner","")]).lower()
            if q not in hay: continue
        filtered.append(p)

    # ── LIST ──
    with col_l:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="font-size:15px;font-weight:700;color:#1A1F3C;">{len(filtered)} properties</span>
          <span style="font-size:12px;color:#8896B3;">{len(props)} total</span>
        </div>
        """, unsafe_allow_html=True)

        if not filtered:
            st.warning("No properties match the current filters.")
        else:
            sel_idx = st.session_state.get("sel_prop_idx")
            for i, p in enumerate(filtered):
                u_ok = p.get("units") and p.get("units") not in (0,"Not Found")
                has_alert = p.get("alert") and p.get("alert") != "— None —"
                if not u_ok:
                    icon, badge_cls = "⚠", "badge-warn"
                elif has_alert:
                    icon, badge_cls = "🔴", "badge-warn"
                else:
                    icon, badge_cls = "🏠", "badge-prop"

                title    = p.get("nickname") or p.get("address","—")
                subtitle = f"{p.get('prop_id','')} · {p.get('address','')} · {p.get('city','')} · {p.get('units','?')} units"
                premium  = 0  # properties don't have a premium field directly
                # Use sqft as the "number" in the premium column
                sqft     = p.get("sqft") or 0

                # Custom row rendering for properties (uses sqft not premium)
                is_sel = (sel_idx == i)
                sel_bg  = "#EEF2FF" if is_sel else "transparent"
                sel_bdr = "border-left:3px solid #4F6EF7;padding-left:8px;" if is_sel else "border-left:3px solid transparent;padding-left:8px;"

                c0, c1, c2, c3 = st.columns([0.45, 4.5, 1.6, 1.3])
                with c0:
                    st.markdown(f'<div class="pol-badge {badge_cls}">{icon}</div>', unsafe_allow_html=True)
                with c1:
                    st.markdown(f"""
                    <div style="min-height:44px;padding:4px 0;{sel_bdr}background:{sel_bg};border-radius:0 8px 8px 0;">
                      <div style="font-size:14px;font-weight:700;color:#1A1F3C;line-height:1.25;padding:0 6px;">{title}</div>
                      <div style="font-size:11px;color:#8896B3;padding:2px 6px 4px;">{subtitle}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c2:
                    units_disp = f"{p.get('units')} units" if u_ok else "⚠️ No units"
                    units_color = "#EF4444" if not u_ok else "#1A1F3C"
                    st.markdown(f"""
                    <div style="text-align:right;padding:4px 0;min-height:44px;display:flex;
                                align-items:center;justify-content:flex-end;background:{sel_bg};">
                      <span style="font-size:13px;font-weight:700;color:{units_color};">{units_disp}</span>
                    </div>
                    """, unsafe_allow_html=True)
                with c3:
                    yr = p.get("year_built","")
                    lbl = f"Est. {yr}" if yr else "No yr"
                    clicked = st.button(lbl, key=f"prs_{i}", use_container_width=True)
                st.markdown('<div style="height:1px;background:#F0F4FF;margin:0 0 2px;"></div>', unsafe_allow_html=True)

                if clicked:
                    st.session_state["sel_prop_idx"] = None if sel_idx == i else i
                    st.session_state.pop("editing_prop", None)
                    st.rerun()

    # ── DETAIL PANEL ──
    sel_idx = st.session_state.get("sel_prop_idx")
    if sel_idx is not None and filtered and sel_idx < len(filtered):
        p = filtered[sel_idx]
        units = p.get("units"); sqft = p.get("sqft")
        u_ok  = units and units not in (0,"Not Found")
        s_ok  = isinstance(sqft,int) and sqft
        notes     = p.get("notes","") or ""
        alert_lvl = p.get("alert","") or ""
        alert_msg = p.get("alert_msg","") or ""
        tags      = p.get("tags") or []
        followup  = p.get("follow_up_date","")
        pid       = p.get("prop_id","")

        alert_html = ""
        if alert_lvl and alert_lvl != "— None —":
            css = _ALERT_CSS.get(alert_lvl,"alert-amber")
            ico = _ALERT_ICONS.get(alert_lvl,"⚠️")
            alert_html = f'<div class="alert-banner {css}"><span class="alert-icon">{ico}</span><div class="alert-text"><strong>{alert_lvl}</strong>{alert_msg}</div></div>'

        followup_html = ""
        if followup:
            fd = parse_date(followup)
            d_left = (fd - date.today()).days if fd else None
            color = "#92400E" if d_left is not None and d_left < 7 else "#374151"
            followup_html = f'<div class="followup-chip" style="color:{color}">📅 Follow-up: {fd.strftime("%b %d, %Y") if fd else followup}{f" · {d_left}d" if d_left is not None else ""}</div>'

        st.markdown(f"""
        <div class="det-card">
          <div class="det-hdr">
            <div>
              <div class="det-title">{p.get("nickname") or p.get("address","—")}</div>
              <div class="det-meta">{pid} &nbsp;·&nbsp; {p.get("address","")} &nbsp;·&nbsp; {p.get("city","")} {p.get("state","")} {p.get("zip","")}</div>
            </div>
            <span class="status-pill pill-prop">{p.get("type","Property")}</span>
          </div>
          <div class="det-grid">
            <div class="det-field"><div class="dk">Units</div><div class="dv" style="color:{'#EF4444' if not u_ok else '#1A1F3C'}">{units if u_ok else '⚠️ Missing'}</div></div>
            <div class="det-field"><div class="dk">Sq Ft</div><div class="dv" style="color:{'#EF4444' if not s_ok else '#1A1F3C'}">{f"{sqft:,}" if s_ok else "⚠️ Missing"}</div></div>
            <div class="det-field"><div class="dk">Year Built</div><div class="dv">{p.get("year_built","—")}</div></div>
            <div class="det-field"><div class="dk">Owner</div><div class="dv">{p.get("owner","—")}</div></div>
            <div class="det-field"><div class="dk">Mortgagee</div><div class="dv">{p.get("mortgagee","—") or "—"}</div></div>
            <div class="det-field"><div class="dk">Agent</div><div class="dv">{p.get("agent","—") or "—"}</div></div>
          </div>
          {_tag_html(tags)}
          {alert_html}
          {followup_html}
          {f'<div class="notes-box"><div class="notes-lbl">📝 Notes</div>{notes}</div>' if notes else ''}
        </div>
        """, unsafe_allow_html=True)

        ca, cb = st.columns([1,4])
        if ca.button("✏️ Edit Property", key=f"edit_prop_{pid}", type="secondary"):
            st.session_state["editing_prop"] = pid

        if st.session_state.get("editing_prop") == pid:
            st.markdown("---")
            with st.form(f"prop_edit_{pid}"):
                st.markdown("##### ✏️ Edit Property")
                c1,c2 = st.columns(2)
                e_nick  = c1.text_input("Nickname", value=p.get("nickname",""))
                e_addr  = c2.text_input("Address", value=p.get("address",""))
                c1,c2,c3 = st.columns(3)
                e_city  = c1.text_input("City", value=p.get("city",""))
                e_state = c2.text_input("State", value=p.get("state","CA"), max_chars=2)
                e_zip   = c3.text_input("ZIP", value=p.get("zip",""))
                c1,c2,c3 = st.columns(3)
                e_type  = c1.selectbox("Type",
                    ["Multi-Unit Apartment","Single Family – Primary","Condo – Rental","Commercial","Other"],
                    index=["Multi-Unit Apartment","Single Family – Primary","Condo – Rental","Commercial","Other"].index(p.get("type","Multi-Unit Apartment"))
                    if p.get("type") in ["Multi-Unit Apartment","Single Family – Primary","Condo – Rental","Commercial","Other"] else 0)
                e_units = c2.number_input("Units", min_value=0, step=1,
                    value=int(p.get("units") or 0) if isinstance(p.get("units"),int) else 0)
                e_sqft  = c3.number_input("Sq Ft", min_value=0, step=100,
                    value=int(p.get("sqft") or 0) if isinstance(p.get("sqft"),int) else 0)
                c1,c2 = st.columns(2)
                e_owner = c1.text_input("Owner", value=p.get("owner",""))
                e_mort  = c2.text_input("Mortgagee", value=p.get("mortgagee","") or "")
                e_agent = st.text_input("Agent", value=p.get("agent","") or "")
                st.markdown("##### 📋 Tracking")
                c1,c2 = st.columns(2)
                e_alert = c1.selectbox("Alert Level", _ALERT_LEVELS,
                    index=_ALERT_LEVELS.index(p.get("alert","— None —")) if p.get("alert") in _ALERT_LEVELS else 0)
                raw_fu  = p.get("follow_up_date","")
                e_fu    = c2.date_input("Follow-up Date", value=parse_date(raw_fu) if raw_fu else date.today(), key="prop_fu")
                e_amsg  = st.text_input("Alert Message", value=p.get("alert_msg","") or "", placeholder="What needs attention?")
                e_tags  = st.multiselect("Tags", _PROP_TAGS, default=[t for t in (p.get("tags") or []) if t in _PROP_TAGS], key="prop_tags")
                e_notes = st.text_area("Notes", value=p.get("notes","") or "", height=90)
                c1,c2 = st.columns([1,3])
                saved   = c1.form_submit_button("💾 Save", type="primary", use_container_width=True)
                cancel  = c2.form_submit_button("✕ Cancel", use_container_width=True)

            if saved:
                updated = {**p, "nickname":e_nick.strip(), "address":e_addr.strip(),
                    "city":e_city.strip(), "state":e_state.strip().upper(), "zip":e_zip.strip(),
                    "type":e_type, "units":int(e_units) if e_units else None,
                    "sqft":int(e_sqft) if e_sqft else None, "owner":e_owner.strip(),
                    "mortgagee":e_mort.strip() or "Not stated", "agent":e_agent.strip(),
                    "alert":e_alert if e_alert != "— None —" else "",
                    "alert_msg":e_amsg.strip(), "follow_up_date":str(e_fu),
                    "tags":e_tags, "notes":e_notes.strip()}
                props_list = data.get("properties",[])
                idx = next((i for i,x in enumerate(props_list) if x.get("prop_id")==pid), None)
                if idx is not None: props_list[idx] = updated
                data["properties"] = props_list; save_fn(data)
                st.session_state.pop("editing_prop", None)
                st.success(f"✅ Property {pid} updated."); st.rerun()
            if cancel:
                st.session_state.pop("editing_prop", None); st.rerun()
    elif filtered:
        st.markdown("""
        <div class="sel-hint">
          <div class="sel-hint-icon">↑</div>
          Click any property row to see full details, edit, and add notes or alerts
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# AUTO PAGE
# ══════════════════════════════════════════════════════════════════════
def page_auto(data, save_fn):
    auto = data.get("auto_policies", [])
    st.markdown(_DET_CSS, unsafe_allow_html=True)

    col_t, col_s = st.columns([1.8, 3])
    with col_t:
        st.markdown(f"""
        <div class="pg-title">🚗 Auto Insurance</div>
        <div class="pg-sub">{len(auto)} auto {'policy' if len(auto)==1 else 'policies'}</div>
        """, unsafe_allow_html=True)
    with col_s:
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
        srch = st.text_input("q", placeholder="🔍  Search insured, carrier, policy #...",
                             key="auto_srch", label_visibility="collapsed")

    if not auto:
        st.info("No auto policies yet. Go to Upload / Add to add one.")
        return

    # ── counts ──
    all_states = sorted(set(a.get("state","") for a in auto if a.get("state")))
    n30_a = sum(1 for a in auto if (d := days_to(a.get("expiration_date"))) is not None and 0 <= d < 30)
    n90_a = sum(1 for a in auto if (d := days_to(a.get("expiration_date"))) is not None and 0 <= d < 90)
    state_counts = {}
    for a in auto:
        s = a.get("state","")
        if s: state_counts[s] = state_counts.get(s, 0) + 1

    # ── filter state ──
    afa = st.session_state.get("af_state", "All")
    afu = st.session_state.get("af_urg",   "All")
    total_a = len(auto)

    col_f, col_l = st.columns([1, 3.2])

    # ── FILTER PANEL ──
    with col_f:
        with st.container(border=True):
            st.markdown('<div class="fpanel-hdr">FILTER BY</div>', unsafe_allow_html=True)

            _filter_section("STATE")
            for val in ["All"] + all_states:
                cnt = state_counts.get(val, total_a) if val != "All" else total_a
                dot = "⚪" if val == "All" else "🔵"
                if _filter_btn(f"{dot}  {val}  ({cnt})", f"afs_{val}", afa == val):
                    st.session_state["af_state"] = val; st.rerun()

            _filter_section("URGENCY")
            for val, emoji, cnt in [("All","⚪",total_a),("Expires <30d","🔴",n30_a),("Expires <90d","🟡",n90_a)]:
                if _filter_btn(f"{emoji}  {val}  ({cnt})", f"afu_{val}", afu == val):
                    st.session_state["af_urg"] = val; st.rerun()

            st.markdown("---")
            total_prem = sum((a.get("premium") or 0) for a in auto)
            st.metric("Auto Policies", len(auto))
            st.metric("Total Premium", f"${total_prem:,.0f}")
            if n30_a:
                st.markdown(f'<div style="background:#FEF2F2;border-radius:8px;padding:7px 10px;font-size:12px;color:#991B1B;margin-top:8px;">🔴 {n30_a} expiring &lt;30 days</div>', unsafe_allow_html=True)

    # ── apply filters ──
    q = (srch or "").lower().strip()
    filtered = []
    for a in auto:
        if afa != "All" and a.get("state","") != afa: continue
        d = days_to(a.get("expiration_date"))
        if afu == "Expires <30d" and (d is None or not (0 <= d < 30)): continue
        if afu == "Expires <90d" and (d is None or not (0 <= d < 90)): continue
        if q:
            hay = " ".join(str(v) for v in [a.get("insured",""),a.get("policy_number",""),
                a.get("carrier",""),a.get("state","")]).lower()
            if q not in hay: continue
        filtered.append(a)

    # ── LIST ──
    with col_l:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <span style="font-size:15px;font-weight:700;color:#1A1F3C;">{len(filtered)} auto policies</span>
          <span style="font-size:12px;color:#8896B3;">{total_a} total</span>
        </div>
        """, unsafe_allow_html=True)

        if not filtered:
            st.warning("No policies match the current filters.")
        else:
            sel_idx = st.session_state.get("sel_auto_idx")
            for i, a in enumerate(filtered):
                d       = days_to(a.get("expiration_date"))
                carrier = a.get("carrier","—")
                pno     = a.get("policy_number","—")
                insured = a.get("insured","—")
                state   = a.get("state","—")
                prem    = a.get("premium") or 0
                subtitle = f"{pno} · {insured} · {state}"

                if _render_row(i, "🚗", "badge-auto", carrier, subtitle, prem, d, sel_idx, f"as_{i}"):
                    new_idx = None if sel_idx == i else i
                    st.session_state["sel_auto_idx"] = new_idx
                    st.session_state.pop("editing_auto", None)
                    st.rerun()

    # ── DETAIL PANEL ──
    sel_idx = st.session_state.get("sel_auto_idx")
    if sel_idx is not None and filtered and sel_idx < len(filtered):
        a   = filtered[sel_idx]
        d   = days_to(a.get("expiration_date"))
        exp = parse_date(a.get("expiration_date"))
        eff = parse_date(a.get("effective_date"))
        pno = a.get("policy_number","")
        notes     = a.get("notes","") or ""
        alert_lvl = a.get("alert","") or ""
        alert_msg = a.get("alert_msg","") or ""
        tags      = a.get("tags") or []
        followup  = a.get("follow_up_date","")

        alert_html = ""
        if alert_lvl and alert_lvl != "— None —":
            css = _ALERT_CSS.get(alert_lvl,"alert-amber")
            ico = _ALERT_ICONS.get(alert_lvl,"⚠️")
            alert_html = f'<div class="alert-banner {css}"><span class="alert-icon">{ico}</span><div class="alert-text"><strong>{alert_lvl}</strong>{alert_msg}</div></div>'

        followup_html = ""
        if followup:
            fd = parse_date(followup)
            d_left = (fd - date.today()).days if fd else None
            color = "#92400E" if d_left is not None and d_left < 7 else "#374151"
            followup_html = f'<div class="followup-chip" style="color:{color}">📅 Follow-up: {fd.strftime("%b %d, %Y") if fd else followup}{f" · {d_left}d" if d_left is not None else ""}</div>'

        exp_disp = exp.strftime("%b %d, %Y") if exp else "—"
        exp_color = _dc(d)
        if d is not None:
            exp_disp += f" · <span style='color:{exp_color};font-weight:700'>{_dl(d)}</span>"

        st.markdown(f"""
        <div class="det-card">
          <div class="det-hdr">
            <div>
              <div class="det-title">{a.get("insured","—")}</div>
              <div class="det-meta">{pno} &nbsp;·&nbsp; {a.get("carrier","—")} &nbsp;·&nbsp; State: {a.get("state","—")}</div>
            </div>
            <span class="status-pill pill-auto">Auto</span>
          </div>
          <div class="det-grid">
            <div class="det-field"><div class="dk">Carrier</div><div class="dv">{a.get("carrier","—")}</div></div>
            <div class="det-field"><div class="dk">Agency</div><div class="dv">{a.get("agency","—") or "—"}</div></div>
            <div class="det-field"><div class="dk">Effective</div><div class="dv">{eff.strftime("%b %d, %Y") if eff else "—"}</div></div>
            <div class="det-field"><div class="dk">Expires</div><div class="dv">{exp_disp}</div></div>
            <div class="det-field"><div class="dk">Premium</div><div class="dv">${(a.get("premium") or 0):,.0f}</div></div>
            <div class="det-field"><div class="dk">BI / PD</div><div class="dv">{a.get("bipd","—") or "—"}</div></div>
            <div class="det-field"><div class="dk">Comp Ded</div><div class="dv">{a.get("comp_ded","—") or "—"}</div></div>
            <div class="det-field"><div class="dk">Coll Ded</div><div class="dv">{a.get("coll_ded","—") or "—"}</div></div>
            <div class="det-field"><div class="dk">UM / UIM</div><div class="dv">{a.get("um_uim","—") or "—"}</div></div>
            <div class="det-field"><div class="dk">PIP / Med Pay</div><div class="dv">{a.get("pip_medpay","—") or "—"}</div></div>
          </div>
          <div class="det-field" style="margin-bottom:10px">
            <div class="dk">Vehicles</div>
            <div class="dv" style="font-size:12px;font-weight:400;line-height:1.5">{a.get("vehicles","—") or "—"}</div>
          </div>
          {_tag_html(tags)}
          {alert_html}
          {followup_html}
          {f'<div class="notes-box"><div class="notes-lbl">📝 Notes</div>{notes}</div>' if notes else ''}
        </div>
        """, unsafe_allow_html=True)

        ca, cb = st.columns([1,4])
        if ca.button("✏️ Edit Auto Policy", key=f"edit_auto_{pno}", type="secondary"):
            st.session_state["editing_auto"] = pno

        if st.session_state.get("editing_auto") == pno:
            st.markdown("---")
            with st.form(f"auto_edit_{pno}"):
                st.markdown("##### ✏️ Edit Auto Policy")
                c1,c2 = st.columns(2)
                e_ins    = c1.text_input("Named Insured", value=a.get("insured",""))
                e_carrier= c2.text_input("Carrier *", value=a.get("carrier",""))
                c1,c2,c3 = st.columns(3)
                e_pno    = c1.text_input("Policy Number *", value=pno)
                e_state  = c2.text_input("State", value=a.get("state","CA"), max_chars=2)
                e_agency = c3.text_input("Agency", value=a.get("agency","") or "")
                c1,c2 = st.columns(2)
                e_eff    = c1.date_input("Effective", value=eff or date.today(), key="ae_eff")
                e_exp    = c2.date_input("Expiration", value=exp or date.today().replace(year=date.today().year+1), key="ae_exp")
                e_prem   = st.number_input("Premium ($)", min_value=0.0, step=50.0, format="%.2f",
                               value=float(a.get("premium") or 0))
                e_veh    = st.text_area("Vehicle(s)", value=a.get("vehicles","") or "", height=60)
                c1,c2 = st.columns(2)
                e_bipd   = c1.text_input("BI / PD Limits", value=a.get("bipd","") or "")
                e_um     = c2.text_input("UM / UIM", value=a.get("um_uim","") or "")
                c1,c2 = st.columns(2)
                e_comp   = c1.text_input("Comp Deductible", value=a.get("comp_ded","") or "")
                e_coll   = c2.text_input("Collision Deductible", value=a.get("coll_ded","") or "")
                e_pip    = st.text_input("PIP / Med Pay", value=a.get("pip_medpay","") or "")
                st.markdown("##### 📋 Tracking")
                c1,c2 = st.columns(2)
                e_alert  = c1.selectbox("Alert Level", _ALERT_LEVELS,
                               index=_ALERT_LEVELS.index(alert_lvl) if alert_lvl in _ALERT_LEVELS else 0)
                raw_fu   = a.get("follow_up_date","")
                e_fu     = c2.date_input("Follow-up Date", value=parse_date(raw_fu) if raw_fu else date.today(), key="ae_fu")
                e_amsg   = st.text_input("Alert Message", value=alert_msg, placeholder="What needs attention?")
                e_tags   = st.multiselect("Tags", _POL_TAGS, default=[t for t in tags if t in _POL_TAGS], key="auto_tags_edit")
                e_notes  = st.text_area("Notes", value=notes, height=80)
                c1,c2 = st.columns([1,3])
                saved   = c1.form_submit_button("💾 Save", type="primary", use_container_width=True)
                cancel  = c2.form_submit_button("✕ Cancel", use_container_width=True)

            if saved:
                updated = {**a,
                    "insured":e_ins.strip(), "carrier":e_carrier.strip(), "policy_number":e_pno.strip(),
                    "state":e_state.strip().upper(), "agency":e_agency.strip(),
                    "effective_date":str(e_eff), "expiration_date":str(e_exp), "premium":float(e_prem),
                    "vehicles":e_veh.strip(), "bipd":e_bipd.strip(), "um_uim":e_um.strip(),
                    "comp_ded":e_comp.strip(), "coll_ded":e_coll.strip(), "pip_medpay":e_pip.strip(),
                    "alert":e_alert if e_alert != "— None —" else "",
                    "alert_msg":e_amsg.strip(), "follow_up_date":str(e_fu),
                    "tags":e_tags, "notes":e_notes.strip()}
                auto_list = data.get("auto_policies",[])
                idx = next((i for i,x in enumerate(auto_list) if x.get("policy_number")==pno), None)
                if idx is not None: auto_list[idx] = updated
                data["auto_policies"] = auto_list; save_fn(data)
                st.session_state.pop("editing_auto", None)
                st.success(f"✅ Auto policy {pno} updated."); st.rerun()
            if cancel:
                st.session_state.pop("editing_auto", None); st.rerun()
    elif filtered:
        st.markdown("""
        <div class="sel-hint">
          <div class="sel-hint-icon">↑</div>
          Click any auto policy row to see full details, edit, and add notes or alerts
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# UPLOAD / ADD
# ══════════════════════════════════════════════════════════════════════
def page_upload(data, client_id, save_fn):
    st.markdown('<div style="font-size:22px;font-weight:700;color:#1A1F3C;margin-bottom:16px;">📤 Add / Update Policy</div>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["🏢 Property Policy", "🚗 Auto Policy", "🏠 Property Record"])

    with tab1:
        col_pdf, col_form = st.columns([1,1])
        with col_pdf:
            st.markdown("**Policy PDF (reference)**")
            uploaded = st.file_uploader("Upload PDF", type=["pdf"], key="pol_pdf")
            pdf_link = ""
            if uploaded:
                pdf_bytes = uploaded.read()
                safe = uploaded.name.replace(" ","_")
                pdf_link = save_pdf(client_id, safe, pdf_bytes)
                b64 = base64.b64encode(pdf_bytes).decode()
                st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="680px" style="border:1px solid #E4EAF8;border-radius:8px;"></iframe>', unsafe_allow_html=True)
            else:
                st.info("Upload a PDF to view it here while filling the form.")
        with col_form:
            st.markdown("**Policy Details**")
            with st.form("policy_form"):
                st.markdown("##### 🔑 Identity")
                c1,c2 = st.columns(2)
                prop_id  = c1.text_input("Prop ID (P001…)")
                pol_no   = c2.text_input("Policy Number *")
                carrier  = st.text_input("Insurance Carrier *")
                agency   = st.text_input("Agency / Broker")
                pol_type = st.selectbox("Policy Type",["Commercial Package – Apartment","Apartment Owners","Apartment Owners Premier","HO-3 Homeowners","Rental Condo – Unitowners","CEA Earthquake","Commercial Liability Umbrella","Other"])
                status   = st.selectbox("Status",["Active","Quote","Expired"])
                st.markdown("##### 💰 Dates & Premium")
                c1,c2 = st.columns(2)
                eff_date = c1.date_input("Effective Date", value=date.today())
                exp_date = c2.date_input("Expiration Date", value=date.today().replace(year=date.today().year+1))
                premium  = st.number_input("Total Premium ($)", min_value=0.0, step=100.0, format="%.2f")
                st.markdown("##### 🏗️ Coverage")
                bldg     = st.number_input("Building Limit / Coverage A ($)", min_value=0, step=10000)
                bi       = st.text_input("Business Income / Loss of Rents")
                liab     = st.text_input("Liability / GL Aggregate")
                st.markdown("##### ⚠️ Deductibles")
                c1,c2,c3 = st.columns(3)
                ded_aop   = c1.text_input("AOP Deductible")
                ded_water = c2.text_input("Water Damage")
                ded_sewer = c3.text_input("Sewer/Drain Backup")
                st.markdown("##### 🔍 Special")
                c1,c2 = st.columns(2)
                hab  = c1.text_input("Habitability Sublimit")
                insp = c2.text_input("Inspection Requirement")
                notes = st.text_area("Notes / Endorsements", height=70)
                submitted = st.form_submit_button("💾 Save Policy", type="primary", use_container_width=True)
            if submitted:
                if not pol_no or not carrier:
                    st.error("Policy Number and Carrier are required.")
                else:
                    new_pol = {"prop_id":prop_id.strip() or None,"policy_number":pol_no.strip(),
                        "status":status,"carrier":carrier.strip(),"agency":agency.strip(),
                        "policy_type":pol_type,"effective_date":str(eff_date),
                        "expiration_date":str(exp_date),"premium":float(premium),
                        "building_limit":int(bldg) if bldg else None,"business_income":bi.strip(),
                        "liability":liab.strip(),"ded_aop":ded_aop.strip() or "Not Found",
                        "ded_water":ded_water.strip() or "Not Found","ded_sewer":ded_sewer.strip() or "Not Covered",
                        "habitability":hab.strip() or "N/A","inspection":insp.strip() or "Not Found",
                        "pdf_link":pdf_link,"notes":notes.strip()}
                    pols = data.get("policies",[])
                    idx  = next((i for i,p in enumerate(pols) if p.get("policy_number")==pol_no.strip()),None)
                    if idx is not None: pols[idx]=new_pol; st.success(f"✅ Policy {pol_no} updated.")
                    else: pols.append(new_pol); st.success(f"✅ Policy {pol_no} added.")
                    data["policies"]=pols; save_fn(data); st.balloons()

    with tab2:
        with st.form("auto_form"):
            c1,c2 = st.columns(2)
            a_group  = c1.text_input("Policy Group / Insured Entity")
            a_insured= c2.text_input("Named Insured(s)")
            c1,c2,c3 = st.columns(3)
            a_carrier= c1.text_input("Carrier")
            a_pno    = c2.text_input("Policy Number")
            a_state  = c3.text_input("State", max_chars=2, value="CA")
            a_agency = st.text_input("Agency")
            c1,c2 = st.columns(2)
            a_eff  = c1.date_input("Effective", value=date.today(), key="ae")
            a_exp  = c2.date_input("Expiration", value=date.today().replace(year=date.today().year+1), key="ax")
            a_prem = st.number_input("Total Premium ($)", min_value=0.0, step=50.0, format="%.2f", key="ap")
            a_veh  = st.text_area("Vehicle(s)", height=60)
            a_vins = st.text_area("VIN(s)", height=60)
            a_bipd = st.text_input("BI / PD Limits")
            c1,c2 = st.columns(2)
            a_comp = c1.text_input("Comp Deductible")
            a_coll = c2.text_input("Collision Deductible")
            a_um   = st.text_input("UM/UIM")
            a_pip  = st.text_input("PIP / Med Pay")
            a_notes= st.text_area("Notes", height=60, key="an")
            a_sub  = st.form_submit_button("💾 Save Auto Policy", type="primary", use_container_width=True)
        if a_sub:
            if not a_pno or not a_carrier:
                st.error("Policy Number and Carrier required.")
            else:
                new_auto={"group":a_group.strip(),"insured":a_insured.strip(),"state":a_state.strip().upper(),
                    "carrier":a_carrier.strip(),"agency":a_agency.strip(),"policy_number":a_pno.strip(),
                    "effective_date":str(a_eff),"expiration_date":str(a_exp),"premium":float(a_prem),
                    "vehicles":a_veh.strip(),"vins":a_vins.strip(),"bipd":a_bipd.strip(),
                    "comp_ded":a_comp.strip(),"coll_ded":a_coll.strip(),"um_uim":a_um.strip(),
                    "pip_medpay":a_pip.strip(),"notes":a_notes.strip()}
                autos=data.get("auto_policies",[])
                idx=next((i for i,a in enumerate(autos) if a.get("policy_number")==a_pno.strip()),None)
                if idx is not None: autos[idx]=new_auto; st.success(f"✅ Auto policy {a_pno} updated.")
                else: autos.append(new_auto); st.success(f"✅ Auto policy {a_pno} added.")
                data["auto_policies"]=autos; save_fn(data)

    with tab3:
        existing_ids=[p.get("prop_id","") for p in data.get("properties",[])]
        next_id=f"P{len(existing_ids)+1:03d}"
        with st.form("prop_form"):
            c1,c2 = st.columns(2)
            p_id   = c1.text_input("Prop ID", value=next_id)
            p_nick = c2.text_input("Nickname", placeholder="3632 Centinela")
            p_addr = st.text_input("Full Address *")
            c1,c2,c3 = st.columns([2,1,1])
            p_city  = c1.text_input("City")
            p_state = c2.text_input("State", value="CA", max_chars=2)
            p_zip   = c3.text_input("ZIP")
            c1,c2 = st.columns(2)
            p_type = c1.selectbox("Property Type",["Multi-Unit Apartment","Single Family – Primary","Condo – Rental","Commercial","Other"])
            p_yr   = c2.number_input("Year Built", min_value=1800, max_value=2030, value=1970, step=1)
            c1,c2 = st.columns(2)
            p_units = c1.number_input("Units", min_value=0, step=1, value=0)
            p_sqft  = c2.number_input("Sq Ft", min_value=0, step=100, value=0)
            p_owner = st.text_input("Owner / Insured Name")
            p_mort  = st.text_input("Mortgagee / Lender")
            p_agent = st.text_input("Primary Agent")
            p_notes = st.text_area("Notes", height=60, key="pn")
            p_sub   = st.form_submit_button("💾 Save Property", type="primary", use_container_width=True)
        if p_sub:
            if not p_addr:
                st.error("Address is required.")
            else:
                new_prop={"prop_id":p_id.strip(),"nickname":p_nick.strip(),"address":p_addr.strip(),
                    "city":p_city.strip(),"state":p_state.strip().upper(),"zip":p_zip.strip(),
                    "type":p_type,"year_built":int(p_yr),"units":int(p_units) if p_units else None,
                    "sqft":int(p_sqft) if p_sqft else None,"owner":p_owner.strip(),
                    "mortgagee":p_mort.strip() or "Not stated","agent":p_agent.strip(),"notes":p_notes.strip()}
                props=data.get("properties",[])
                idx=next((i for i,p in enumerate(props) if p.get("prop_id")==p_id.strip()),None)
                if idx is not None: props[idx]=new_prop; st.success(f"✅ Property {p_id} updated.")
                else: props.append(new_prop); st.success(f"✅ Property {p_id} added.")
                data["properties"]=props; save_fn(data)


# ══════════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════════
def page_export(data):
    st.markdown('<div style="font-size:22px;font-weight:700;color:#1A1F3C;margin-bottom:16px;">⬇️ Download Excel</div>', unsafe_allow_html=True)
    portfolio=data.get("portfolio_name","Portfolio")
    st.info(f"**{portfolio}** · {len(data.get('properties',[]))} properties · {len(data.get('policies',[]))} policy rows · {len(data.get('auto_policies',[]))} auto policies")
    version=st.number_input("Version number",min_value=1,max_value=99,value=1,step=1)
    safe=portfolio.replace(" ","_").replace("/","-")
    filename=f"{safe}_Master_Insurance_Schedule_v{version}.xlsx"
    if st.button("🔄 Generate Excel",type="primary",use_container_width=True):
        with st.spinner("Building workbook…"):
            try:
                script=_ROOT/"build_workbook.py"
                with tempfile.TemporaryDirectory() as tmp:
                    dp=Path(tmp)/"data.json"; op=Path(tmp)/filename
                    dp.write_text(json.dumps(data,default=str))
                    r=subprocess.run(["python3",str(script),str(dp),str(op)],
                        capture_output=True,text=True,timeout=60)
                    if r.returncode!=0:
                        st.error(f"Build error:\n{r.stderr}"); return
                    xlsx=op.read_bytes()
                st.success(f"✅ {filename} ready!")
                st.download_button(f"⬇️ Download {filename}",xlsx,filename,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,type="primary")
            except Exception as e:
                st.error(f"Error: {e}")
    st.markdown("---")
    st.markdown("**Export raw data as JSON (backup):**")
    st.download_button("⬇️ Export portfolio.json",json.dumps(data,indent=2,default=str),
        f"{safe}_portfolio_{date.today()}.json","application/json")


# ══════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════
def show_login():
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(160deg,#EEF2FF 0%,#EDE9FE 100%) !important; }
    .stTextInput label, .stSelectbox label {
      color: #4B5563 !important; font-size: 14px !important; font-weight: 500 !important; }
    </style>""", unsafe_allow_html=True)
    _,col,_ = st.columns([1.3,1,1.3])
    with col:
        st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background:white;border:1px solid #DDE3F8;border-radius:20px;
          padding:36px 32px 28px;text-align:center;margin-bottom:16px;">
          <div style="font-size:52px;line-height:1;">🛡️</div>
          <div style="font-size:24px;font-weight:700;color:#1A1F3C;margin-top:10px;">InsureTrack</div>
          <div style="font-size:13px;color:#8896B3;margin-top:4px;">Insurance Portfolio Management</div>
        </div>""", unsafe_allow_html=True)
        clients = load_clients()
        if not clients:
            st.error("No clients configured. Check clients.json."); return
        client_names = {v["name"]:k for k,v in clients.items()}
        selected = st.selectbox("Select Portfolio", sorted(client_names.keys()))
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        if st.button("Sign In →", use_container_width=True, type="primary"):
            cid = client_names[selected]
            if clients[cid]["password"] == password:
                st.session_state.logged_in   = True
                st.session_state.client_id   = cid
                st.session_state.client_name = selected
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.markdown("<div style='text-align:center;font-size:11px;color:#A0AECE;margin-top:12px;'>🔒 Secure · Multi-client</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════
def show_sidebar():
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:6px 4px 4px;">
          <div style="font-size:17px;font-weight:700;color:#FFFFFF;">🛡️ InsureTrack</div>
          <div style="font-size:12px;color:#6B7A99;margin-top:3px;">{st.session_state.client_name}</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("---")
        nav=[("📊","Dashboard","dashboard"),("🏠","Properties","properties"),
             ("📋","Policies","policies"),("🚗","Auto","auto"),
             ("📤","Upload / Add","upload"),("⬇️","Download Excel","export")]
        for icon,label,pid in nav:
            active=st.session_state.get("page")==pid
            if st.button(f"{icon}  {label}",use_container_width=True,
                         type="primary" if active else "secondary",key=f"nav_{pid}"):
                st.session_state.page=pid; st.rerun()
        st.markdown("---")
        if st.button("↩  Sign Out",use_container_width=True,key="signout"):
            for k in ["logged_in","client_id","client_name","page"]: st.session_state.pop(k,None)
            st.rerun()
        st.markdown("<div style='font-size:11px;color:#4A5580;text-align:center;margin-top:12px;'>v3.0</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    if not st.session_state.get("logged_in"):
        show_login(); return
    if "page" not in st.session_state:
        st.session_state.page = "dashboard"

    show_sidebar()
    data = load_portfolio(st.session_state.client_id)
    save = lambda d: save_portfolio(st.session_state.client_id, d)

    page = st.session_state.page
    if   page == "dashboard":  page_dashboard(data)
    elif page == "properties": page_properties(data, save)
    elif page == "policies":   page_policies(data, save)
    elif page == "auto":       page_auto(data, save)
    elif page == "upload":     page_upload(data, st.session_state.client_id, save)
    elif page == "export":     page_export(data)


main()
