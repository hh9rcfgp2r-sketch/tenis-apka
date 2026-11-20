import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Tenis Pro Live 2026", page_icon="🎾", layout="centered")

st.title("🎾 Tenis Pro Live 2026")
st.caption("Živý 7-pilierový analytický model (ATP & WTA)")

okruh = st.radio("Vyber kategóriu:", ("ATP (Muži)", "WTA (Ženy)"), horizontal=True)

@st.cache_data(ttl=900)
def nacitaj_kompletnu_databazu(kategoria):
    tour = "atp" if "ATP" in kategoria else "wta"
    zaznamy = list()
    dnesne_zapasy = list()
    posledny_rank = dict()

    # 1. Načítanie širokej databázy tisícok hráčov (ATP/WTA + Challengers)
    arch_base = "https://raw.githubusercontent." + "com/Aneeshers/tennis-sackmann-archive/main/"
    arch_subory = (
        f"{arch_base}{tour}/{tour}_matches_2023.csv",
        f"{arch_base}{tour}/{tour}_matches_2024.csv",
        f"{arch_base}{tour}/{tour}_matches_qual_chall_2023.csv",
        f"{arch_base}{tour}/{tour}_matches_qual_chall_2024.csv"
    )
    for url in arch_subory:
        try:
            df_a = pd.read_csv(url, low_memory=False)
            for _, r in df_a.iterrows():
                w, l = r.get("winner_name"), r.get("loser_name")
                if pd.notna(w) and pd.notna(l):
                    zaznamy.append({
                        "datum": str(r.get("tourney_date", "20240101")).replace(".0", ""),
                        "surface": str(r.get("surface", "Hard")),
                        "winner": str(w).strip(),
                        "loser": str(l).strip(),
                        "w_rank": r.get("winner_rank", 300),
                        "l_rank": r.get("loser_rank", 300),
                        "score": str(r.get("score", ""))
                    })
        except Exception:
            pass

    # 2. Živá databáza sezóny 2025 & 2026 + prebiehajúce turnaje (TennisMyLife)
    tml_base = "https://stats.tennismylife." + "org"
    tml_subory = list()
    if tour == "atp":
        tml_subory = [
            f"{tml_base}/data/2025.csv",
            f"{tml_base}/data/2026.csv",
            f"{tml_base}/data/challenger_2025.csv",
            f"{tml_base}/data/challenger_2026.csv",
            f"{tml_base}/data/ongoing_tourneys.csv"
        ]
    else:
        tml_subory = [
            f"{tml_base}/data/wta_2025.csv",
            f"{tml_base}/data/wta_2026.csv",
            f"{tml_base}/data/wta_challenger_2026.csv",
            f"{tml_base}/data/wta_ongoing_tourneys.csv"
        ]

    for url in tml_subory:
        try:
            df_t = pd.read_csv(url, low_memory=False)
            for _, r in df_t.iterrows():
                w, l = r.get("winner_name"), r.get("loser_name")
                if pd.notna(w) and pd.notna(l):
                    zaznamy.append({
                        "datum": str(r.get("tourney_date", "20260101")).replace(".0", ""),
                        "surface": str(r.get("surface", "Hard")),
                        "winner": str(w).strip(),
                        "loser": str(l).strip(),
                        "w_rank": r.get("winner_rank", 250),
                        "l_rank": r.get("loser_rank", 250),
                        "score": str(r.get("score", ""))
                    })
        except Exception:
            pass

    # 3. Živý minútový feed z ESPN (aktuálny rebríček + posledné dni + dnešné zápasy)
    espn_base = "https://api.espn." + f"com/apis/site/v2/sports/tennis/{tour}"
    try:
        rk_resp = requests.get(f"{espn_base}/rankings", timeout=8).json()
        for rk_group in rk_resp.get("rankings", list()):
            for entry in rk_group.get("ranks", list()):
                meno = entry.get("athlete", {}).get("displayName", "").strip()
                if meno:
                    posledny_rank[meno] = int(entry.get("current", 250))
    except Exception:
        pass

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
                    if not meno1 or not meno2:
                        continue
                    if "FINAL" not in status.upper():
                        dnesne_zapasy.append({"popis": f"{meno1} vs. {meno2} ({turnaj_nazov})", "h1": meno1, "h2": meno2})
                    else:
                        w, l = (meno1, meno2) if p1_data.get("winner") else (meno2, meno1)
                        zaznamy.append({"datum": datum_zapasu, "surface": "Hard", "winner": w, "loser": l, "w_rank": 100, "l_rank": 100, "score": ""})
    except Exception:
        pass

    df = pd.DataFrame(zaznamy)
    if df.empty:
        return pd.DataFrame(), list(), dict(), dict(), dnesne_zapasy

    df = df.drop_duplicates(subset=["datum", "winner", "loser"]).sort_values("datum").reset_index(drop=True)

    elo_surf = {"Hard": dict(), "Clay": dict(), "Grass": dict()}
    for _, r in df.iterrows():
        w, l, s = r["winner"], r["loser"], r["surface"]
        if pd.notna(r.get("w_rank")) and w not in posledny_rank:
            posledny_rank[w] = int(r["w_rank"])
        if pd.notna(r.get("l_rank")) and l not in posledny_rank:
            posledny_rank[l] = int(r["l_rank"])
        if s not in elo_surf:
            s = "Hard"
        rw, rl = elo_surf[s].get(w, 1500), elo_surf[s].get(l, 1500)
        ew = 1 / (1 + 10 ** ((rl - rw) / 400))
        elo_surf[s][w] = rw + 32 * (1 - ew)
        elo_surf[s][l] = rl + 32 * (0 - (1 - ew))

    vsetci_hraci = sorted(list(set(df["winner"]).union(set(df["loser"])).union(set(posledny_rank.keys()))))
    return df, vsetci_hraci, elo_surf, posledny_rank, dnesne_zapasy

with st.spinner("Načítavam tisíce hráčov a živé dáta 2026..."):
    df, hraci, elo_surf, posledny_rank, dnesne_zapasy = nacitaj_kompletnu_databazu(okruh)

if df.empty:
    st.error("Nepodarilo sa načítať databázu. Skúste obnoviť stránku.")
    st.stop()

najnovsi_datum = str(df["datum"].max())
st.success(f"🟢 Databáza: **{len(hraci)}** hráčov/hráčok | Najnovšie dáta: **{najnovsi_datum[:4]}-{najnovsi_datum[4:6]}-{najnovsi_datum[6:]}**")

# RÝCHLY VÝBER DNEŠNÉHO ZÁPASU
i1 = hraci.index("Carlos Alcaraz") if "Carlos Alcaraz" in hraci else 0
i2 = hraci.index("Flavio Cobolli") if "Flavio Cobolli" in hraci else (1 if len(hraci) > 1 else 0)

if dnesne_zapasy:
    moznosti = ["— Vyber z dnešných živých zápasov —"] + [z["popis"] for z in dnesne_zapasy]
    vyber = st.selectbox("⚡ Dnešné živé zápasy (ťukni pre výber):", moznosti)
    for z in dnesne_zapasy:
        if z["popis"] == vyber:
            if z["h1"] in hraci: i1 = hraci.index(z["h1"])
            if z["h2"] in hraci: i2 = hraci.index(z["h2"])

col1, col2 = st.columns(2)
with col1:
    h1 = st.selectbox("Hráč / Hráčka 1", hraci, index=i1)
with col2:
    h2 = st.selectbox("Hráč / Hráčka 2", hraci, index=i2)

col_p, col_t = st.columns(2)
with col_p:
    povrch = st.selectbox("Povrch:", ("Hard", "Clay", "Grass"))
with col_t:
    typ_turnaja = st.selectbox("Úroveň turnaja:", ("Grand Slam / Masters / Finals", "ATP/WTA 250-500", "Challenger / ITF"))

with st.expander("⚙️ Doplnkové podmienky (Domáci, Únava, Zdravie/Cyklus)"):
    domaci = st.radio("Kto hrá v domácom prostredí?", ("Nikto", h1, h2), horizontal=True)
    unava_h1 = st.slider(f"Únava / Zdravotný hendikep: {h1}", 0, 10, 2)
    unava_h2 = st.slider(f"Únava / Zdravotný hendikep: {h2}", 0, 10, 2)

if h1 == h2:
    st.warning("Vyberte dvoch rôznych súperov.")
    st.stop()

# 1. Surface Elo (25 %)
e1, e2 = elo_surf[povrch].get(h1, 1500), elo_surf[povrch].get(h2, 1500)
p_elo1 = 1 / (1 + 10 ** ((e2 - e1) / 400))

# 2. Forma z posledných 20 zápasov (20 %)
z1 = df[(df["winner"] == h1) | (df["loser"] == h1)].tail(20)
z2 = df[(df["winner"] == h2) | (df["loser"] == h2)].tail(20)

def skore_formy(zapasy, meno):
    if zapasy.empty: return 0.5, list()
    vahy = np.linspace(0.5, 1.5, len(zapasy))
    body, hist = 0, list()
    for (_, r), v in zip(zapasy.iterrows(), vahy):
        if r["winner"] == meno:
            body += v
            hist.append("Z")
        else:
            hist.append("P")
    return body / sum(vahy), hist

f1, hist1 = skore_formy(z1, h1)
f2, hist2 = skore_formy(z2, h2)
p_forma1 = f1 / (f1 + f2) if (f1 + f2) > 0 else 0.5

# 3. Vzájomné zápasy H2H + Spoloční súperi z posledných 20 zápasov (15 %)
h2h = df[((df["winner"] == h1) & (df["loser"] == h2)) | ((df["winner"] == h2) & (df["loser"] == h1))]
w_h2h_1, w_h2h_2 = len(h2h[h2h["winner"] == h1]), len(h2h[h2h["winner"] == h2])

spolocni = list((set(z1["winner"]).union(set(z1["loser"])) - {h1}).intersection(set(z2["winner"]).union(set(z2["loser"])) - {h2}))
spol1 = sum(len(z1[(z1["winner"] == h1) & (z1["loser"] == s)]) for s in spolocni)
spol2 = sum(len(z2[(z2["winner"] == h2) & (z2["loser"] == s)]) for s in spolocni)
p_h2h1 = (w_h2h_1 * 1.5 + spol1 + 1) / (w_h2h_1 * 1.5 + spol1 + w_h2h_2 * 1.5 + spol2 + 2)

# 4. Únavnosť (15 %)
p_unava1 = (11 - unava_h1) / ((11 - unava_h1) + (11 - unava_h2))

# 5. Finančná a rebríčková motivácia (10 %)




