"""FGW/IEC3 Tool - Vereinfacht OHNE matplotlib"""

import streamlit as st
import numpy as np
import pdfplumber
import io
import re
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import cm

st.set_page_config(page_title="FGW/IEC3 Tool", page_icon="⚡", layout="wide")

st.markdown("""<style>
.main{background:linear-gradient(135deg,#f8faf9 0%,#e8f5e9 100%)}
.stButton>button{background:#27ae60;color:white;font-weight:600;border-radius:8px;padding:0.5rem 2rem}
</style>""", unsafe_allow_html=True)

def calc_fgw19(v,P,Pn,nh):
    P85=0.85*Pn;mi=np.argmax(P);v85=float(np.interp(P85,P[:mi+1],v[:mi+1]))
    vl,vh=0.8*v85,1.3*v85;f=np.log(10/0.05)/np.log(nh/0.05)
    return{'name':'FGW19','v_ref':v85,'v_ref_name':'V₈₅%','v_low_NH':vl,'v_high_NH':vh,'v_low_10m':vl*f,'v_high_10m':vh*f,'formula':'0,8·V₈₅%–1,3·V₈₅%'}

def calc_iec3(v,P,Pn,nh):
    mi=np.argmax(P);vn=float(np.interp(Pn,P[:mi+1],v[:mi+1]))
    vl,vh=0.3*vn,1.2*vn;f=np.log(10/0.05)/np.log(nh/0.05)
    return{'name':'IEC3','v_ref':vn,'v_ref_name':'V_Nenn','v_low_NH':vl,'v_high_NH':vh,'v_low_10m':vl*f,'v_high_10m':vh*f,'formula':'0,3·V_Nenn–1,2·V_Nenn'}

def ext_nh(t):
    for p in[r'Nabenhöhe[:\s]+(\d+)',r'NH[:\s=]+(\d+)',r'-(\d{2,3})-']:
        for m in re.findall(p,t,re.I):
            n=int(m)
            if 50<=n<=200:return float(n)

def ext_mode(t):
    for p in[r'Betriebsmodus\s+\d+\s*kW',r'N\d+\s+dB',r'Mode\s+\d+']:
        m=re.search(p,t,re.I)
        if m:return m.group(0)[:40]
    return"Standard"

def parse_tbl(t):
    v,p=[],[]
    if not t or len(t)<2:return v,p
    h=t[0];vc=pc=None
    if len(h)==2:
        ht=''.join([str(c)for c in h if c]).lower()
        if'm/s'in ht or'kw'in ht:vc,pc=0,1
    if vc is None:
        for i,c in enumerate(h):
            if not c:continue
            cl=str(c).lower()
            if any(k in cl for k in['wind','v ','m/s'])and vc is None:vc=i
            elif any(k in cl for k in['leistung','power','kw'])and'ct'not in cl and pc is None:pc=i
    if vc is None or pc is None:return v,p
    for row in t[1:]:
        try:
            vv=float(re.sub(r'[^\d.]','',str(row[vc]).replace(',','.')))
            pp=float(re.sub(r'[^\d.]','',str(row[pc]).replace(',','.')))
            if 0<=vv<=30 and 0<=pp<=10000:v.append(vv);p.append(pp)
        except:pass
    return v,p

def ext_curves(pdf):
    cs=[]
    with pdfplumber.open(pdf)as f:
        txt="\n".join([pg.extract_text()for pg in f.pages])
        gnh=ext_nh(txt)
        for pn,pg in enumerate(f.pages,1):
            pt=pg.extract_text()
            for t in pg.extract_tables():
                v,p=parse_tbl(t)
                if len(v)>5:
                    cs.append({'v':v,'P':p,'mode':ext_mode(pt)or f"S{pn}",'nabenhoehe_auto':ext_nh(pt)or gnh,'P_nenn':max(p),'id':len(cs)})
    return cs

def mk_pdf(cs,std,nh):
    calc=calc_fgw19 if std=='FGW19'else calc_iec3
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=A4)
    styles=getSampleStyleSheet()
    story=[]
    
    for c in cs:
        v,P=np.array(c['v']),np.array(c['P'])
        r=calc(v,P,c['P_nenn'],nh)
        m=(v>=r['v_low_NH'])&(v<=r['v_high_NH'])
        
        # Titel
        story.append(Paragraph(f"<b>{r['name']} - {c['mode']}</b>",styles['Title']))
        story.append(Spacer(1,0.5*cm))
        
        # Info-Tabelle
        info=[
            ['Parameter','Wert'],
            ['Nennleistung',f"{c['P_nenn']:.0f} kW"],
            [r['v_ref_name'],f"{r['v_ref']:.2f} m/s"],
            ['Nabenhöhe',f"{nh:.0f} m"],
            ['Formel',r['formula']],
            [f"Bereich (NH {nh:.0f}m)",f"{r['v_low_NH']:.2f}–{r['v_high_NH']:.2f} m/s"],
            ['Bereich (10m)',f"{r['v_low_10m']:.2f}–{r['v_high_10m']:.2f} m/s"]
        ]
        it=Table(info,colWidths=[6*cm,8*cm])
        it.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(1,0),colors.HexColor('#1f4e79')),
            ('TEXTCOLOR',(0,0),(1,0),colors.whitesmoke),
            ('BACKGROUND',(0,5),(1,6),colors.HexColor('#d5edd9')),
            ('GRID',(0,0),(-1,-1),1,colors.grey)
        ]))
        story.append(it)
        story.append(Spacer(1,1*cm))
        
        # Daten-Tabelle
        td=[['v [m/s]','P [kW]','Im Bereich']]
        for vv,pp,mm in zip(v,P,m):
            td.append([f"{vv:.1f}",f"{pp:.0f}","✓"if mm else""])
        
        dt=Table(td,colWidths=[3*cm,3*cm,3*cm])
        dt.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(2,0),colors.HexColor('#27ae60')),
            ('TEXTCOLOR',(0,0),(2,0),colors.whitesmoke),
            ('GRID',(0,0),(-1,-1),0.5,colors.grey),
            ('FONTSIZE',(0,0),(-1,-1),8)
        ]))
        for i in range(1,len(td)):
            if m[i-1]:
                dt.setStyle(TableStyle([
                    ('BACKGROUND',(0,i),(2,i),colors.HexColor('#d5edd9'))
                ]))
        story.append(dt)
        story.append(Spacer(1,2*cm))
    
    doc.build(story)
    out.seek(0)
    return out

st.title("⚡ FGW/IEC3 Markierungs-Tool")
st.info("ℹ️ Vereinfachte Version ohne Diagramme (nur Tabellen)")
st.markdown("---")

st.header("1️⃣ PDF hochladen")
uploaded=st.file_uploader("PDF mit Leistungskurve(n)",type=['pdf'])

if uploaded:
    st.success(f"✓ {uploaded.name}")
    with st.spinner("🔍 Analysiere..."):
        curves=ext_curves(uploaded)
    if not curves:
        st.error("❌ Keine Kurven gefunden!");st.stop()
    
    st.header("2️⃣ Kurven auswählen")
    st.success(f"✓ {len(curves)} Kurve(n)")
    opts=[]
    for i,c in enumerate(curves):
        nh=f"{c['nabenhoehe_auto']:.0f}m"if c['nabenhoehe_auto']else"?m"
        opts.append(f"[{i+1}] {c['mode']} | NH {nh} | {len(c['v'])} Pkt")
    sel=st.multiselect("Kurven:",range(len(curves)),format_func=lambda x:opts[x],default=range(len(curves)))
    if not sel:st.warning("⚠️ Kurve auswählen!");st.stop()
    sel_c=[curves[i]for i in sel]
    
    st.header("3️⃣ Nabenhöhe")
    auto_nh=sel_c[0].get('nabenhoehe_auto')
    if auto_nh:st.info(f"✓ Erkannt: {auto_nh:.0f} m");dnh=int(auto_nh)
    else:st.warning("⚠️ Manuell eingeben");dnh=100
    nh=st.number_input("NH (m):",50,200,dnh,1)
    
    st.header("4️⃣ Standard")
    std=st.radio("",["FGW19","IEC3"],format_func=lambda x:"FGW TR 1 Rev. 19"if x=="FGW19"else"IEC 61400-1 Ed. 3")
    
    st.header("5️⃣ PDF erstellen")
    if st.button("🚀 PDF ERSTELLEN",type="primary",use_container_width=True):
        with st.spinner("⏳ Erstelle PDF..."):
            try:
                out=mk_pdf(sel_c,std,nh)
                fn=f"{uploaded.name.replace('.pdf','')}_{std}_NH{nh:.0f}m.pdf"
                st.success("✅ Fertig! (Tabellen-Version ohne Diagramme)")
                st.download_button("📥 DOWNLOAD",out,fn,"application/pdf",type="primary",use_container_width=True)
            except Exception as e:st.error(f"❌ {e}")
