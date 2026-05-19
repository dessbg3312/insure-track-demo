"""
InsureTrack — Single-file Insurance Portfolio Manager
No local imports. Works on Streamlit Cloud without configuration.
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
_ROOT        = Path(__file__).parent
_DATA_DIR    = _ROOT / "data"
_CLIENTS_FILE = _ROOT / "clients.json"

# ══════════════════════════════════════════════════════════════════════
# DATA LAYER  (local JSON or Supabase when env vars present)
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
                    "properties": r["properties"] or [],
                    "policies":   r["policies"]   or [],
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
        sb = _sb(); path = f"{client_id}/{filename}"
        try:
            sb.storage.from_("pdfs").upload(path, content_bytes, {"content-type":"application/pdf"})
        except Exception:
            try: sb.storage.from_("pdfs").update(path, content_bytes, {"content-type":"application/pdf"})
            except Exception: return ""
        return sb.storage.from_("pdfs").get_public_url(path)
    else:
        d = _DATA_DIR / client_id / "pdfs"; d.mkdir(parents=True, exist_ok=True)
        (d / filename).write_bytes(content_bytes)
        return str(d / filename)

# ══════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
.stApp { background: #F0F4FF !important; }
#MainMenu, footer, header { visibility: hidden; }

[data-testid="stSidebar"] { background: #1A1F3C !important; border-right: 1px solid #2D3561; }
[data-testid="stSidebar"],
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
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
[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover,
[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover p,
[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover span {
  background: #252C52 !important; color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[kind="primary"] p,
[data-testid="stSidebar"] .stButton > button[kind="primary"] span {
  background: #4F6EF7 !important; color: #FFFFFF !important;
}

.block-container { padding: 2rem 2.5rem !important; max-width: 1400px !important; }

.kpi-card { background:#fff; border:1px solid #E4EAF8; border-radius:14px;
  padding:18px 20px; position:relative; overflow:hidden; }
.kpi-card::before { content:""; position:absolute; top:0; left:0; right:0;
  height:4px; border-radius:14px 14px 0 0; }
.kpi-card.blue::before   { background:#4F6EF7; }
.kpi-card.green::before  { background:#10B981; }
.kpi-card.orange::before { background:#F59E0B; }
.kpi-card.purple::before { background:#8B5CF6; }
.kpi-icon  { font-size:20px; margin-bottom:6px; display:block; }
.kpi-label { font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:.07em; color:#8896B3; }
.kpi-value { font-size:24px; font-weight:700; color:#1A1F3C; margin-top:2px; }
.kpi-sub   { font-size:11px; color:#A0AECE; margin-top:3px; }

.section-hdr { font-size:11px; font-weight:700; color:#4F6EF7; letter-spacing:.08em;
  text-transform:uppercase; border-bottom:2px solid #E4EAF8;
  padding-bottom:6px; margin:24px 0 14px; }

.flag-amber { background:#FFFBEB; border-left:3px solid #F59E0B;
  padding:7px 14px; border-radius:0 8px 8px 0; margin:4px 0;
  font-size:13px; color:#78350F; }
.flag-red   { background:#FEF2F2; border-left:3px solid #EF4444;
  padding:7px 14px; border-radius:0 8px 8px 0; margin:4px 0;
  font-size:13px; color:#7F1D1D; }
.flag-green { background:#F0FDF4; border-left:3px solid #10B981;
  padding:7px 14px; border-radius:0 8px 8px 0; margin:4px 0;
  font-size:13px; color:#14532D; }
</style>
""", unsafe_allow_html=True)

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

# ══════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════
def page_dashboard(data):
    policies   = data.get("policies",[])
    auto       = data.get("auto_policies",[])
    properties = data.get("properties",[])
    name       = data.get("portfolio_name","Portfolio")

    # Header + search
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

    # Search results
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
                st.markdown(f"""<div style="background:#fff;border:1px solid #E4EAF8;border-radius:10px;
                  padding:12px 16px;margin:5px 0;">
                  <span style="font-size:11px;font-weight:600;padding:2px 10px;border-radius:20px;{bstyle}">{badge}</span>
                  <div style="font-size:14px;font-weight:600;color:#1A1F3C;margin-top:5px;">{title}</div>
                  <div style="font-size:12px;color:#6B7A99;margin-top:2px;">{sub}</div>
                </div>""", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#E4EAF8;margin:16px 0'>", unsafe_allow_html=True)

    if not policies and not properties:
        st.info("No data yet. Go to **Upload / Add** to add your first policy.")
        return

    # Premium buckets
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

    # KPI cards
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

    # Timeline + donut
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

    # Expiring soon
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

    # Action items
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
# PROPERTIES
# ══════════════════════════════════════════════════════════════════════
def page_properties(data):
    props = data.get("properties",[])
    st.markdown('<div style="font-size:22px;font-weight:700;color:#1A1F3C;margin-bottom:16px;">🏠 Properties</div>', unsafe_allow_html=True)
    if not props:
        st.info("No properties yet. Go to Upload / Add to add one.")
        return

    search = st.text_input("🔍 Search address or nickname", "")
    rows = []
    for p in props:
        if search and search.lower() not in (str(p.get("address",""))+str(p.get("nickname",""))).lower():
            continue
        rows.append({"ID":p.get("prop_id",""),"Nickname":p.get("nickname",""),
            "Address":p.get("address",""),"City":p.get("city",""),"Type":p.get("type",""),
            "Built":p.get("year_built",""),"Units":p.get("units","Not Found"),
            "Sq Ft":p.get("sqft","Not Found"),"Owner":p.get("owner",""),
            "Agent":p.get("agent",""),"Notes":(p.get("notes") or "")[:80]})

    if not rows:
        st.warning("No properties match your search.")
        return

    df = pd.DataFrame(rows)
    def flag_missing(val):
        if val in ("Not Found", None, 0): return "background-color:#fef9c3;color:#92400e"
        return ""
    styled = df.style.applymap(flag_missing, subset=["Units","Sq Ft"])
    st.dataframe(styled, use_container_width=True, hide_index=True, height=560)
    st.caption(f"{len(rows)} properties · Yellow = data needs verification")
    st.markdown("---")
    c1,c2,c3 = st.columns(3)
    total_units = sum((p.get("units") or 0) for p in props if isinstance(p.get("units"),int))
    total_sqft  = sum((p.get("sqft") or 0) for p in props if isinstance(p.get("sqft"),int))
    c1.metric("Total Properties", len(props))
    c2.metric("Total Units (confirmed)", total_units)
    c3.metric("Total Sq Ft (confirmed)", f"{total_sqft:,}")


# ══════════════════════════════════════════════════════════════════════
# POLICIES
# ══════════════════════════════════════════════════════════════════════
def page_policies(data):
    policies = data.get("policies",[])
    st.markdown('<div style="font-size:22px;font-weight:700;color:#1A1F3C;margin-bottom:16px;">📋 Policies</div>', unsafe_allow_html=True)
    if not policies:
        st.info("No policies yet. Upload a PDF to get started.")
        return

    col1,col2,col3 = st.columns([1,1,2])
    with col1:
        status_filter = st.multiselect("Status", ["Active","Quote","Expired"], default=["Active","Quote"])
    with col2:
        type_filter = st.selectbox("Type", ["All","Commercial","Residential","Umbrella"])
    with col3:
        search = st.text_input("Search policy # or carrier", "")

    rows=[]
    for p in policies:
        status=p.get("status","Active")
        if status_filter and status not in status_filter: continue
        ptype=(p.get("policy_type") or "").lower()
        if type_filter=="Commercial" and any(x in ptype for x in ["ho-","homeown","condo","cea"]): continue
        if type_filter=="Residential" and not any(x in ptype for x in ["ho-","homeown","condo","cea"]): continue
        if type_filter=="Umbrella" and "umbrella" not in ptype and "excess" not in ptype: continue
        if search and search.lower() not in (p.get("policy_number","")+p.get("carrier","")).lower(): continue
        exp=parse_date(p.get("expiration_date"))
        d = days_to(p.get("expiration_date"))
        rows.append({"Prop ID":p.get("prop_id","MULTI"),"Policy #":p.get("policy_number",""),
            "Status":status,"Carrier":p.get("carrier",""),"Type":p.get("policy_type",""),
            "Effective":parse_date(p.get("effective_date")).strftime("%m/%d/%Y") if parse_date(p.get("effective_date")) else "—",
            "Expires":exp.strftime("%m/%d/%Y") if exp else "—",
            "Days Left":max(0,d) if d is not None else "—",
            "Premium":p.get("premium"),"Bldg Limit":p.get("building_limit"),
            "AOP Ded":p.get("ded_aop",""),"Notes":(p.get("notes") or "")[:80]})

    if not rows:
        st.warning("No policies match your filters.")
        return

    df=pd.DataFrame(rows)
    def style_status(val):
        return {"Active":"background-color:#e2efda","Quote":"background-color:#fff9c4","Expired":"background-color:#fce4ec"}.get(val,"")
    def style_days(val):
        if isinstance(val,int):
            if val<30: return "color:#ef4444;font-weight:700"
            if val<90: return "color:#f59e0b;font-weight:600"
        return ""
    styled=(df.style.applymap(style_status,subset=["Status"]).applymap(style_days,subset=["Days Left"])
        .format({"Premium":lambda v:f"${v:,.0f}" if v else "—","Bldg Limit":lambda v:f"${v:,.0f}" if v else "—"}))
    st.dataframe(styled,use_container_width=True,hide_index=True,height=520)

    bound=[r for r in rows if r["Status"]=="Active"]
    if bound:
        seen=set(); unique=0
        for p in policies:
            pno=p.get("policy_number","")
            if pno not in seen and p.get("status","Active")=="Active":
                seen.add(pno); unique+=p.get("premium") or 0
        st.markdown(f"**{len(bound)} active rows** · Unique policy total: **${unique:,.2f}**")
        st.caption("Multi-property policies appear on multiple rows but premium is counted once.")


# ══════════════════════════════════════════════════════════════════════
# AUTO
# ══════════════════════════════════════════════════════════════════════
def page_auto(data):
    auto=data.get("auto_policies",[])
    st.markdown('<div style="font-size:22px;font-weight:700;color:#1A1F3C;margin-bottom:16px;">🚗 Auto Insurance</div>', unsafe_allow_html=True)
    if not auto:
        st.info("No auto policies yet.")
        return
    rows=[]
    for a in auto:
        exp=parse_date(a.get("expiration_date"))
        d=days_to(a.get("expiration_date"))
        rows.append({"Policy #":a.get("policy_number",""),"Insured":a.get("insured",""),
            "Carrier":a.get("carrier",""),"State":a.get("state",""),
            "Vehicles":a.get("vehicles",""),"Expires":exp.strftime("%m/%d/%Y") if exp else "—",
            "Days Left":max(0,d) if d is not None else "—","Premium":a.get("premium"),
            "BI/PD":a.get("bipd",""),"Notes":(a.get("notes") or "")[:80]})
    df=pd.DataFrame(rows)
    def sd(val):
        if isinstance(val,int):
            if val<30: return "color:#ef4444;font-weight:700"
            if val<90: return "color:#f59e0b;font-weight:600"
        return ""
    styled=df.style.applymap(sd,subset=["Days Left"]).format({"Premium":lambda v:f"${v:,.2f}" if v else "—"})
    st.dataframe(styled,use_container_width=True,hide_index=True)
    total=sum((a.get("premium") or 0) for a in auto)
    st.markdown(f"**{len(auto)} policies** · Total as issued: **${total:,.2f}**")


# ══════════════════════════════════════════════════════════════════════
# UPLOAD / ADD
# ══════════════════════════════════════════════════════════════════════
def page_upload(data, client_id, save_fn):
    st.markdown('<div style="font-size:22px;font-weight:700;color:#1A1F3C;margin-bottom:16px;">📤 Add / Update Policy</div>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["🏢 Property Policy", "🚗 Auto Policy", "🏠 Property Record"])

    # ── Tab 1: Property Policy ───────────────────────────────────────
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
                bi       = st.text_input("Business Income / Loss of Rents", placeholder="e.g. $180,000 (12 months ALS)")
                liab     = st.text_input("Liability / GL Aggregate", placeholder="e.g. $2,000,000 Agg")
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
                    idx = next((i for i,p in enumerate(pols) if p.get("policy_number")==pol_no.strip() and p.get("prop_id")==(prop_id.strip() or None)),None)
                    if idx is not None: pols[idx]=new_pol; st.success(f"✅ Policy {pol_no} updated.")
                    else: pols.append(new_pol); st.success(f"✅ Policy {pol_no} added.")
                    data["policies"]=pols; save_fn(data); st.balloons()

    # ── Tab 2: Auto Policy ───────────────────────────────────────────
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
            a_eff = c1.date_input("Effective", value=date.today(), key="ae")
            a_exp = c2.date_input("Expiration", value=date.today().replace(year=date.today().year+1), key="ax")
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

    # ── Tab 3: Property Record ───────────────────────────────────────
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
        st.markdown("<div style='font-size:11px;color:#4A5580;text-align:center;margin-top:12px;'>v2.0</div>", unsafe_allow_html=True)


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
    elif page == "properties": page_properties(data)
    elif page == "policies":   page_policies(data)
    elif page == "auto":       page_auto(data)
    elif page == "upload":     page_upload(data, st.session_state.client_id, save)
    elif page == "export":     page_export(data)


main()
