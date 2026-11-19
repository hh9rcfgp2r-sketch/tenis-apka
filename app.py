import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Tenis Pro Analytics", page_icon="🎾", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    .card {
        background-color: #1a1f2c;
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 14px;
        border: 1px solid #2d3548;
    }
    .upset-badge {
        background-color: #ff4b4b22;
        border: 1px solid #ff4b4b;
        color: #ff6b6b;
        padding: 8px 12px;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 12px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎾 Tenis Pro Analytics")
st.caption("Nezávislý 6-pilierový model pre ATP & WTA")

okruh = st.radio("Kategória:", ("ATP (Muži)", "WTA (Ženy)"), horizontal=True)

@st.cache_data(ttl=86400)
def nacitaj_databazu(kategoria):
    prefix = "atp" if "ATP" in kategoria else "wta"
    roky = (2023, 2024, 2025, 2026)
    stlpce = (
        "tourney_date", "tourney_name", "surface", "tourney_level",
        "winner_name", "winner_ioc", "winner_rank",
        "loser_name", "loser_ioc", "loser_rank", "score"
    )
    dfs = list()
    baza = "https://githubusercontent.com_"
    for rok in roky:
        url = f"{baza}{prefix}/master/{prefix}_matches_{rok}.csv"
        try:
            df_rok = pd.read_csv(url, usecols=lambda c: c in stlpce)
            dfs.append(df_rok)
        except Exception:
            pass

    if not dfs:
        return pd.DataFrame(), list(), dict(), dict(), dict()

    df = pd.concat(dfs, ignore_index=True).dropna(subset=("winner_name", "loser_name", "surface"))
    df = df.sort_values("tourney_date").reset_index(drop=True)

    elo_surf = {"Hard": dict(), "Clay": dict(), "Grass": dict()}
    posledny_rank = dict()
    krajina_hraca = dict()
    K = 32

    for _, r in df.iterrows():
        w, l, s = r["winner_name"], r["loser_name"], r["surface"]
        if pd.notna(r.get("winner_rank")):
            posledny_rank[w] = int(r["winner_rank"])
        if pd.notna(r.get("loser_rank")):
            posledny_rank[l] = int(r["loser_rank"])
        if pd.notna(r.get("winner_ioc")):
            krajina_hraca[w] = r["winner_ioc"]
        if pd.notna(r.get("loser_ioc")):
            krajina_hraca[l] = r["loser_ioc"]

        if s in elo_surf:
            rw = elo_surf[s].get(w, 1500)
            rl = elo_surf[s].get(l, 1500)
            ew = 1 / (1 + 10 ** ((rl - rw) / 400))
            elo_surf[s][w] = rw + K * (1 - ew)
            elo_surf[s][l] = rl + K * (0 - (1 - ew))

    hraci = sorted(list(set(df["winner_name"]).union(set(df["loser_name"]))))
    return df, hraci, elo_surf, posledny_rank, krajina_hraca

with st.spinner("Načítavam tisíce hráčov a štatistiky..."):
    df, hraci, elo_surf, posledny_rank, krajina_hraca = nacitaj_databazu(okruh)

if df.empty:
    st.error("Nepodarilo sa načítať databázu. Skontrolujte pripojenie.")
    st.stop()

st.caption(f"V databáze aktívnych: **{len(hraci)}** hráčov/hráčok")

col1, col2 = st.columns(2)
with col1:
    h1 = st.selectbox("Hráč 1", hraci, index=0)
with col2:
    h2 = st.selectbox("Hráč 2", hraci, index=1 if len(hraci) > 1 else 0)

col_p, col_t = st.columns(2)
with col_p:
    povrch = st.selectbox("Povrch:", ("Hard", "Clay", "Grass"))
with col_t:
    typ_turnaja = st.selectbox("Úroveň turnaja:", ("Grand Slam / Masters", "ATP/WTA 250-500", "Challenger / ITF"))

with st.expander("⚙️ Doplnkové podmienky (Domáce prostredie & Únava)"):
    domaci = st.radio("Kto hrá v domácom prostredí?", ("Nikto (neutrálne)", h1, h2), horizontal=True)
    unava_h1 = st.slider(f"Únava {h1} (ťažké zápasy za posledné dni)", 0, 10, 2)
    unava_h2 = st.slider(f"Únava {h2} (ťažké zápasy za posledné dni)", 0, 10, 2)

if h1 == h2:
    st.warning("Vyberte dvoch rôznych súperov.")
    st.stop()

# 1. Surface Elo (25 %)
e1 = elo_surf[povrch].get(h1, 1500)
e2 = elo_surf[povrch].get(h2, 1500)
p_elo1 = 1 / (1 + 10 ** ((e2 - e1) / 400))

# 2. Forma z posledných 20 zápasov (25 %)
z1 = df[(df["winner_name"] == h1) | (df["loser_name"] == h1)].tail(20)
z2 = df[(df["winner_name"] == h2) | (df["loser_name"] == h2)].tail(20)

def skore_formy(zapasy, meno):
    if zapasy.empty:
        return 0.5, list()
    vahy = np.linspace(0.5, 1.5, len(zapasy))
    body = 0
    historia = list()
    for (_, r), v in zip(zapasy.iterrows(), vahy):
        if r["winner_name"] == meno:
            body += v
            historia.append("Z")
        else:
            historia.append("P")
    return body / sum(vahy), historia

f1, hist1 = skore_formy(z1, h1)
f2, hist2 = skore_formy(z2, h2)
p_forma1 = f1 / (f1 + f2) if (f1 + f2) > 0 else 0.5

# 3. Vzájomné zápasy H2H + Spoloční súperi (15 %)
h2h = df[((df["winner_name"] == h1) & (df["loser_name"] == h2)) |
         ((df["winner_name"] == h2) & (df["loser_name"] == h1))]
w_h2h_1 = len(h2h[h2h["winner_name"] == h1])
w_h2h_2 = len(h2h[h2h["winner_name"] == h2])

superi1 = set(z1["winner_name"]).union(set(z1["loser_name"])) - {h1}
superi2 = set(z2["winner_name"]).union(set(z2["loser_name"])) - {h2}
spolocni = list(superi1.intersection(superi2))

spol_skore1, spol_skore2 = 0, 0
for s_meno in spolocni:
    v1 = len(z1[(z1["winner_name"] == h1) & (z1["loser_name"] == s_meno)])
    v2 = len(z2[(z2["winner_name"] == h2) & (z2["loser_name"] == s_meno)])
    spol_skore1 += v1
    spol_skore2 += v2

celk_h2h_1 = w_h2h_1 * 1.5 + spol_skore1 + 1
celk_h2h_2 = w_h2h_2 * 1.5 + spol_skore2 + 1
p_h2h1 = celk_h2h_1 / (celk_h2h_1 + celk_h2h_2)

# 4. Únavnosť (15 %)
p_unava1 = (11 - unava_h1) / ((11 - unava_h1) + (11 - unava_h2))

# 5. Finančná a rebríčková motivácia (10 %)
r1 = posledny_rank.get(h1, 250)
r2 = posledny_rank.get(h2, 250)

def index_motivacie(rank, historia, turnaj):
    mot = 1.0
    if rank > 100:
        mot += 0.35
    if historia[-3:].count("P") >= 2:
        mot += 0.25
    if rank <= 15 and turnaj != "Grand Slam / Masters":
        mot -= 0.20
    return max(0.3, mot)

m1 = index_motivacie(r1, hist1, typ_turnaja)
m2 = index_motivacie(r2, hist2, typ_turnaja)
p_mot1 = m1 / (m1 + m2)

# 6. Domáce prostredie (10 %)
if domaci == h1:
    p_dom1 = 0.65
elif domaci == h2:
    p_dom1 = 0.35
else:
    p_dom1 = 0.50

# FINÁLNY VÁŽENÝ SÚČET (100 %)
sanca1 = (
    0.25 * p_elo1 +
    0.25 * p_forma1 +
    0.15 * p_h2h1 +
    0.15 * p_unava1 +
    0.10 * p_mot1 +
    0.10 * p_dom1
)
sanca2 = 1 - sanca1

st.markdown("---")

if (r1 > r2 + 30 and sanca1 > 0.52) or (r2 > r1 + 30 and sanca2 > 0.52):
    meno_prekvapenia = h1 if sanca1 > sanca2 else h2
    st.markdown(f'<div class="upset-badge">⚠️ POZOR NA PREKVAPENIE: {meno_prekvapenia} má podľa 6 pilierov navrch aj napriek horšiemu rebríčku!</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    st.markdown(f"""
    <div class="card">
        <h4>{h1}</h4>
        <p>Rebríček: <b>#{r1}</b> | {povrch} Elo: <b>{int(e1)}</b></p>
        <h2 style="color:#00e676;">{sanca1*100:.1f} %</h2>
        <p>Férový kurz: <b>{1/sanca1:.2f}</b></p>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="card">
        <h4>{h2}</h4>
        <p>Rebríček: <b>#{r2}</b> | {povrch} Elo: <b>{int(e2)}</b></p>
        <h2 style="color:#4da6ff;">{sanca2*100:.1f} %</h2>
        <p>Férový kurz: <b>{1/sanca2:.2f}</b></p>
    </div>
    """, unsafe_allow_html=True)

st.progress(float(sanca1))

st.subheader("📊 Forma (posledných 20 zápasov)")
st.write(f"**{h1}** ({hist1.count('Z')}W - {hist1.count('P')}L): " + " ".join(hist1))
st.write(f"**{h2}** ({hist2.count('Z')}W - {hist2.count('P')}L): " + " ".join(hist2))

st.subheader("🔄 Vzájomné zápasy & Spoloční súperi")
st.write(f"**Priama bilancia (H2H):** {h1} **{w_h2h_1} : {w_h2h_2}** {h2}")

if spolocni:
    st.write(f"**Spoloční súperi z posledných 20 zápasov ({len(spolocni)}):**")
    for s_meno in spolocni[:6]:
        v1_text = "Výhra" if len(z1[(z1["winner_name"] == h1) & (z1["loser_name"] == s_meno)]) > 0 else "Prehra"
        v2_text = "Výhra" if len(z2[(z2["winner_name"] == h2) & (z2["loser_name"] == s_meno)]) > 0 else "Prehra"
        st.write(f"• vs. **{s_meno}** → {h1}: *{v1_text}* | {h2}: *{v2_text}*")
else:
    st.caption("V posledných 20 zápasoch nemali spoločného súpera.")
