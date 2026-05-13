[fgw_streamlit (1).py](https://github.com/user-attachments/files/27705685/fgw_streamlit.1.py)
[requirements_streamlit.txt](https://github.com/user-attachments/files/27705684/requirements_streamlit.txt)
# FGW19-IEC3---Tool-"""
FGW/IEC3 Tool - Streamlit Version für Microsoft Teams
======================================================

100% KOSTENLOS - Keine Installation nötig!

Installation:
    pip install streamlit pdfplumber pypdf numpy matplotlib

Start lokal zum Testen:
    streamlit run fgw_streamlit.py

Deployment auf Streamlit Cloud:
    → Kostenlos!
    → Anleitung siehe unten
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pdfplumber
import io
import re
from pathlib import Path
import tempfile

# ===== SEITEN-KONFIGURATION =====
st.set_page_config(
    page_title="FGW/IEC3 Markierungs-Tool",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===== CUSTOM CSS =====
st.markdown("""
<style>
    .main {background: linear-gradient(135deg, #f8faf9 0%, #e8f5e9 100%);}
    .stButton>button {
        background: linear-gradient(135deg, #1e6b2e 0%, #27ae60 100%);
        color: white;
        font-weight: 600;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        border: none;
    }
    .stButton>button:hover {background: #1e6b2e;}
    h1 {color: #1e6b2e;}
    .success-box {
        background: #d5edd9;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #27ae60;
        margin: 1rem 0;
    }
    .info-box {
        background: #fff8e1;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ===== BERECHNUNGSFUNKTIONEN =====

def calc_fgw19(v, P, P_nenn, nh):
    P_85 = 0.85 * P_nenn
    max_idx = np.argmax(P)
    v_85 = float(np.interp(P_85, P[:max_idx+1], v[:max_idx+1]))
    v_low = 0.8 * v_85
    v_high = 1.3 * v_85
    f = np.log(10/0.05) / np.log(nh/0.05)
    return {
        'name': 'FGW TR 1 Rev. 19',
        'v_ref': v_85, 'v_ref_name': 'V₈₅%',
        'v_low_NH': v_low, 'v_high_NH': v_high,
        'v_low_10m': v_low*f, 'v_high_10m': v_high*f,
        'formula': '0,8·V₈₅% – 1,3·V₈₅%'
    }

def calc_iec3(v, P, P_nenn, nh):
    max_idx = np.argmax(P)
    v_n = float(np.interp(P_nenn, P[:max_idx+1], v[:max_idx+1]))
    v_low = 0.3 * v_n
    v_high = 1.2 * v_n
    f = np.log(10/0.05) / np.log(nh/0.05)
    return {
        'name': 'IEC 61400-1 Ed. 3',
        'v_ref': v_n, 'v_ref_name': 'V_Nenn',
        'v_low_NH': v_low, 'v_high_NH': v_high,
        'v_low_10m': v_low*f, 'v_high_10m': v_high*f,
        'formula': '0,3·V_Nenn – 1,2·V_Nenn'
    }

# ===== EXTRAKTIONSFUNKTIONEN =====

def extract_nh(text):
    for p in [r'Nabenhöhe[:\s]+(\d+)', r'NH[:\s=]+(\d+)', r'-(\d{2,3})-']:
        for m in re.findall(p, text, re.I):
            nh = int(m)
            if 50 <= nh <= 200:
                return float(nh)
    return None

def extract_mode(text):
    patterns = [
        r'Betriebsmodus\s+\d+\s*kW', r'Betriebsmodus\s+[A-Z][a-z]+',
        r'N\d+\s+dB', r'Mode\s+\d+', r'NR\s+\d+'
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(0)[:40]
    return "Standard"

def parse_table(table):
    v, p = [], []
    if not table or len(table) < 2:
        return v, p
    h = table[0]
    v_col = p_col = None
    if len(h) == 2:
        ht = ''.join([str(c) for c in h if c]).lower()
        if 'm/s' in ht or 'kw' in ht:
            v_col, p_col = 0, 1
    if v_col is None:
        for i, c in enumerate(h):
            if not c:
                continue
            cl = str(c).lower()
            if any(k in cl for k in ['wind','v ','m/s']) and v_col is None:
                v_col = i
            elif any(k in cl for k in ['leistung','power','kw']) and 'ct' not in cl and p_col is None:
                p_col = i
    if v_col is None or p_col is None:
        return v, p
    for row in table[1:]:
        try:
            vv = float(re.sub(r'[^\d.]','',str(row[v_col]).replace(',','.')))
            pp = float(re.sub(r'[^\d.]','',str(row[p_col]).replace(',','.')))
            if 0 <= vv <= 30 and 0 <= pp <= 10000:
                v.append(vv)
                p.append(pp)
        except:
            pass
    return v, p

def extract_curves(pdf_file):
    curves = []
    with pdfplumber.open(pdf_file) as pdf:
        text_all = "\n".join([pg.extract_text() for pg in pdf.pages])
        g_nh = extract_nh(text_all)
        for pn, pg in enumerate(pdf.pages, 1):
            pt = pg.extract_text()
            for table in pg.extract_tables():
                v, p = parse_table(table)
                if len(v) > 5:
                    curves.append({
                        'v': v, 'P': p,
                        'mode': extract_mode(pt) or f"Seite {pn}",
                        'nabenhoehe_auto': extract_nh(pt) or g_nh,
                        'P_nenn': max(p),
                        'id': len(curves)
                    })
    return curves

def create_pdf(curves, standard, nh):
    calc = calc_fgw19 if standard == 'FGW19' else calc_iec3
    output = io.BytesIO()
    
    with PdfPages(output) as pdf:
        for c in curves:
            v = np.array(c['v'])
            P = np.array(c['P'])
            res = calc(v, P, c['P_nenn'], nh)
            mask = (v >= res['v_low_NH']) & (v <= res['v_high_NH'])
            
            # Seite 1
            fig = plt.figure(figsize=(8.27,11.69))
            fig.patch.set_facecolor("white")
            fig.text(0.5,0.95,f"{res['name']}",ha="center",fontsize=14,weight="bold")
            fig.text(0.5,0.92,f"{c['mode']} · NH {nh:.0f}m",ha="center",fontsize=9,style="italic",color="#666")
            
            tdata = [
                ["Parameter","Wert"],["",""],
                ["Nennleistung",f"{c['P_nenn']:.0f} kW"],
                [res['v_ref_name'],f"{res['v_ref']:.2f} m/s"],
                ["Nabenhöhe",f"{nh:.0f} m"],
                ["Formel",res['formula']],["",""],
                [f"Bereich (NH {nh:.0f}m)",f"{res['v_low_NH']:.2f}–{res['v_high_NH']:.2f} m/s"],
                ["Bereich (10m)",f"{res['v_low_10m']:.2f}–{res['v_high_10m']:.2f} m/s"]
            ]
            
            ax = fig.add_axes((0.2,0.3,0.6,0.45))
            ax.axis("off")
            t = ax.table(cellText=tdata,cellLoc='left',loc='center',colWidths=[0.5,0.5])
            t.auto_set_font_size(False)
            t.set_fontsize(11)
            t.scale(1,2.3)
            for i,j in [(0,0),(0,1)]:
                t[(i,j)].set_facecolor('#1f4e79')
                t[(i,j)].set_text_props(color='white',weight='bold')
            for i in [7,8]:
                for j in [0,1]:
                    t[(i,j)].set_facecolor('#d5edd9')
                    t[(i,j)].set_text_props(weight='bold',color='#1e6b2e')
            pdf.savefig(fig,bbox_inches="tight")
            plt.close(fig)
            
            # Seite 2
            fig,ax = plt.subplots(figsize=(11,8))
            ax.axvspan(res['v_low_NH'],res['v_high_NH'],alpha=0.25,color='#2ecc71')
            ax.plot(v,P,'o-',lw=2,ms=3,color='#003f5c')
            ax.plot([res['v_ref']],[c['P_nenn']*0.85 if standard=='FGW19' else c['P_nenn']],'D',ms=10,color='#c0392b')
            ax.set_xlabel("Windgeschwindigkeit [m/s]",fontsize=11)
            ax.set_ylabel("Leistung [kW]",fontsize=11)
            ax.set_title(f"{res['name']} – {c['mode']}\nNH {nh:.0f}m",fontsize=12,weight='bold')
            ax.grid(True,alpha=0.3)
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
            
            # Seite 3
            fig = plt.figure(figsize=(8.27,11.69))
            fig.patch.set_facecolor("white")
            fig.text(0.5,0.96,f"Leistungskurve – {c['mode']}",ha="center",fontsize=13,weight="bold")
            fig.text(0.5,0.935,f"Grün: {res['name']} {res['v_low_NH']:.2f}–{res['v_high_NH']:.2f} m/s",ha="center",fontsize=9,style="italic",color='#1e6b2e')
            
            ax = fig.add_axes((0.15,0.05,0.7,0.87))
            ax.axis("off")
            
            tdata = [["v [m/s]","P [kW]","Im Bereich"]]
            for vv,pp,mm in zip(v,P,mask):
                tdata.append([f"{vv:.1f}",f"{pp:.0f}","✓" if mm else ""])
            
            t = ax.table(cellText=tdata,cellLoc='center',loc='upper center',colWidths=[0.3,0.4,0.3])
            t.auto_set_font_size(False)
            t.set_fontsize(8)
            t.scale(1,1.2)
            
            for i in range(len(tdata)):
                for j in range(3):
                    cell = t[(i,j)]
                    if i == 0:
                        cell.set_facecolor('#27ae60')
                        cell.set_text_props(color='white',weight='bold')
                    elif i > 0 and mask[i-1]:
                        cell.set_facecolor('#d5edd9')
                        cell.set_text_props(weight='bold',color='#1e6b2e')
                    else:
                        cell.set_facecolor('#fff' if i%2==0 else '#f7f9fc')
            
            pdf.savefig(fig,bbox_inches="tight")
            plt.close(fig)
    
    output.seek(0)
    return output

# ===== HAUPTANWENDUNG =====

st.title("⚡ FGW/IEC3 Markierungs-Tool")
st.markdown("**Automatische Bereichsmarkierung für Leistungskurven**")
st.markdown("---")

# Info-Box
st.markdown("""
<div class="info-box">
    <strong>ℹ️ Kostenlos für Ihr Team!</strong><br>
    Dieses Tool läuft komplett kostenlos auf Streamlit Cloud.
    Perfekt integrierbar in Microsoft Teams!
</div>
""", unsafe_allow_html=True)

# Schritt 1: PDF hochladen
st.header("1️⃣ PDF hochladen")
uploaded_file = st.file_uploader(
    "PDF mit Leistungskurve(n) auswählen",
    type=['pdf'],
    help="VENSYS, ENERCON, Siemens Gamesa PDFs"
)

if uploaded_file:
    st.success(f"✓ Datei geladen: {uploaded_file.name} ({uploaded_file.size/1024/1024:.2f} MB)")
    
    # Kurven extrahieren
    with st.spinner("🔍 Analysiere PDF..."):
        curves = extract_curves(uploaded_file)
    
    if not curves:
        st.error("❌ Keine Leistungskurven gefunden!")
        st.stop()
    
    # Schritt 2: Kurven auswählen
    st.header("2️⃣ Leistungskurven auswählen")
    st.success(f"✓ {len(curves)} Kurve(n) gefunden")
    
    curve_options = []
    for i, c in enumerate(curves):
        nh_text = f"{c['nabenhoehe_auto']:.0f}m" if c['nabenhoehe_auto'] else "?m"
        curve_options.append(
            f"[{i+1}] {c['mode']:30s} | NH {nh_text} | {len(c['v'])} Punkte | P_max {c['P_nenn']:.0f} kW"
        )
    
    selected_indices = st.multiselect(
        "Wählen Sie die Kurven aus:",
        range(len(curves)),
        format_func=lambda x: curve_options[x],
        default=range(len(curves))
    )
    
    if not selected_indices:
        st.warning("⚠️ Bitte wählen Sie mindestens eine Kurve aus!")
        st.stop()
    
    selected_curves = [curves[i] for i in selected_indices]
    
    # Schritt 3: Nabenhöhe
    st.header("3️⃣ Nabenhöhe eingeben")
    
    auto_nh = selected_curves[0].get('nabenhoehe_auto')
    if auto_nh:
        st.info(f"✓ Automatisch erkannt: {auto_nh:.0f} m")
        default_nh = int(auto_nh)
    else:
        st.warning("⚠️ Nabenhöhe nicht automatisch erkannt - bitte manuell eingeben!")
        default_nh = 100
    
    nabenhoehe = st.number_input(
        "Nabenhöhe (NH) in Metern:",
        min_value=50,
        max_value=200,
        value=default_nh,
        step=1,
        help="Nabenhöhe der Windenergieanlage"
    )
    
    # Schritt 4: Standard
    st.header("4️⃣ Bereichs-Standard wählen")
    
    standard = st.radio(
        "Wählen Sie den Standard:",
        ["FGW19", "IEC3"],
        format_func=lambda x: "FGW TR 1 Rev. 19 (0,8·V₈₅% – 1,3·V₈₅%)" if x == "FGW19" else "IEC 61400-1 Ed. 3 (0,3·V_Nenn – 1,2·V_Nenn)",
        help="FGW19 für Deutschland, IEC3 international"
    )
    
    # Schritt 5: Verarbeiten
    st.header("5️⃣ PDF erstellen")
    
    if st.button("🚀 PDF ERSTELLEN", type="primary", use_container_width=True):
        with st.spinner("⏳ Erstelle markiertes PDF..."):
            try:
                output_pdf = create_pdf(selected_curves, standard, nabenhoehe)
                
                filename = f"{uploaded_file.name.replace('.pdf','')}_{standard}_NH{nabenhoehe:.0f}m_markiert.pdf"
                
                st.markdown("""
                <div class="success-box">
                    <h3>✅ PDF erfolgreich erstellt!</h3>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Kurven", len(selected_curves))
                with col2:
                    st.metric("Standard", standard)
                with col3:
                    st.metric("Nabenhöhe", f"{nabenhoehe:.0f} m")
                
                st.download_button(
                    label="📥 PDF HERUNTERLADEN",
                    data=output_pdf,
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"❌ Fehler: {str(e)}")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #7f8c8d; font-size: 0.9rem;">
    <p>FGW TR 1 Rev. 19 · IEC 61400-1 Ed. 3 · Logarithmisches Windprofil (z₀=0,05m)</p>
    <p>Kostenlos gehostet auf Streamlit Cloud | Für Microsoft Teams optimiert</p>
</div>
""", unsafe_allow_html=True)
