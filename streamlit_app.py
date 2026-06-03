import streamlit as st
import requests
import json
import base64
import time
import os
import random
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

SEVERITY_COLOR = {
    "low":      ("#d1fae5", "#065f46", "#10b981"),
    "medium":   ("#fef3c7", "#78350f", "#f59e0b"),
    "high":     ("#fee2e2", "#7f1d1d", "#ef4444"),
    "critical": ("#fce7f3", "#831843", "#ec4899"),
}
SEVERITY_LABEL  = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}
REPAIR_LABEL    = {"repair": "Repair", "replace": "Replace", "paint": "Paint", "align": "Align"}

PROPERTY_CATEGORIES = [
    ("My Stuff",                  "Items you own"),
    ("Stuff That I Borrow",       "Items belonging to others that you had"),
    ("Someone Else's Stuff",      "Third-party property you damaged"),
    ("My Landlord's Property",    "Fixtures or fittings in a rented property"),
    ("Other — I'll Explain Later","Something that doesn't fit above"),
]

CLAIM_QUESTIONS = [
    ("bot", "Hi! I'm here to help you file your insurance claim quickly. First — **did anyone get hurt?**"),
]


# ── API helpers ───────────────────────────────────────────────────────────────

def query_agent(user_input: str, user_id: str) -> str:
    try:
        r = requests.post(f"{BACKEND_URL}/query",
                          json={"user_input": user_input, "user_id": user_id},
                          timeout=60)
        r.raise_for_status()
        return r.json()["response"]
    except requests.exceptions.ConnectionError:
        return "Error: Backend unavailable. Make sure backend_app.py is running on port 8000."
    except requests.exceptions.Timeout:
        return "Error: Request timed out."
    except Exception as e:
        return f"Error: {e}"


def analyze_damage(image_bytes: bytes, media_type: str) -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    try:
        r = requests.post(f"{BACKEND_URL}/analyze-damage",
                          json={"image_b64": b64, "media_type": media_type},
                          timeout=90)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Backend unavailable"}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out (90 s)"}
    except Exception as e:
        return {"error": str(e)}


# ── PDF report ────────────────────────────────────────────────────────────────

def build_damage_pdf(result: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    BLACK  = colors.HexColor("#111111")
    GRAY   = colors.HexColor("#6b7280")
    LGRAY  = colors.HexColor("#f3f4f6")
    BORDER = colors.HexColor("#e5e7eb")
    GREEN  = colors.HexColor("#10b981")
    RED    = colors.HexColor("#ef4444")
    YELLOW = colors.HexColor("#f59e0b")
    PINK   = colors.HexColor("#ec4899")
    SEV_DOT = {"low": GREEN, "medium": YELLOW, "high": RED, "critical": PINK}

    def s(name, **kw):
        defaults = dict(fontName="Helvetica", fontSize=9, textColor=BLACK, leading=14)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    base   = s("base")
    bold11 = s("bold11", fontName="Helvetica-Bold", fontSize=11, leading=16, spaceBefore=14, spaceAfter=6)
    logo   = s("logo",   fontName="Helvetica-Bold", fontSize=18, leading=22)
    title  = s("title",  fontName="Helvetica-Bold", fontSize=22, leading=28, spaceAfter=2)
    meta   = s("meta",   textColor=GRAY)
    small  = s("small",  fontSize=8, textColor=GRAY, leading=12)
    mc     = s("mc",     fontName="Helvetica-Bold", fontSize=16, leading=20, alignment=TA_CENTER)
    ml     = s("ml",     fontSize=8, textColor=GRAY, leading=11, alignment=TA_CENTER)
    footer = s("footer", fontSize=8, textColor=GRAY, leading=11, alignment=TA_CENTER)
    wt     = s("wt",     fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#7f1d1d"), leading=13)
    wb     = s("wb",     fontSize=9, textColor=colors.HexColor("#7f1d1d"), leading=13)
    rt     = s("rt",     fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#166534"), leading=13)
    rb     = s("rb",     fontSize=9, textColor=colors.HexColor("#14532d"), leading=13)

    W = A4[0] - 40*mm
    now = datetime.now().strftime("%B %d, %Y  %H:%M")
    story = []

    hdr = Table([[Paragraph("InsurAI", logo),
                  Paragraph(f"<font color='#6b7280'>Vehicle Damage Report</font><br/>"
                             f"<font color='#9ca3af' size='8'>Generated: {now}</font>", base)]],
                colWidths=[W*.45, W*.55])
    hdr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(1,0),(1,0),"RIGHT"),
                              ("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story += [hdr, HRFlowable(width="100%", thickness=1.5, color=BLACK, spaceAfter=12)]
    story.append(Paragraph("Damage Assessment Report", title))
    desc = result.get("vehicle_description", "")
    if desc:
        story.append(Paragraph(desc, meta))
    story.append(Spacer(1, 10))

    sev   = result.get("overall_severity", "—")
    c_min = result.get("total_cost_min", 0)
    c_max = result.get("total_cost_max", 0)
    rtime = result.get("repair_time_days", "—")
    drive = "Yes" if result.get("can_drive", True) else "No"
    conf  = f"{int(result.get('confidence', 0)*100)}%"

    def mc_cell(v, l): return [Paragraph(v, mc), Paragraph(l, ml)]
    sev_c = colors.HexColor(SEVERITY_COLOR.get(sev, ("#f3f4f6","#374151","#9ca3af"))[2])
    metrics = Table([[mc_cell(f"${c_min:,}–${c_max:,}", "Repair Cost"),
                      mc_cell(SEVERITY_LABEL.get(sev, sev), "Severity"),
                      mc_cell(rtime, "Repair Time"),
                      mc_cell(drive, "Can Drive"),
                      mc_cell(conf, "AI Confidence")]],
                    colWidths=[W/5]*5)
    metrics.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.5,BORDER),
        ("BACKGROUND",(0,0),(-1,-1),LGRAY),("TOPPADDING",(0,0),(-1,-1),10),
        ("BOTTOMPADDING",(0,0),(-1,-1),10),("TEXTCOLOR",(1,0),(1,0),sev_c),
        ("TEXTCOLOR",(3,0),(3,0),GREEN if drive=="Yes" else RED)]))
    story += [metrics, Spacer(1,14)]

    parts = result.get("damaged_parts", [])
    if parts:
        story += [HRFlowable(width="100%",thickness=.5,color=BORDER),
                  Paragraph("Damaged Components", bold11)]
        rows = [[Paragraph(f"<b>{h}</b>", base) for h in
                 ["Component","Severity","Description","Work Type","Cost Range"]]]
        for p in parts:
            ps = p.get("severity","low")
            dot = SEV_DOT.get(ps, GRAY)
            rows.append([
                Paragraph(p.get("part",""), base),
                Paragraph(f"<font color='{dot.hexval()}'>●</font>  {SEVERITY_LABEL.get(ps,ps)}", base),
                Paragraph(p.get("description",""), small),
                Paragraph(REPAIR_LABEL.get(p.get("repair_type",""), p.get("repair_type","")), base),
                Paragraph(f"${p.get('cost_min',0):,}–${p.get('cost_max',0):,}", base),
            ])
        tbl = Table(rows, colWidths=[W*.17,W*.12,W*.36,W*.13,W*.22], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),BLACK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),8),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,LGRAY]),
            ("GRID",(0,0),(-1,-1),.4,BORDER),("TOPPADDING",(0,0),(-1,-1),6),
            ("BOTTOMPADDING",(0,0),(-1,-1),6),("LEFTPADDING",(0,0),(-1,-1),8),
            ("VALIGN",(0,0),(-1,-1),"TOP")]))
        story += [tbl, Spacer(1,12)]

    for items, title_txt, ts, bs, bg, bc in [
        (result.get("safety_concerns",[]),  "Safety Concerns",   wt, wb,
         colors.HexColor("#fef2f2"), colors.HexColor("#fecaca")),
        (result.get("recommendations",[]),  "Recommendations",   rt, rb,
         colors.HexColor("#f0fdf4"), colors.HexColor("#bbf7d0")),
    ]:
        if items:
            body = "\n".join(f"• {x}" for x in items)
            story += [HRFlowable(width="100%",thickness=.5,color=BORDER),
                      Paragraph(title_txt, bold11)]
            t = Table([[Paragraph(f"<b>{title_txt}</b>", ts),
                        Paragraph(body, bs)]], colWidths=[W*.15, W*.85])
            t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),.5,bc),
                                   ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
                                   ("LEFTPADDING",(0,0),(-1,-1),10),("VALIGN",(0,0),(-1,-1),"TOP")]))
            story.append(t)

    story.append(Spacer(1, 20))
    doc.build(story)
    return buf.getvalue()


def build_claim_pdf(claim: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    BLACK  = colors.HexColor("#111111")
    GRAY   = colors.HexColor("#6b7280")
    LGRAY  = colors.HexColor("#f3f4f6")
    BORDER = colors.HexColor("#e5e7eb")
    GREEN  = colors.HexColor("#10b981")
    W = A4[0] - 40*mm
    now = datetime.now().strftime("%B %d, %Y  %H:%M")

    def s(name, **kw):
        defaults = dict(fontName="Helvetica", fontSize=9, textColor=BLACK, leading=14)
        defaults.update(kw); return ParagraphStyle(name, **defaults)

    story = []
    hdr = Table([[Paragraph("InsurAI", s("l", fontName="Helvetica-Bold", fontSize=18, leading=22)),
                  Paragraph(f"<font color='#6b7280'>Claim Receipt</font><br/>"
                             f"<font color='#9ca3af' size='8'>Generated: {now}</font>", s("b"))]],
                colWidths=[W*.45, W*.55])
    hdr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(1,0),(1,0),"RIGHT"),
                              ("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story += [hdr, HRFlowable(width="100%", thickness=1.5, color=BLACK, spaceAfter=12)]

    story.append(Paragraph("CLAIM APPROVED", s("h", fontName="Helvetica-Bold", fontSize=28,
                                                textColor=GREEN, leading=34, spaceAfter=4)))
    story.append(Paragraph("Your claim has been reviewed and approved. Payment will be sent immediately.",
                            s("sub", textColor=GRAY, leading=16)))
    story.append(Spacer(1, 16))

    def mc(v, l): return [Paragraph(v, s("mv", fontName="Helvetica-Bold", fontSize=20,
                                          leading=24, alignment=TA_CENTER)),
                           Paragraph(l, s("ml", fontSize=8, textColor=GRAY, leading=11, alignment=TA_CENTER))]
    metrics = Table([[mc(f"${claim.get('payout', 900):,}", "Payout Amount"),
                      mc(f"{claim.get('processing_time', 4.6)}s", "Processing Time"),
                      mc(claim.get("claim_id", "CLM-0001"), "Claim ID"),
                      mc("Approved", "Status")]],
                    colWidths=[W/4]*4)
    metrics.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.5,BORDER),
        ("BACKGROUND",(0,0),(-1,-1),LGRAY),("TOPPADDING",(0,0),(-1,-1),12),
        ("BOTTOMPADDING",(0,0),(-1,-1),12),("TEXTCOLOR",(3,0),(3,0),GREEN)]))
    story += [metrics, Spacer(1, 16)]

    details = [
        ["Property Category", claim.get("category", "—")],
        ["Incident Description", claim.get("damage_description", "—")],
        ["Injuries Reported", "Yes" if claim.get("injured") else "No"],
        ["Policyholder", claim.get("user_id", "user_1")],
        ["Date Filed", now],
        ["Signed By", claim.get("signature", "—")],
    ]
    det_tbl = Table([[Paragraph(f"<b>{k}</b>", s("k")), Paragraph(v, s("v"))]
                      for k, v in details], colWidths=[W*.35, W*.65])
    det_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white, LGRAY]),
        ("GRID",(0,0),(-1,-1),.4,BORDER),("TOPPADDING",(0,0),(-1,-1),8),
        ("BOTTOMPADDING",(0,0),(-1,-1),8),("LEFTPADDING",(0,0),(-1,-1),12)]))
    story += [Paragraph("Claim Details", s("sec", fontName="Helvetica-Bold", fontSize=11,
                                            leading=16, spaceBefore=14, spaceAfter=6)),
              det_tbl, Spacer(1, 20),
              HRFlowable(width="100%", thickness=.5, color=BORDER, spaceBefore=4),
              Paragraph("This claim was processed automatically by InsurAI. "
                        "Keep this receipt for your records.",
                        s("f", fontSize=8, textColor=GRAY, leading=11, alignment=TA_CENTER))]
    doc.build(story)
    return buf.getvalue()


# ── CSS ───────────────────────────────────────────────────────────────────────

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    html,body,[class*="css"]{ font-family:'Inter',system-ui,sans-serif !important; }
    #MainMenu,footer{ visibility:hidden; }
    .stDeployButton,[data-testid="stToolbar"]{ display:none; }
    .stApp,[data-testid="stAppViewContainer"]{ background:#f4f4f0 !important; }
    [data-testid="stHeader"]{ background:#111 !important; border-bottom:1px solid rgba(255,255,255,.06) !important; }

    /* Sidebar */
    [data-testid="stSidebar"]{ background:#fff !important; border-right:1px solid #e5e7eb !important; }
    [data-testid="stSidebar"] .block-container{ padding:32px 20px !important; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"]{ background:transparent !important; border-bottom:2px solid #e5e7eb !important; gap:0 !important; }
    .stTabs [data-baseweb="tab"]{ background:transparent !important; border:none !important; padding:12px 24px !important;
        font-size:14px !important; font-weight:500 !important; color:#6b7280 !important;
        border-bottom:2px solid transparent !important; margin-bottom:-2px !important; }
    .stTabs [aria-selected="true"]{ color:#111 !important; border-bottom:2px solid #111 !important; }
    .stTabs [data-baseweb="tab-panel"]{ padding:0 !important; }

    /* File uploader */
    [data-testid="stFileUploader"]{ border:none !important; background:transparent !important; padding:0 !important; }
    [data-testid="stFileUploader"]>div{ border:2px dashed #d1d5db !important; border-radius:16px !important;
        background:#fff !important; transition:border-color .2s !important; }
    [data-testid="stFileUploader"]>div:hover{ border-color:#111 !important; }
    [data-testid="stFileUploaderDropzoneInstructions"]{ padding:40px 32px !important; }

    /* Buttons */
    .stButton>button{ background:#111 !important; color:#fff !important; border:none !important;
        border-radius:6px !important; font-size:14px !important; font-weight:500 !important;
        padding:10px 24px !important; transition:background .15s !important; }
    .stButton>button:hover{ background:#333 !important; }
    [data-testid="stDownloadButton"] button{ background:#fff !important; color:#111 !important;
        border:1.5px solid #d1d5db !important; border-radius:6px !important;
        font-size:14px !important; font-weight:500 !important; padding:10px 24px !important;
        transition:all .15s !important; }
    [data-testid="stDownloadButton"] button:hover{ border-color:#111 !important; }
    [data-testid="stSidebar"] .stButton>button{ background:#fff !important; color:#374151 !important;
        border:1.5px solid #e5e7eb !important; font-size:13px !important; width:100% !important; padding:8px 12px !important; }
    [data-testid="stSidebar"] .stButton>button:hover{ border-color:#111 !important; color:#111 !important; }

    /* Chat */
    [data-testid="stChatInput"]{ border:1.5px solid #d1d5db !important; border-radius:8px !important; background:#fff !important; }
    [data-testid="stChatInput"]:focus-within{ border-color:#111 !important; }
    [data-testid="stChatInputSubmitButton"] button{ background:#111 !important; border-radius:6px !important; }
    .stChatMessageContent{ background:#fff !important; border:1px solid #e5e7eb !important;
        border-radius:10px !important; font-size:15px !important; box-shadow:0 1px 2px rgba(0,0,0,.04) !important; }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) .stChatMessageContent{
        background:#111 !important; border-color:#111 !important; color:#f9fafb !important; }

    /* Metrics */
    [data-testid="stMetric"]{ background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:16px 20px; }
    [data-testid="stMetricLabel"]{ font-size:12px !important; color:#6b7280 !important; }
    [data-testid="stMetricValue"]{ font-size:22px !important; font-weight:700 !important; color:#111 !important; }

    /* Inputs */
    .stTextInput input{ border:1.5px solid #e5e7eb !important; border-radius:6px !important; font-size:14px !important; }
    .stTextInput input:focus{ border-color:#111 !important; box-shadow:none !important; }
    .stTextArea textarea{ border:1.5px solid #e5e7eb !important; border-radius:8px !important; font-size:14px !important; }
    .stTextArea textarea:focus{ border-color:#111 !important; box-shadow:none !important; }

    /* Tables */
    .stMarkdown table{ width:100%; border-collapse:collapse; font-size:14px; }
    .stMarkdown th{ background:#f9fafb; font-weight:600; padding:10px 14px;
        border-bottom:2px solid #e5e7eb; text-align:left; color:#111; }
    .stMarkdown td{ padding:10px 14px; border-bottom:1px solid #f3f4f6; color:#374151; }

    /* Claim flow */
    .step-badge{ display:inline-flex; align-items:center; gap:8px; margin-bottom:20px; }
    .step-dot{ width:28px; height:28px; border-radius:50%; background:#111; color:#fff;
        font-size:13px; font-weight:700; display:inline-flex; align-items:center; justify-content:center; }
    .step-dot-inactive{ background:#e5e7eb; color:#9ca3af; }
    .step-line{ width:40px; height:2px; background:#e5e7eb; }

    /* Category cards */
    div[data-testid="stButton"].cat-btn > button{
        background:#fff !important; color:#111 !important;
        border:1.5px solid #e5e7eb !important; border-radius:10px !important;
        font-size:14px !important; font-weight:500 !important;
        padding:14px 16px !important; text-align:left !important;
        width:100% !important; transition:all .15s !important;
    }
    div[data-testid="stButton"].cat-btn > button:hover{
        border-color:#111 !important; background:#f9fafb !important;
    }

    /* Claim approved */
    .approved-banner{
        background:linear-gradient(135deg,#111 0%,#1f2937 100%);
        border-radius:16px; padding:48px; text-align:center; margin-bottom:24px;
    }
    .approved-check{ font-size:56px; margin-bottom:16px; }
    .approved-title{ font-size:40px; font-weight:800; color:#10b981; letter-spacing:-1px; margin-bottom:8px; }
    .approved-sub{ font-size:16px; color:rgba(255,255,255,.6); font-weight:300; }

    /* Pledge */
    .pledge-card{
        background:#fff; border:1px solid #e5e7eb; border-radius:16px;
        padding:36px; max-width:520px; margin:0 auto;
    }
    .pledge-title{ font-size:22px; font-weight:700; color:#111; letter-spacing:-.5px; margin-bottom:12px; }
    .pledge-text{ font-size:14px; color:#6b7280; line-height:1.7; margin-bottom:24px; }
    .sig-line{ border-bottom:2px solid #111; margin-top:24px; margin-bottom:4px; }
    .sig-label{ font-size:11px; color:#9ca3af; text-transform:uppercase; letter-spacing:1px; }
    .swear-btn > button{
        background:#111 !important; color:#fff !important; font-size:16px !important;
        font-weight:800 !important; padding:16px 32px !important; border-radius:8px !important;
        letter-spacing:1px !important; width:100% !important; margin-top:24px !important;
    }
    </style>
    """, unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown(
            "<div style='font-size:18px;font-weight:700;color:#111;margin-bottom:4px;'>InsurAI</div>"
            "<div style='font-size:12px;color:#9ca3af;margin-bottom:32px;'>Damage Assessment & Claims</div>",
            unsafe_allow_html=True)

        st.markdown("<div style='font-size:11px;font-weight:600;text-transform:uppercase;"
                    "letter-spacing:1px;color:#9ca3af;margin-bottom:8px;'>Session</div>",
                    unsafe_allow_html=True)
        user_id = st.text_input("User ID", value="user_1", label_visibility="collapsed")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if st.button("Clear conversation"):
            st.session_state.messages = []
            st.rerun()

        st.markdown(
            "<hr style='border:none;border-top:1px solid #f3f4f6;margin:20px 0'>"
            "<div style='font-size:11px;font-weight:600;text-transform:uppercase;"
            "letter-spacing:1px;color:#9ca3af;margin-bottom:10px;'>Quick queries</div>",
            unsafe_allow_html=True)
        for ex in ["What policies does the customer have?",
                   "Show all active claims", "Compare coverage limits"]:
            if st.button(ex, key=f"ex_{ex}"):
                st.session_state.pending_query = ex
                st.rerun()

        st.markdown(
            "<hr style='border:none;border-top:1px solid #f3f4f6;margin:20px 0'>"
            "<div style='font-size:11px;color:#d1d5db;line-height:1.8'>"
            "Claude Vision · RAG · SQLite<br>Session memory: on</div>",
            unsafe_allow_html=True)
    return user_id


# ── Damage Analysis tab ───────────────────────────────────────────────────────

def render_damage_tab():
    st.markdown(
        "<div style='padding:32px 0 24px'>"
        "<div style='font-size:11px;font-weight:600;letter-spacing:2px;text-transform:uppercase;"
        "color:#9ca3af;margin-bottom:8px'>01 — Computer Vision</div>"
        "<div style='font-size:26px;font-weight:700;color:#111;letter-spacing:-.5px'>"
        "Vehicle Damage Assessment</div>"
        "<div style='font-size:15px;color:#6b7280;margin-top:8px;max-width:560px'>"
        "Upload a photo of a damaged vehicle. AI will identify damage zones, "
        "assess severity, and estimate repair costs."
        "</div></div>", unsafe_allow_html=True)

    col_up, col_prev = st.columns([1, 1], gap="large")
    with col_up:
        uploaded = st.file_uploader(
            "Drag & drop a photo or click to browse",
            type=["jpg", "jpeg", "png", "webp"],
            help="Supported: JPG, PNG, WEBP — max 200 MB",
        )
        if uploaded:
            media_type = f"image/{uploaded.type.split('/')[-1]}"
            if media_type == "image/jpg":
                media_type = "image/jpeg"
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            btn_col, dl_col, mech_col = st.columns(3, gap="small")
            with btn_col:
                analyze_btn = st.button("Analyze damage", use_container_width=True)
            with dl_col:
                if st.session_state.get("damage_result") and "error" not in st.session_state["damage_result"]:
                    ts = datetime.now().strftime("%Y%m%d_%H%M")
                    st.download_button("Download PDF",
                                       data=build_damage_pdf(st.session_state["damage_result"]),
                                       file_name=f"damage_report_{ts}.pdf",
                                       mime="application/pdf", use_container_width=True)
            with mech_col:
                if st.session_state.get("damage_result") and "error" not in st.session_state["damage_result"]:
                    if st.button("Send to Mechanic", use_container_width=True):
                        st.session_state.mechanic_sent = True
            if analyze_btn:
                st.session_state.last_analyzed = uploaded.name
                with st.spinner("Claude Vision is analyzing the photo..."):
                    result = analyze_damage(uploaded.getvalue(), media_type)
                st.session_state.damage_result = result
                st.rerun()

    with col_prev:
        if uploaded:
            st.image(uploaded, use_container_width=True, caption=uploaded.name)
        else:
            st.markdown(
                "<div style='height:220px;background:#fff;border:1.5px dashed #e5e7eb;"
                "border-radius:12px;display:flex;align-items:center;justify-content:center;"
                "color:#d1d5db;font-size:14px;'>Photo preview will appear here</div>",
                unsafe_allow_html=True)

    result = st.session_state.get("damage_result")
    if not result:
        return
    if "error" in result:
        st.error(f"Analysis error: {result['error']}")
        return

    st.markdown("<hr style='border:none;border-top:1px solid #e5e7eb;margin:24px 0'>", unsafe_allow_html=True)

    sev    = result.get("overall_severity", "—")
    c_min  = result.get("total_cost_min", 0)
    c_max  = result.get("total_cost_max", 0)
    r_time = result.get("repair_time_days", "—")
    can_d  = result.get("can_drive", True)
    conf   = result.get("confidence", 0)

    for col, label, value in zip(
        st.columns(5),
        ["Repair Cost", "Severity", "Repair Time", "Can Drive", "AI Confidence"],
        [f"${c_min:,}–${c_max:,}", SEVERITY_LABEL.get(sev, sev),
         r_time, "Yes" if can_d else "No", f"{int(conf*100)}%"]
    ):
        with col:
            st.metric(label, value)

    desc = result.get("vehicle_description", "")
    if desc:
        st.markdown(
            f"<div style='background:#fff;border:1px solid #e5e7eb;border-radius:10px;"
            f"padding:14px 20px;font-size:14px;color:#374151;margin:16px 0'>"
            f"<span style='font-weight:600;color:#111'>Vehicle: </span>{desc}</div>",
            unsafe_allow_html=True)

    parts = result.get("damaged_parts", [])
    if parts:
        st.markdown("<div style='font-size:14px;font-weight:600;color:#111;margin:20px 0 10px'>"
                    "Damaged Components</div>", unsafe_allow_html=True)
        rows_html = ""
        for p in parts:
            sev_p = p.get("severity", "low")
            bg, txt, _ = SEVERITY_COLOR.get(sev_p, ("#f3f4f6","#374151","#9ca3af"))
            c1, c2 = p.get("cost_min",0), p.get("cost_max",0)
            rows_html += (
                f"<tr>"
                f"<td style='padding:12px 16px;font-weight:500;color:#111'>{p.get('part','')}</td>"
                f"<td style='padding:12px 16px'><span style='background:{bg};color:{txt};"
                f"padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600'>"
                f"{SEVERITY_LABEL.get(sev_p,sev_p)}</span></td>"
                f"<td style='padding:12px 16px;color:#6b7280;font-size:13px'>{p.get('description','')}</td>"
                f"<td style='padding:12px 16px'><span style='background:#f3f4f6;color:#374151;"
                f"padding:3px 8px;border-radius:4px;font-size:12px'>"
                f"{REPAIR_LABEL.get(p.get('repair_type',''),p.get('repair_type',''))}</span></td>"
                f"<td style='padding:12px 16px;font-weight:600;color:#111'>${c1:,}–${c2:,}</td>"
                f"</tr>"
            )
        st.markdown(
            f"<div style='background:#fff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden'>"
            f"<table style='width:100%;border-collapse:collapse'><thead>"
            f"<tr style='background:#111'>" +
            "".join(f"<th style='padding:10px 16px;text-align:left;font-size:11px;"
                    f"color:rgba(255,255,255,.7);font-weight:600;text-transform:uppercase;"
                    f"letter-spacing:1px'>{h}</th>"
                    for h in ["Component","Severity","Description","Work Type","Cost Range"]) +
            f"</tr></thead><tbody>{rows_html}</tbody></table></div>",
            unsafe_allow_html=True)

    safety = result.get("safety_concerns", [])
    recs   = result.get("recommendations", [])
    if safety or recs:
        c_s, c_r = st.columns(2, gap="medium")
        def info_box(col, items, title, bg, border, title_col, text_col):
            with col:
                li = "".join(f"<li style='margin-bottom:5px'>{x}</li>" for x in items)
                st.markdown(
                    f"<div style='background:{bg};border:1px solid {border};"
                    f"border-radius:10px;padding:16px 20px'>"
                    f"<div style='font-size:13px;font-weight:600;color:{title_col};margin-bottom:8px'>{title}</div>"
                    f"<ul style='margin:0;padding-left:18px;font-size:13px;color:{text_col}'>{li}</ul></div>",
                    unsafe_allow_html=True)
        if safety: info_box(c_s, safety, "Safety Concerns",   "#fef2f2","#fecaca","#991b1b","#7f1d1d")
        if recs:   info_box(c_r, recs,   "Recommendations",   "#f0fdf4","#bbf7d0","#166534","#14532d")

    # Mechanic sent notification
    if st.session_state.get("mechanic_sent"):
        st.markdown(
            "<div style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;"
            "padding:14px 20px;margin-top:16px;display:flex;align-items:center;gap:12px'>"
            "<span style='font-size:20px'>&#10003;</span>"
            "<div><div style='font-size:14px;font-weight:600;color:#166534'>Report sent to a certified mechanic</div>"
            "<div style='font-size:13px;color:#15803d;margin-top:2px'>"
            "A certified mechanic will review the damage report and contact you within 24 hours.</div></div></div>",
            unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    dl_c, mech_c, _ = st.columns([1, 1, 2])
    with dl_c:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        st.download_button("Download PDF Report",
                           data=build_damage_pdf(result),
                           file_name=f"damage_report_{ts}.pdf",
                           mime="application/pdf", use_container_width=True)
    with mech_c:
        if st.button("Send to Certified Mechanic", use_container_width=True):
            st.session_state.mechanic_sent = True
            st.rerun()


# ── File a Claim tab ──────────────────────────────────────────────────────────

def render_claim_tab(user_id: str):
    # Init state
    for k, v in [("claim_step", 1), ("claim_messages", []),
                 ("claim_data", {}), ("claim_hurt_answered", False),
                 ("claim_damage_answered", False), ("claim_category", None),
                 ("claim_result", None), ("claim_signature", "")]:
        if k not in st.session_state:
            st.session_state[k] = v

    step = st.session_state.claim_step

    # ── Step indicator ────────────────────────────────────────────────────────
    steps = ["Incident Report", "Pledge of Honesty", "Claim Result"]
    st.markdown("<div style='padding:28px 0 8px;display:flex;gap:12px;align-items:center'>", unsafe_allow_html=True)
    dots_html = ""
    for i, lbl in enumerate(steps, 1):
        active = "background:#111;color:#fff;" if i == step else "background:#e5e7eb;color:#9ca3af;"
        line   = "<div style='width:40px;height:2px;background:#e5e7eb;'></div>" if i < len(steps) else ""
        dots_html += (
            f"<div style='display:flex;align-items:center;gap:8px'>"
            f"<div style='width:28px;height:28px;border-radius:50%;{active}"
            f"font-size:12px;font-weight:700;display:flex;align-items:center;"
            f"justify-content:center;flex-shrink:0'>{i}</div>"
            f"<span style='font-size:13px;font-weight:500;color:{'#111' if i==step else '#9ca3af'}'>{lbl}</span>"
            f"</div>{line}"
        )
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;padding:28px 0 24px'>{dots_html}</div>",
        unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════
    # STEP 1 — Incident Report Chat
    # ═══════════════════════════════════════════════════════════════════
    if step == 1:
        st.markdown(
            "<div style='font-size:11px;font-weight:600;letter-spacing:2px;text-transform:uppercase;"
            "color:#9ca3af;margin-bottom:8px'>02 — Guided Claims</div>"
            "<div style='font-size:26px;font-weight:700;color:#111;letter-spacing:-.5px'>"
            "Tell us what happened</div>"
            "<div style='font-size:15px;color:#6b7280;margin-top:6px;margin-bottom:24px'>"
            "Chat with our AI assistant to report your incident — no long forms.</div>",
            unsafe_allow_html=True)

        col_chat, col_cats = st.columns([3, 2], gap="large")

        with col_chat:
            # Seed first bot message
            if not st.session_state.claim_messages:
                st.session_state.claim_messages = [
                    {"role": "assistant",
                     "content": "Hi! I'm here to help you file your insurance claim quickly.\n\n"
                                "First — **did anyone get hurt?**"}
                ]

            for msg in st.session_state.claim_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            user_msg = st.chat_input("Type your answer...")
            if user_msg:
                st.session_state.claim_messages.append({"role": "user", "content": user_msg})

                # State machine for guided questions
                if not st.session_state.claim_hurt_answered:
                    st.session_state.claim_data["injured"] = any(
                        w in user_msg.lower() for w in ["yes","yeah","yep","hurt","injured","someone"])
                    st.session_state.claim_hurt_answered = True
                    st.session_state.claim_messages.append({
                        "role": "assistant",
                        "content": "Got it. **What was stolen or damaged?** Please describe the incident."
                    })
                elif not st.session_state.claim_damage_answered:
                    st.session_state.claim_data["damage_description"] = user_msg
                    st.session_state.claim_damage_answered = True
                    st.session_state.claim_messages.append({
                        "role": "assistant",
                        "content": "Thank you. Now please **select a property category** on the right "
                                   "that best describes what was affected."
                    })
                else:
                    st.session_state.claim_messages.append({
                        "role": "assistant",
                        "content": "Please select a **property category** from the panel on the right to continue."
                    })
                st.rerun()

        with col_cats:
            st.markdown(
                "<div style='font-size:13px;font-weight:600;color:#111;margin-bottom:12px;'>"
                "What was affected?</div>", unsafe_allow_html=True)

            for cat, desc in PROPERTY_CATEGORIES:
                selected = st.session_state.claim_category == cat
                border = "border:2px solid #111;" if selected else "border:1.5px solid #e5e7eb;"
                bg     = "background:#f9fafb;" if selected else "background:#fff;"
                check  = " ✓" if selected else ""
                if st.button(f"{cat}{check}", key=f"cat_{cat}", use_container_width=True,
                             help=desc, disabled=not st.session_state.claim_damage_answered):
                    st.session_state.claim_category = cat
                    st.session_state.claim_data["category"] = cat
                    st.rerun()
                st.markdown(
                    f"<div style='font-size:11px;color:#9ca3af;margin:-10px 0 8px 4px'>{desc}</div>",
                    unsafe_allow_html=True)

            if st.session_state.claim_category and st.session_state.claim_damage_answered:
                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                if st.button("Continue to Pledge →", use_container_width=True):
                    st.session_state.claim_step = 2
                    st.rerun()

    # ═══════════════════════════════════════════════════════════════════
    # STEP 2 — Pledge of Honesty
    # ═══════════════════════════════════════════════════════════════════
    elif step == 2:
        _, col_pledge, _ = st.columns([1, 2, 1])
        with col_pledge:
            st.markdown(
                "<div style='background:#fff;border:1px solid #e5e7eb;border-radius:16px;"
                "padding:40px;margin-top:8px'>", unsafe_allow_html=True)

            st.markdown(
                "<div style='font-size:22px;font-weight:800;color:#111;letter-spacing:-.5px;"
                "margin-bottom:16px'>Pledge of Honesty</div>"
                "<div style='font-size:14px;color:#6b7280;line-height:1.8;margin-bottom:24px'>"
                "You are part of a community built on trust. By submitting this claim, "
                "you promise to only claim losses you have actually suffered. "
                "Fraudulent claims harm every member of our community and are "
                "a violation of your policy terms."
                "</div>", unsafe_allow_html=True)

            photo = st.camera_input("Take a photo to verify your identity",
                                    label_visibility="visible")
            if not photo:
                st.markdown(
                    "<div style='font-size:12px;color:#9ca3af;margin:-8px 0 16px'>"
                    "Camera access is optional — you may skip this step.</div>",
                    unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.markdown(
                "<div style='font-size:12px;font-weight:600;color:#9ca3af;"
                "text-transform:uppercase;letter-spacing:1px;margin-bottom:6px'>"
                "Electronic Signature</div>", unsafe_allow_html=True)

            sig = st.text_input("Type your full name as your signature",
                                placeholder="Your full name...",
                                label_visibility="collapsed",
                                value=st.session_state.claim_signature)
            st.session_state.claim_signature = sig

            st.markdown(
                "<div style='border-bottom:2px solid #111;margin:4px 0 2px'></div>"
                "<div style='font-size:10px;color:#9ca3af;letter-spacing:1px;text-transform:uppercase'>"
                "Signature</div>", unsafe_allow_html=True)

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

            if sig.strip():
                if st.button("I SWEAR I'LL BE HONEST", use_container_width=True):
                    st.session_state.claim_data["signature"] = sig
                    st.session_state.claim_data["user_id"] = user_id
                    # Simulate AI processing
                    proc_time = round(random.uniform(3.8, 6.2), 1)
                    payout = random.choice([600, 750, 900, 1100, 1400])
                    claim_id = f"CLM-{random.randint(1000,9999)}"
                    st.session_state.claim_result = {
                        "payout": payout,
                        "processing_time": proc_time,
                        "claim_id": claim_id,
                        **st.session_state.claim_data,
                    }
                    st.session_state.claim_step = 3
                    st.rerun()
            else:
                st.markdown(
                    "<div style='background:#111;color:#fff;border-radius:8px;"
                    "padding:16px;text-align:center;font-size:16px;font-weight:800;"
                    "letter-spacing:1px;opacity:.35;margin-top:16px'>"
                    "I SWEAR I'LL BE HONEST</div>", unsafe_allow_html=True)
                st.caption("Please enter your signature to continue")

            st.markdown("</div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════
    # STEP 3 — Claim Approved
    # ═══════════════════════════════════════════════════════════════════
    elif step == 3:
        cr = st.session_state.claim_result or {}

        st.markdown(
            "<div style='background:linear-gradient(135deg,#111 0%,#1f2937 100%);"
            "border-radius:16px;padding:56px 48px;text-align:center;margin:8px 0 32px'>"
            "<div style='font-size:64px;margin-bottom:16px'>✓</div>"
            "<div style='font-size:44px;font-weight:800;color:#10b981;letter-spacing:-1.5px;"
            "margin-bottom:8px'>CLAIM APPROVED</div>"
            "<div style='font-size:17px;color:rgba(255,255,255,.6);font-weight:300;max-width:480px;margin:0 auto'>"
            "We reviewed your claim and found it valid. "
            "Payment will be sent immediately."
            "</div></div>", unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        for col, label, value in [
            (c1, "Payout",           f"${cr.get('payout', 900):,}"),
            (c2, "Processing Time",  f"{cr.get('processing_time', 4.6)}s"),
            (c3, "Claim ID",         cr.get("claim_id", "CLM-0001")),
            (c4, "Status",           "Approved"),
        ]:
            with col:
                st.metric(label, value)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Claim summary
        with st.expander("Claim Summary", expanded=True):
            st.markdown(
                f"| Field | Details |\n|---|---|\n"
                f"| **Property Category** | {cr.get('category','—')} |\n"
                f"| **Incident Description** | {cr.get('damage_description','—')} |\n"
                f"| **Injuries Reported** | {'Yes' if cr.get('injured') else 'No'} |\n"
                f"| **Signed By** | {cr.get('signature','—')} |\n"
                f"| **Policyholder** | {cr.get('user_id','—')} |"
            )

        btn1, btn2, btn3 = st.columns(3)
        with btn1:
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button("Download Receipt",
                               data=build_claim_pdf(cr),
                               file_name=f"claim_receipt_{ts}.pdf",
                               mime="application/pdf", use_container_width=True)
        with btn2:
            if st.button("File Another Claim", use_container_width=True):
                for k in ["claim_step","claim_messages","claim_data","claim_hurt_answered",
                          "claim_damage_answered","claim_category","claim_result","claim_signature"]:
                    del st.session_state[k]
                st.rerun()


# ── Insurance Chat tab ────────────────────────────────────────────────────────

def render_chat_tab(user_id: str):
    st.markdown(
        "<div style='padding:32px 0 16px'>"
        "<div style='font-size:11px;font-weight:600;letter-spacing:2px;text-transform:uppercase;"
        "color:#9ca3af;margin-bottom:8px'>03 — Knowledge Base</div>"
        "<div style='font-size:26px;font-weight:700;color:#111;letter-spacing:-.5px'>"
        "Insurance Assistant</div>"
        "<div style='font-size:15px;color:#6b7280;margin-top:8px'>"
        "Ask anything about policies, customers, or claims.</div></div>",
        unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_query" not in st.session_state:
        st.session_state.pending_query = None

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    pending = st.session_state.get("pending_query")
    if pending:
        st.session_state.pending_query = None
        prompt = pending
    else:
        prompt = st.chat_input("Ask about insurance policies, claims, customers...")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            ph = st.empty()
            with st.spinner(""):
                answer = query_agent(prompt, user_id)
            for i in range(0, len(answer), 8):
                ph.markdown(answer[: i+8] + "▌", unsafe_allow_html=True)
                time.sleep(0.008)
            ph.markdown(answer, unsafe_allow_html=True)
        st.session_state.messages.append({"role": "assistant", "content": answer})


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="InsurAI — Damage Assessment",
                       page_icon="◆", layout="wide",
                       initial_sidebar_state="expanded")
    inject_css()

    if "damage_result" not in st.session_state:
        st.session_state.damage_result = None

    user_id = render_sidebar()

    tab1, tab2, tab3 = st.tabs(["Damage Analysis", "File a Claim", "Insurance Chat"])
    with tab1:
        render_damage_tab()
    with tab2:
        render_claim_tab(user_id)
    with tab3:
        render_chat_tab(user_id)


if __name__ == "__main__":
    main()
