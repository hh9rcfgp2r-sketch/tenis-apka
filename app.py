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

st.title("🎾 Tenis Pro Live 2026")
st.caption("Živý 6-pilierový model pre ATP, WTA & Challengers")

okruh = st.radio("Kategória:", ("ATP (Muži)", "WTA (Ženy)"), horizontal=True)

@st.cache_data(ttl=900)
def nacitaj_zive_data(kategoria):
    tour = "atp" if "ATP" in kategoria else "wta"
    zaznamy = list()
    dnesne_zapasy = list()
    posledny_rank = dict()

    # 1. Živá databáza TennisMyLife (2025 + 2026 + Challengers + prebiehajúce turnaje)
    tml_base = "https://stats.tennismylife." + "org"
    csv_odkazy = list()
    try:
        api_files = requests.get(f"{tml_base}/api/data-files", timeout=8).json()
        for item in api_files:
            nazov = str(item.get("name", "") if isinstance(item, dict) else item)
            cesta = str(item.get("url", nazov) if isinstance(item, dict) else item)
            if not cesta.startswith("http"):
                cesta = f"{tml_base}/data/{cesta.lstrip('/')}"
            if tour == "atp" and ("2025" in nazov or "2026" in nazov or "ongoing" in nazov.lower()):
                if "wta" not in nazov.lower():
                    csv_odkazy.append(cesta)
            elif tour == "wta" and "wta" in nazov.lower() and ("2025" in nazov or "2026" in nazov or "ongoing" in nazov.lower()):
                csv_odkazy.append(cesta)
    except Exception:
        pass

    # Záložné priame odkazy na 2026 a prebiehajúce turnaje
    if not csv_odkazy:
        if tour == "atp":
            csv_odkazy = [
                f"{tml_base}/data/2025.csv",
                f"{tml_base}/data/2026.csv",
                f"{tml_base}/data/challenger_2026.csv",
                f"{tml_base}/data/ongoing_tourneys.csv"
            ]
        else:
            csv_odkazy = [
                f"{tml_base}/data/wta_2025.csv",
                f"{tml_base}/data/wta_2026.csv",
                f"{tml_base}/data/wta_ongoing_tourneys.csv"
            ]

    for url in set(csv_odkazy):
        try:
            df_part = pd.read_csv(url, low_memory=False)
            for _, r in df_part.iterrows():
                w = r.get("winner_name")
                l = r.get("loser_name")
                if pd.notna(w) and pd.notna(l):
                    zaznamy.append({
                        "datum": str(r.get("tourney_date", "20260101")).replace(".0", ""),
                        "turnaj": str(r.get("tourney_name", tour.upper())),
                        "surface": str(r.get("surface", "Hard")),
                        "winner": str(w).strip(),
                        "loser": str(l).strip(),
                        "w_rank": r.get("winner_rank", 250),
                        "l_rank": r.get("loser_rank", 250)
                    })
        except Exception:
            pass

    # 2. Aktuálny rebríček z ESPN (zaručí prítomnosť všetkých top hráčov vrátane Alcaraza)
    espn_base = "https://api.espn." + f"com/apis/site/v2/sports/tennis/{tour}"
    try:
        rk_resp = requests.get(f"{espn_base}/rankings", timeout=8).json()
        for rk_group in rk_resp.get("rankings", list()):
            for entry in rk_group.get("ranks", list()):
                meno = entry.get("athlete", {}).get("displayName", "")
                poz = entry.get("current", 250)
                if meno:
                    posledny_rank[meno] = int(poz)
    except Exception:
        pass

    # 3. Živý minútový feed z ESPN (posledných 20 dní + dnešné a zajtrajšie zápasy)
    dnes = datetime.utcnow()
    start_dt = (dnes - timedelta(days=20)).strftime("%Y%m%d")
    end_dt = (dnes + timedelta(days=2)).strftime("%Y%m%d")
    try:
        resp = requests.get(f"{espn_base}/scoreboard?dates={start_dt}-{end_dt}", timeout=10).json()
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

                    p1_data, p2_data = hraci_comp
                    meno1 = p1_data.get("athlete", {}).get("displayName", "").strip()
                    meno2 = p2_data.get("athlete", {}).get("displayName", "").strip()
                    rank1 = p1_data.get("curatedRank", {}).get("current", 250)
                    rank2 = p2_data.get("curatedRank", {}).get("current", 250)

                    if not meno1 or not meno2:
                        continue

                    if "FINAL" not in status.upper():
                        dnesne_zapasy.append({
                            "popis": f"{meno1} vs. {meno2} ({turnaj_nazov})",
                            "h1": meno1,
                            "h2": meno2
                        })
                    else:
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

    elo_surf = {"Hard": dict(), "Clay": dict(), "Grass": dict()}
    K = 32

    for _, r in df.iterrows():
        w, l, s = r["winner"], r["loser"], r["surface"]
        if pd.notna(r.get("w_rank")) and w not in posledny_rank:
            posledny_rank[w] = int(r["w_rank"])
        if pd.notna(r.get("l_rank")) and l not in posledny_rank:
            posledny_rank[l] = int(r["l_rank"])
        if s not in elo_surf:
            s = "Hard"

        rw = elo_surf[s].get(w, 1500)
        rl = elo_surf[s].get(l, 1500)
        ew = 1 / (1 + 10 ** ((rl - rw) / 400))
        elo_surf[s][w] = rw + K * (1 - ew)
        elo_surf[s][l] = rl + K * (0 - (1 - ew))

    vsetci_hraci = sorted(list(set(df["winner"]).union(set(df["loser"])).union(set(posledny_rank.keys()))))
    return df, vsetci_hraci, elo_surf, posledny_rank, dnesne_zapasy

with st.spinner("Sťahujem živé výsledky 2026 a dnešné zápasy..."):
    df, hraci, elo_surf, posledny_rank, dnesne_zapasy = nacitaj_zive_data(okruh)

if df.empty:
    st.error("Živý feed je momentálne nedostupný. Skúste obnoviť stránku.")
    st.stop()

najnovsi_datum = str(df["datum"].max())
st.success(f"🟢 Živé dáta 2026 aktívne | Najnovší zápas: **{najnovsi_datum[:4]}-{najnovsi_datum[4:6]}-{najnovsi_datum[6:]}** | Hráčov: **{len(hraci)}**")

# RÝCHLY VÝBER DNEŠNÉHO ZÁPASU
predvoleny_i1 = hraci.index("Carlos Alcaraz") if "Carlos Alcaraz" in hraci else 0
predvoleny_i2 = hraci.index("Flavio Cobolli") if "Flavio Cobolli" in hraci else (1 if len(hraci) > 1 else 0)

if dnesne_zapasy:
    st.subheader("⚡ Dnešné / Najbližšie živé zápasy")
    moznosti = ["— Vyber z dnešných zápasov alebo zvoľ nižšie —"] + [z["popis"] for z in dnesne_zapasy]
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



