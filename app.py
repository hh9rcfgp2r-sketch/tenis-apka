import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Tenis Pro Live 2026", page_icon="🎾", layout="centered")
st.title("🎾 Tenis Pro Live 2026")
okruh = st.radio("Kategória:", ("ATP (Muži)", "WTA (Ženy)"), horizontal=True)

@st.cache_data(ttl=900)
def nacitaj_data(kategoria):
    tour = "atp" if "ATP" in kategoria else "wta"
    zaznamy, dnesne, ranks = list(), list(), dict()
    arch = "https://raw.githubusercontent." + "com/Aneeshers/tennis-sackmann-archive/main/"
    for s in (f"{arch}{tour}/{tour}_matches_2023.csv", f"{arch}{tour}/{tour}_matches_2024.csv", f"{arch}{tour}/{tour}_matches_qual_chall_2024.csv"):
        try:
            for _, r in pd.read_csv(s, low_memory=False).iterrows():
                if pd.notna(r.get("winner_name")) and pd.notna(r.get("loser_name")):
                    zaznamy.append({"datum": str(r.get("tourney_date", "20240101"))[:8], "surface": str(r.get("surface", "Hard")), "winner": str(r["winner_name"]).strip(), "loser": str(r["loser_name"]).strip(), "w_rank": r.get("winner_rank", 300), "l_rank": r.get("loser_rank", 300), "score": str(r.get("score", ""))})
        except Exception: pass

    tml = "https://stats.tennismylife." + "org/data/"
    subory = [f"{tml}2025.csv", f"{tml}2026.csv", f"{tml}challenger_2026.csv", f"{tml}ongoing_tourneys.csv"] if tour == "atp" else [f"{tml}wta_2025.csv", f"{tml}wta_2026.csv", f"{tml}wta_challenger_2026.csv", f"{tml}wta_ongoing_tourneys.csv"]
    for s in subory:
        try:
            for _, r in pd.read_csv(s, low_memory=False).iterrows():
                if pd.notna(r.get("winner_name")) and pd.notna(r.get("loser_name")):
                    zaznamy.append({"datum": str(r.get("tourney_date", "20260101"))[:8], "surface": str(r.get("surface", "Hard")), "winner": str(r["winner_name"]).strip(), "loser": str(r["loser_name"]).strip(), "w_rank": r.get("winner_rank", 250), "l_rank": r.get("loser_rank", 250), "score": str(r.get("score", ""))})
        except Exception: pass

    espn = "https://api.espn." + f"com/apis/site/v2/sports/tennis/{tour}"
    try:
        for g in requests.get(f"{espn}/rankings", timeout=8).json().get("rankings", list()):
            for e in g.get("ranks", list()):
                m = e.get("athlete", {}).get("displayName", "").strip()
                if m: ranks[m] = int(e.get("current", 250))
    except Exception: pass

    dnes = datetime.utcnow()
    try:
        url_sc = f"{espn}/scoreboard?dates={(dnes - timedelta(days=20)).strftime('%Y%m%d')}-{(dnes + timedelta(days=2)).strftime('%Y%m%d')}"
        for ev in requests.get(url_sc, timeout=10).json().get("events", list()):
            trn = ev.get("name", "Turnaj")
            for gr in ev.get("groupings", list()):
                if "Singles" not in gr.get("grouping", {}).get("name", "Singles"): continue
                for cp in gr.get("competitions", list()):
                    st_name = cp.get("status", {}).get("type", {}).get("name", "")
                    dt_str = cp.get("date", "")[:10].replace("-", "")
                    comps = cp.get("competitors", list())
                    if len(comps) != 2: continue
                    m1, m2 = comps[0].get("athlete", {}).get("displayName", "").strip(), comps[1].get("athlete", {}).get("displayName", "").strip()
                    sc_txt = " ".join([f"{s1.get('value',0)}-{s2.get('value',0)}" for s1, s2 in zip(comps[0].get("linescores", list()), comps[1].get("linescores", list()))])
                    if not m1 or not m2: continue
                    if "FINAL" not in st_name.upper():
                        dnesne.append({"popis": f"{m1} vs. {m2} ({trn})", "h1": m1, "h2": m2})
                    else:
                        w, l = (m1, m2) if comps[0].get("winner") else (m2, m1)
                        zaznamy.append({"datum": dt_str, "surface": "Hard", "winner": w, "loser": l, "w_rank": 100, "l_rank": 100, "score": sc_txt})
    except Exception: pass

    df = pd.DataFrame(zaznamy)
    if df.empty: return pd.DataFrame(), list(), dict(), dict(), dnesne
    df = df.drop_duplicates(subset=["datum", "winner", "loser"]).sort_values("datum").reset_index(drop=True)
    elo = {"Hard": dict(), "Clay": dict(), "Grass": dict()}
    for _, r in df.iterrows():
        w, l, s = r["winner"], r["loser"], r["surface"] if r["surface"] in ("Hard", "Clay", "Grass") else "Hard"
        if pd.notna(r.get("w_rank")) and w not in ranks: ranks[w] = int(r["w_rank"])
        if pd.notna(r.get("l_rank")) and l not in ranks: ranks[l] = int(r["l_rank"])
        rw, rl = elo[s].get(w, 1500), elo[s].get(l, 1500)
        ew = 1 / (1 + 10 ** ((rl - rw) / 400))
        elo[s][w], elo[s][l] = rw + 32 * (1 - ew), rl + 32 * (0 - (1 - ew))
    return df, sorted(list(set(df["winner"]).union(set(df["loser"])).union(set(ranks.keys())))), elo, ranks, dnesne

with st.spinner("Načítavam živé dáta 2026..."):
    df, hraci, elo_surf, ranks, dnesne = nacitaj_data(okruh)

if df.empty:
    st.error("Chyba načítania dát.")
    st.stop()

st.success(f"🟢 Databáza: **{len(hraci)}** hráčov/hráčok | Dnešných zápasov: **{len(dnesne)}**")
i1 = hraci.index("Carlos Alcaraz") if "Carlos Alcaraz" in hraci else 0
i2 = hraci.index("Flavio Cobolli") if "Flavio Cobolli" in hraci else (1 if len(hraci) > 1 else 0)

if dnesne:
    vyber = st.selectbox("⚡ Dnešné živé zápasy:", ["— Vyber z dnešných zápasov —"] + [z["popis"] for z in dnesne])
    for z in dnesne:
        if z["popis"] == vyber:
            if z["h1"] in hraci: i1 = hraci.index(z["h1"])
            if z["h2"] in hraci: i2 = hraci.index(z["h2"])

c_a, c_b = st.columns(2)
h1 = c_a.selectbox("Hráč / Hráčka 1", hraci, index=i1)
h2 = c_b.selectbox("Hráč / Hráčka 2", hraci, index=i2)
c_p, c_t, c_d = st.columns(3)
povrch = c_p.selectbox("Povrch:", ("Hard", "Clay", "Grass"))
turnaj = c_t.selectbox("Turnaj:", ("Grand Slam / Masters / Finals", "ATP/WTA 250-500", "Challenger / ITF"))
domaci = c_d.selectbox("Domáci:", ("Nikto", h1, h2))

if h1 == h2:
    st.warning("Vyberte dvoch rôznych súperov.")
    st.stop()

e1, e2 = elo_surf[povrch].get(h1, 1500), elo_surf[povrch].get(h2, 1500)
p_elo = 1 / (1 + 10 ** ((e2 - e1) / 400))

z1 = df[(df["winner"] == h1) | (df["loser"] == h1)].tail(20)
z2 = df[(df["winner"] == h2) | (df["loser"] == h2)].tail(20)

def forma(zap, m):
    if zap.empty: return 0.5, list()
    vahy = np.linspace(0.5, 1.5, len(zap))
    b, h = 0, list()
    for (_, r), v in zip(zap.iterrows(), vahy):
        if r["winner"] == m: b += v; h.append("Z")
        else: h.append("P")
    return b / sum(vahy), h

f1, hist1 = forma(z1, h1)
f2, hist2 = forma(z2, h2)
p_forma = f1 / (f1 + f2) if (f1 + f2) > 0 else 0.5

h2h = df[((df["winner"] == h1) & (df["loser"] == h2)) | ((df["winner"] == h2) & (df["loser"] == h1))]
wh1, wh2 = len(h2h[h2h["winner"] == h1]), len(h2h[h2h["winner"] == h2])

spol = list((set(z1["winner"]).union(set(z1["loser"])) - {h1}).intersection(set(z2["winner"]).union(set(z2["loser"])) - {h2}))
s1 = sum(len(z1[(z1["winner"] == h1) & (z1["loser"] == s)]) for s in spol)
s2 = sum(len(z2[(z2["winner"] == h2) & (z2["loser"] == s)]) for s in spol)
p_h2h = (wh1 * 1.5 + s1 + 1) / (wh1 * 1.5 + s1 + wh2 * 1.5 + s2 + 2)

lim7 = (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d")
u1, u2 = len(z1[z1["datum"] >= lim7]), len(z2[z2["datum"] >= lim7])
p_unava = (10 - min(8, u1)) / ((10 - min(8, u1)) + (10 - min(8, u2)))

r1, r2 = ranks.get(h1, 250), ranks.get(h2, 250)
m1 = max(0.3, 1.0 + (0.35 if r1 > 100 else 0) + (0.25 if hist1[-3:].count("P") >= 2 else 0) - (0.20 if r1 <= 15 and turnaj != "Grand Slam / Masters / Finals" else 0))
m2 = max(0.3, 1.0 + (0.35 if r2 > 100 else 0) + (0.25 if hist2[-3:].count("P") >= 2 else 0) - (0.20 if r2 <= 15 and turnaj != "Grand Slam / Masters / Finals" else 0))
p_mot = m1 / (m1 + m2)
p_dom = 0.65 if domaci == h1 else (0.35 if domaci == h2 else 0.50)

def vykyvy(zap, m, wta):
    skr, neob, dtp = 0, 0, list()
    for _, r in zap.iterrows():
        if r["loser"] == m:
            if "RET" in str(r.get("score", "")).upper() or "W/O" in str(r.get("score", "")).upper(): skr += 1
            if float(r.get("w_rank", 150) or 150) > float(r.get("l_rank", 150) or 150) + 60: neob += 1
            try: dtp.append(datetime.strptime(str(r["datum"])[:8], "%Y%m%d"))
            except Exception: pass
    cyk = wta and len(dtp) > 0 and ((datetime.utcnow() - dtp[-1]).days % 28 in (0, 1, 2, 3, 25, 26, 27))
    return max(0.2, 1.0 - skr * 0.15 - neob * 0.10 - (0.25 if cyk else 0)), skr, neob, cyk

st1, skr1, np1, cyk1 = vykyvy(z1, h1, "WTA" in okruh)
st2, skr2, np2, cyk2 = vykyvy(z2, h2, "WTA" in okruh)
p_stab = st1 / (st1 + st2)

sanca1 = 0.25 * p_elo + 0.20 * p_forma + 0.15 * p_h2h + 0.15 * p_unava + 0.10 * p_mot + 0.10 * p_dom + 0.05 * p_stab
sanca2 = 1 - sanca1

st.divider()
if (r1 > r2 + 30 and sanca1 > 0.52) or (r2 > r1 + 30 and sanca2 > 0.52):
    st.error(f"⚠️ POZOR NA PREKVAPENIE: **{h1 if sanca1 > sanca2 else h2}** má podľa 7 pilierov navrch!")

col1, col2 = st.columns(2)
with col1:
    st.subheader(h1)
    st.caption(f"Rank: **#{r1}** | Elo: **{int(e1)}** | Zápasy 7d: **{u1}**")
    st.metric("Šanca na výhru", f"{sanca1*100:.1f} %", f"Férový kurz: {1/sanca1:.2f}")
with col2:
    st.subheader(h2)
    st.caption(f"Rank: **#{r2}** | Elo: **{int(e2)}** | Zápasy 7d: **{u2}**")
    st.metric("Šanca na výhru", f"{sanca2*100:.1f} %", f"Férový kurz: {1/sanca2:.2f}")

st.progress(float(sanca1))
st.divider()

st.subheader("📊 Posledných 20 zápasov & Skóre")
st.write(f"**{h1}** ({hist1.count('Z')}W - {hist1.count('P')}L): " + " ".join(hist1))
st.write(f"**{h2}** ({hist2.count('Z')}W - {hist2.count('P')}L): " + " ".join(hist2))
with st.expander("📋 Detailný rozpis posledných 20 zápasov so skóre"):
    c_z1, c_z2 = st.columns(2)
    with c_z1:
        st.write(f"**{h1}:**")
        for _, r in z1.iloc[::-1].iterrows():
            vys = "✅" if r["winner"] == h1 else "❌"






