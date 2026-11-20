import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Tenis Pro Live 2026", page_icon="🎾", layout="centered")
st.title("🎾 Tenis Pro Live 2026")
okruh = st.radio("Kategoria:", ("ATP (Muzi)", "WTA (Zeny)"), horizontal=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}

@st.cache_data(ttl=600)
def nacitaj_data(kategoria):
    tour = "atp" if "ATP" in kategoria else "wta"
    zaznamy = list()
    dnesne = list()
    ranks = dict()

    arch = "https://raw.githubusercontent." + "com/Aneeshers/tennis-sackmann-archive/main/"
    subory_arch = (
        f"{arch}{tour}/{tour}_matches_2024.csv",
        f"{arch}{tour}/{tour}_matches_qual_chall_2024.csv"
    )
    for s in subory_arch:
        try:
            df_a = pd.read_csv(s, low_memory=False)
            for _, r in df_a.iterrows():
                if pd.notna(r.get("winner_name")) and pd.notna(r.get("loser_name")):
                    zaznamy.append({
                        "datum": str(r.get("tourney_date", "20240101"))[:8],
                        "surface": str(r.get("surface", "Hard")),
                        "winner": str(r["winner_name"]).strip(),
                        "loser": str(r["loser_name"]).strip(),
                        "w_rank": r.get("winner_rank", 300),
                        "l_rank": r.get("loser_rank", 300),
                        "score": str(r.get("score", ""))
                    })
        except Exception:
            pass

    tml_urls = list()
    try:
        files = requests.get("https://stats.tennismylife." + "org/api/data-files", headers=HEADERS, timeout=10).json()
        for f in files:
            name = str(f.get("name", "") if isinstance(f, dict) else f)
            link = str(f.get("url", "") if isinstance(f, dict) else f)
            if not link.startswith("http"):
                link = "https://stats.tennismylife." + "org/data/" + name.lstrip("/")
            low = name.lower()
            if ("2025" in low or "2026" in low or "ongoing" in low) and low.endswith(".csv"):
                if tour == "atp" and "wta" not in low:
                    tml_urls.append(link)
                elif tour == "wta" and "wta" in low:
                    tml_urls.append(link)
    except Exception:
        pass

    for u in set(tml_urls):
        try:
            df_t = pd.read_csv(u, low_memory=False)
            for _, r in df_t.iterrows():
                if pd.notna(r.get("winner_name")) and pd.notna(r.get("loser_name")):
                    zaznamy.append({
                        "datum": str(r.get("tourney_date", "20260101")).replace(".0", "")[:8],
                        "surface": str(r.get("surface", "Hard")),
                        "winner": str(r["winner_name"]).strip(),
                        "loser": str(r["loser_name"]).strip(),
                        "w_rank": r.get("winner_rank", 250),
                        "l_rank": r.get("loser_rank", 250),
                        "score": str(r.get("score", ""))
                    })
        except Exception:
            pass

    espn = "https://api.espn." + f"com/apis/site/v2/sports/tennis/{tour}"
    try:
        rk_json = requests.get(f"{espn}/rankings", headers=HEADERS, timeout=8).json()
        for g in rk_json.get("rankings", list()):
            for e in g.get("ranks", list()):
                m = e.get("athlete", {}).get("displayName", "").strip()
                if m:
                    ranks[m] = int(e.get("current", 250))
    except Exception:
        pass

    dnes = datetime.utcnow()
    for krok in range(0, 120, 30):
        od_dt = (dnes - timedelta(days=krok + 30)).strftime("%Y%m%d")
        do_dt = (dnes - timedelta(days=krok - 2 if krok == 0 else krok)).strftime("%Y%m%d")
        try:
            sc_json = requests.get(f"{espn}/scoreboard?dates={od_dt}-{do_dt}", headers=HEADERS, timeout=10).json()
            for ev in sc_json.get("events", list()):
                trn = ev.get("name", "Turnaj")
                for gr in ev.get("groupings", list()):
                    if "Singles" not in gr.get("grouping", {}).get("name", "Singles"):
                        continue
                    for cp in gr.get("competitions", list()):
                        st_name = cp.get("status", {}).get("type", {}).get("name", "")
                        dt_str = cp.get("date", "")[:10].replace("-", "")
                        comps = cp.get("competitors", list())
                        if len(comps) != 2:
                            continue
                        c0 = comps.pop(0)
                        c1 = comps.pop(0)
                        m1 = c0.get("athlete", {}).get("displayName", "").strip()
                        m2 = c1.get("athlete", {}).get("displayName", "").strip()
                        ls1 = list(str(x.get("value", 0)) for x in c0.get("linescores", list()))
                        ls2 = list(str(x.get("value", 0)) for x in c1.get("linescores", list()))
                        sc_txt = " ".join(list(f"{a}-{b}" for a, b in zip(ls1, ls2)))
                        if not m1 or not m2:
                            continue
                        if "FINAL" not in st_name.upper():
                            if krok == 0:
                                dnesne.append({"popis": f"{m1} vs. {m2} ({trn})", "h1": m1, "h2": m2})
                        else:
                            w, l = (m1, m2) if c0.get("winner") else (m2, m1)
                            zaznamy.append({
                                "datum": dt_str,
                                "surface": "Hard",
                                "winner": w,
                                "loser": l,
                                "w_rank": ranks.get(w, 150),
                                "l_rank": ranks.get(l, 150),
                                "score": sc_txt
                            })
        except Exception:
            pass
    df = pd.DataFrame(zaznamy)
    if df.empty:
        return pd.DataFrame(), list(), dict(), dict(), dnesne
    df = df.drop_duplicates(subset=("datum", "winner", "loser")).sort_values("datum").reset_index(drop=True)

    elo = {"Hard": dict(), "Clay": dict(), "Grass": dict()}
    for _, r in df.iterrows():
        w, l = r["winner"], r["loser"]
        s = r["surface"] if r["surface"] in ("Hard", "Clay", "Grass") else "Hard"
        if pd.notna(r.get("w_rank")) and w not in ranks:
            ranks[w] = int(float(r["w_rank"]))
        if pd.notna(r.get("l_rank")) and l not in ranks:
            ranks[l] = int(float(r["l_rank"]))
        rw, rl = elo[s].get(w, 1500), elo[s].get(l, 1500)
        ew = 1 / (1 + 10 ** ((rl - rw) / 400))
        elo[s][w] = rw + 32 * (1 - ew)
        elo[s][l] = rl + 32 * (0 - (1 - ew))

    vsetci = sorted(list(set(df["winner"]).union(set(df["loser"])).union(set(ranks.keys()))))
    return df, vsetci, elo, ranks, dnesne

with st.spinner("Nacitavam zive data 2026..."):
    df, hraci, elo_surf, ranks, dnesne = nacitaj_data(okruh)

if df.empty:
    st.error("Chyba nacitania dat.")
    st.stop()

najnovsi = str(df["datum"].max())
st.success(f"Databaza: {len(hraci)} hracov | Najnovsi zapas: {najnovsi[:4]}-{najnovsi[4:6]}-{najnovsi[6:]} | Dnesne: {len(dnesne)}")

i1, i2 = 0, 1 if len(hraci) > 1 else 0
if dnesne:
    vyber = st.selectbox("Dnesne zive zapasy:", list(("Vyber z dnesnych zapasov",)) + list(z["popis"] for z in dnesne))
    for z in dnesne:
        if z["popis"] == vyber:
            if z["h1"] in hraci:
                i1 = hraci.index(z["h1"])
            if z["h2"] in hraci:
                i2 = hraci.index(z["h2"])

c_a, c_b = st.columns(2)
h1 = c_a.selectbox("Hrac 1", hraci, index=i1)
h2 = c_b.selectbox("Hrac 2", hraci, index=i2)
c_p, c_t, c_d = st.columns(3)
povrch = c_p.selectbox("Povrch:", ("Hard", "Clay", "Grass"))
turnaj = c_t.selectbox("Turnaj:", ("Grand Slam / Masters / Finals", "ATP/WTA 250-500", "Challenger / ITF"))
domaci = c_d.selectbox("Domaci:", ("Nikto", h1, h2))

if h1 == h2:
    st.warning("Vyberte dvoch roznych superov.")
    st.stop()

e1, e2 = elo_surf[povrch].get(h1, 1500), elo_surf[povrch].get(h2, 1500)
p_elo = 1 / (1 + 10 ** ((e2 - e1) / 400))

z1 = df[(df["winner"] == h1) | (df["loser"] == h1)].tail(20)
z2 = df[(df["winner"] == h2) | (df["loser"] == h2)].tail(20)

def forma(zap, m):
    if zap.empty:
        return 0.5, list(), list()
    vahy = np.linspace(0.5, 1.5, len(zap))
    b = 0
    h_raw = list()
    h_farby = list()
    for (_, r), v in zip(zap.iterrows(), vahy):
        if r["winner"] == m:
            b += v
            h_raw.append("Z")
            h_farby.append(":green[**Z**]")
        else:
            h_raw.append("P")
            h_farby.append(":red[**P**]")
    return b / sum(vahy), h_raw, h_farby

f1, hist1, farby1 = forma(z1, h1)
f2, hist2, farby2 = forma(z2, h2)
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
    skr = 0
    neob = 0
    dtp = list()
    for _, r in zap.iterrows():
        if r["loser"] == m:
            sc_u = str(r.get("score", "")).upper()
            if "RET" in sc_u or "W/O" in sc_u:
                skr += 1
            if float(r.get("w_rank", 150) or 150) > float(r.get("l_rank", 150) or 150) + 60:
                neob += 1
            try:
                dtp.append(datetime.strptime(str(r["datum"])[:8], "%Y%m%d"))
            except Exception:
                pass
    cyk = False
    if wta and len(dtp) > 0:
        mod_dni = (datetime.utcnow() - dtp[-1]).days % 28
        if mod_dni <= 3 or mod_dni >= 25:
            cyk = True
    return max(0.2, 1.0 - skr * 0.15 - neob * 0.10 - (0.25 if cyk else 0)), skr, neob, cyk

st1, skr1, np1, cyk1 = vykyvy(z1, h1, "WTA" in okruh)
st2, skr2, np2, cyk2 = vykyvy(z2, h2, "WTA" in okruh)
p_stab = st1 / (st1 + st2)

sanca1 = 0.25 * p_elo + 0.20 * p_forma + 0.15 * p_h2h + 0.15 * p_unava + 0.10 * p_mot + 0.10 * p_dom + 0.05 * p_stab
sanca2 = 1 - sanca1

st.divider()
if (r1 > r2 + 30 and sanca1 > 0.52) or (r2 > r1 + 30 and sanca2 > 0.52):
    st.error(f"POZOR NA PREKVAPENIE: {h1 if sanca1 > sanca2 else h2} ma podla 7 pilierov navrch!")

col1, col2 = st.columns(2)
with col1:
    st.subheader(h1)
    st.caption(f"Rank: #{r1} | Elo: {int(e1)} | Zapasy 7d: {u1}")
    st.metric("Sanca na vyhru", f"{sanca1*100:.1f} %", f"Ferovy kurz: {1/sanca1:.2f}")

with col2:
    st.subheader(h2)
    st.caption(f"Rank: #{r2} | Elo: {int(e2)} | Zapasy 7d: {u2}")
    st.metric("Sanca na vyhru", f"{sanca2*100:.1f} %", f"Ferovy kurz: {1/sanca2:.2f}")

st.progress(float(sanca1))
st.divider()

st.subheader("Poslednych 20 zapasov a Skore")
st.markdown(f"**{h1}** ({hist1.count('Z')}W - {hist1.count('P')}L): " + " ".join(farby1))
st.markdown(f"**{h2}** ({hist2.count('Z')}W - {hist2.count('P')}L): " + " ".join(farby2))

with st.expander("Detailny rozpis poslednych 20 zapasov so skore"):
    c_z1, c_z2 = st.columns(2)
    with c_z1:
        st.markdown(f"**{h1}:**")
        for _, r in z1.iloc[::-1].iterrows():
            znacka = ":green[**Z**]" if r["winner"] == h1 else ":red[**P**]"
            sup = r["loser"] if r["winner"] == h1 else r["winner"]
            st.markdown(f"{znacka} `{r['datum'][4:6]}.{r['datum'][6:]}` vs {sup} ({r['score']})")
    with c_z2:
        st.markdown(f"**{h2}:**")
        for _, r in z2.iloc[::-1].iterrows():
            znacka = ":green[**Z**]" if r["winner"] == h2 else ":red[**P**]"
            sup = r["loser"] if r["winner"] == h2 else r["winner"]
            st.markdown(f"{znacka} `{r['datum'][4:6]}.{r['datum'][6:]}` vs {sup} ({r['score']})")

st.subheader("Neobvykle prehry, skrece a cyklus")
st.write(f"- **{h1}:** Skrece: {skr1} | Neobvykle prehry: {np1}" + (" | Riziko 28-dnoveho okna" if cyk1 else ""))
st.write(f"- **{h2}:** Skrece: {skr2} | Neobvykle prehry: {np2}" + (" | Riziko 28-dnoveho okna" if cyk2 else ""))

st.subheader("Spolocne zapasy (H2H) a Spolocni superi")
st.write(f"**Priama bilancia (H2H):** {h1} {wh1} : {wh2} {h2}")
for _, r in h2h.iloc[::-1].iterrows():
    st.caption(f"- {r['datum'][:4]}-{r['datum'][4:6]}: Vyhral {r['winner']} ({r['score']})")

if spol:
    st.write(f"**Spolocni superi z poslednych 20 zapasov ({len(spol)}):**")
    for sm in spol[:10]:
        r_s1 = z1[(z1["winner"] == sm) | (z1["loser"] == sm)].iloc[-1]
        r_s2 = z2[(z2["winner"] == sm) | (z2["loser"] == sm)].iloc[-1]
        t1 = f":green[**Z**] ({r_s1['score']})" if r_s1["winner"] == h1 else f":red[**P**] ({r_s1['score']})"
        t2 = f":green[**Z**] ({r_s2['score']})" if r_s2["winner"] == h2 else f":red[**P**] ({r_s2['score']})"
        st.markdown(f"- vs. **{sm}** -> {h1}: {t1} | {h2}: {t2}")
else:
    st.caption("Ziadni spolocni superi v poslednych 20 zapasoch.")









