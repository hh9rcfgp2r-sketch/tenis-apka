import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Tenis Pro Live 2026", page_icon="🎾", layout="centered")

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

st.title("🎾 Tenis Pro Live")
st.caption("Živý 6-pilierový model aktualizovaný v reálnom čase")

okruh = st.radio("Kategória:", ("ATP (Muži)", "WTA (Ženy)"), horizontal=True)

@st.cache_data(ttl=900)  # Obnovuje sa každých 15 minút!
def nacitaj_zive_data(kategoria):
    tour = "atp" if "ATP" in kategoria else "wta"
    zaznamy = list()
    dnesne_zapasy = list()

    # 1. Stiahnutie aktuálnej sezóny 2026 (TML živá databáza pre ATP)
    if tour == "atp":
        try:
            url_2026 = "https://raw.githubusercontent." + "com/Tennismylife/TML-Database/master/2026.csv"
            df_tml = pd.read_csv(url_2026, low_memory=False)
            for _, r in df_tml.iterrows():
                if pd.notna(r.get("winner_name")) and pd.notna(r.get("loser_name")):
                    zaznamy.append({
                        "datum": str(r.get("tourney_date", "20260101")),
                        "turnaj": str(r.get("tourney_name", "ATP")),
                        "surface": str(r.get("surface", "Hard")),
                        "winner": str(r["winner_name"]).strip(),
                        "loser": str(r["loser_name"]).strip(),
                        "w_rank": r.get("winner_rank", 200),
                        "l_rank": r.get("loser_rank", 200)
                    })
        except Exception:
            pass

    # 2. Živý minútový feed z ESPN API (posledných 25 dní + dnešné a budúce zápasy)
    dnes = datetime.utcnow()
    start_dt = (dnes - timedelta(days=25)).strftime("%Y%m%d")
    end_dt = (dnes + timedelta(days=2)).strftime("%Y%m%d")
    espn_url = f"https://api.espn." + f"com/apis/site/v2/sports/tennis/{tour}/scoreboard?dates={start_dt}-{end_dt}"

    try:
        resp = requests.get(espn_url, timeout=10).json()
        for event in resp.get("events", list()):
            turnaj_nazov = event.get("name", "Turnaj")
            for group in event.get("groupings", list()):
                if "Singles" not in group.get("grouping", {}).get("name", "Singles"):
                    continue
                for comp in group.get("competitions", list()):
                    status = comp.get("status", {}).get("type", {}).get("name", "")
                    datum_zapasu = comp.get("date", "")[:10].replace("-", "")
                    hraci_comp = comp.get("competitors", list())
                    if len(hraci_comp) != 2:
                        continue

                    p1_data, p2_data = hraci_comp[0], hraci_comp[1]
                    meno1 = p1_data.get("athlete", {}).get("displayName", "")
                    meno2 = p2_data.get("athlete", {}).get("displayName", "")
                    rank1 = p1_data.get("curatedRank", {}).get("current", 200)
                    rank2 = p2_data.get("curatedRank", {}).get("current", 200)

                    if not meno1 or not meno2:
                        continue

                    # Ak zápas ešte neskončil (dnešný/nadchádzajúci), pridáme do klikateľného zoznamu
                    if "FINAL" not in status.upper():
                        dnesne_zapasy.append({
                            "popis": f"{meno1} vs. {meno2} ({turnaj_nazov})",
                            "h1": meno1,
                            "h2": meno2,
                            "turnaj": turnaj_nazov
                        })
                    else:
                        # Dohraný zápas pridáme do živých výsledkov
                        if p1_data.get("winner"):
                            w, l, wr, lr = meno1, meno2, rank1, rank2
                        else:
                            w, l, wr, lr = meno2, meno1, rank2, rank1
                        zaznamy.append({
                            "datum": datum_zapasu,
                            "turnaj": turnaj_nazov,
                            "surface": "Hard",
                            "winner": w,
                            "loser": l,
                            "w_rank": wr,
                            "l_rank": lr
                        })
    except Exception:
        pass

    df = pd.DataFrame(zaznamy)
    if df.empty:
        return pd.DataFrame(), list(), dict(), dict(), dnesne_zapasy

    df = df.drop_duplicates(subset=["datum", "winner", "loser"]).sort_values("datum").reset_index(drop=True)

    # Výpočet aktuálneho Surface Elo zo sezóny 2026
    elo_surf = {"Hard": dict(), "Clay": dict(), "Grass": dict()}
    posledny_rank = dict()
    K = 32

    for _, r in df.iterrows():
        w, l, s = r["winner"], r["loser"], r["surface"]
        if pd.notna(r.get("w_rank")):
            posledny_rank[w] = int(r["w_rank"])
        if pd.notna(r.get("l_rank")):
            posledny_rank[l] = int(r["l_rank"])
        if s not in elo_surf:
            s = "Hard"

        rw = elo_surf[s].get(w, 1500)
        rl = elo_surf[s].get(l, 1500)
        ew = 1 / (1 + 10 ** ((rl - rw) / 400))
        elo_surf[s][w] = rw + K * (1 - ew)
        elo_surf[s][l] = rl + K * (0 - (1 - ew))

    vsetci_hraci = sorted(list(set(df["winner"]).union(set(df["loser"]))))
    return df, vsetci_hraci, elo_surf, posledny_rank, dnesne_zapasy

with st.spinner("Sťahujem živé výsledky z posledných minút a sezónu 2026..."):
    df, hraci, elo_surf, posledny_rank, dnesne_zapasy = nacitaj_zive_data(okruh)

if df.empty:
    st.error("Živý feed je momentálne nedostupný. Skúste obnoviť stránku.")
    st.stop()

najnovsi_datum = str(df["datum"].max())
st.success(f"🟢 Živé dáta aktívne | Najnovší zápas v systéme: **{najnovsi_datum[:4]}-{najnovsi_datum[4:6]}-{najnovsi_datum[6:]}** | Hráčov: **{len(hraci)}**")

# RÝCHLY VÝBER DNEŠNÉHO ZÁPASU JEDNÝM ŤUKNUTÍM
predvoleny_i1, predvoleny_i2 = 0, 1
if dnesne_zapasy:
    st.subheader("⚡ Dnešné / Najbližšie živé zápasy")
    moznosti = ["— Vyber z dnešných zápasov alebo zvoľ ručne nižšie —"] + [z["popis"] for z in dnesne_zapasy]
    vybrany_zapas = st.selectbox("Ťukni na zápas:", moznosti)
    for z in dnesne_zapasy:
        if z["popis"] == vybrany_zapas:
            if z["h1"] in hraci:
                predvoleny_i1 = hraci.index(z["h1"])
            if z["h2"] in hraci:
                predvoleny_i2 = hraci.index(z["h2"])

col1, col2 = st.columns(2)
with col1:
    h1 = st.selectbox("Hráč 1", hraci, index=predvoleny_i1)
with col2:
    h2 = st.selectbox("Hráč 2", hraci, index=predvoleny_i2)

col_p, col_t = st.columns(2)
with col_p:
    povrch = st.selectbox("Povrch:", ("Hard", "Clay", "Grass"))
with col_t:
    typ_turnaja = st.selectbox("Úroveň turnaja:", ("Grand Slam / Masters / Finals", "ATP/WTA 250-500", "Challenger / ITF"))

with st.expander("⚙️ Doplnkové podmienky (Domáce prostredie & Únava)"):
    domaci = st.radio("Kto hrá v domácom prostredí?", ("Nikto (neutrálne)", h1, h2), horizontal=True)
    unava_h1 = st.slider(f"Únava {h1} (ťažké zápasy za posledné dni)", 0, 10, 2)
    unava_h2 = st.slider(f"Únava {h2} (ťažké zápasy za posledné dni)", 0, 10, 2)

if h1 == h2:
    st.warning("Vyberte dvoch rôznych súperov.")
    st.stop()

# --- VÝPOČET 6 PILIEROV ---
e1 = elo_surf[povrch].get(h1, 1500)
e2 = elo_surf[povrch].get(h2, 1500)
p_elo1 = 1 / (1 + 10 ** ((e2 - e1) / 400))

z1 = df[(df["winner"] == h1) | (df["loser"] == h1)].tail(20)
z2 = df[(df["winner"] == h2) | (df["loser"] == h2)].tail(20)

def skore_formy(zapasy, meno):
    if zapasy.empty:
        return 0.5, list()
    vahy = np.linspace(0.5, 1.5, len(zapasy))
    body = 0
    historia = list()
    for (_, r), v in zip(zapasy.iterrows(), vahy):
        if r["winner"] == meno:
            body += v
            historia.append("Z")
        else:
            historia.append("P")
    return body / sum(vahy), historia

f1, hist1 = skore_formy(z1, h1)
f2, hist2 = skore_formy(z2, h2)
p_forma1 = f1 / (f1 + f2) if (f1 + f2) > 0 else 0.5

h2h = df[((df["winner"] == h1) & (df["loser"] == h2)) | ((df["winner"] == h2) & (df["loser"] == h1))]
w_h2h_1 = len(h2h[h2h["winner"] == h1])
w_h2h_2 = len(h2h[h2h["winner"] == h2])

superi1 = set(z1["winner"]).union(set(z1["loser"])) - {h1}
superi2 = set(z2["winner"]).union(set(z2["loser"])) - {h2}
spolocni = list(superi1.intersection(superi2))

spol_skore1, spol_skore2 = 0, 0
for s_meno in spolocni:
    spol_skore1 += len(z1[(z1["winner"] == h1) & (z1["loser"] == s_meno)])
    spol_skore2 += len(z2[(z2["winner"] == h2) & (z2["loser"] == s_meno)])

celk_h2h_1 = w_h2h_1 * 1.5 + spol_skore1 + 1
celk_h2h_2 = w_h2h_2 * 1.5 + spol_skore2 + 1
p_h2h1 = celk_h2h_1 / (celk_h2h_1 + celk_h2h_2)

p_unava1 = (11 - unava_h1) / ((11 - unava_h1) + (11 - unava_h2))

r1 = posledny_rank.get(h1, 200)
r2 = posledny_rank.get(h2, 200)

def index_motivacie(rank, historia, turnaj):
    mot = 1.0
    if rank > 100:
        mot += 0.35
    if historia[-3:].count("P") >= 2:
        mot += 0.25
    if rank <= 15 and turnaj != "Grand Slam / Masters / Finals":
        mot -= 0.20
    return max(0.3, mot)

m1 = index_motivacie(r1, hist1, typ_turnaja)
m2 = index_motivacie(r2, hist2, typ_turnaja)
p_mot1 = m1 / (m1 + m2)

p_dom1 = 0.65 if domaci == h1 else (0.35 if domaci == h2 else 0.50)

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


