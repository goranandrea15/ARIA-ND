import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# ─── COORDONNÉES GÉOGRAPHIQUES ────────────────────────────────
COORDS = {
    # Centres de distribution
    "CD-Montreal":    (45.5017, -73.5673),
    "CD-Quebec":      (46.8139, -71.2080),
    "CD-Sherbrooke":  (45.4042, -71.8929),
    "CD-Gatineau":    (45.4765, -75.7013),
    # Établissements
    "CHUM":                (45.5100, -73.5543),
    "McGill-Univ-Health":  (45.4735, -73.6010),
    "CIUSSS-NordMTL":      (45.5580, -73.6832),
    "CISSS-Laval":         (45.6066, -73.7124),
    "CISSS-Monteregie-O":  (45.3500, -73.8800),
    "CISSS-Monteregie-C":  (45.4500, -73.4500),
    "CISSS-Monteregie-E":  (45.3200, -73.1200),
    "CISSS-Lanaudiere":    (45.8500, -73.4000),
    "CISSS-Laurentides":   (45.9500, -74.0000),
    "CHSLD-Longueuil":     (45.5318, -73.5200),
    "CIUSSS-Estrie-CHUS":  (45.4042, -71.8929),
    "CISSS-Monteregie-Est2":(45.3300, -72.8000),
    "CISSS-Outaouais":     (45.4765, -75.7013),
    "CISSS-Laurentides-N": (46.1000, -74.6000),
    "CIUSSS-Capitale-Nat": (46.8139, -71.2080),
    "IUCPQ":               (46.7800, -71.3100),
    "CIUSSS-Mauricie":     (46.3500, -72.5500),
    "CISSS-ChaudiereApp":  (46.3500, -71.0000),
    "CISSS-Bas-StLaurent": (47.8500, -69.5000),
    "CISSS-Saguenay-LSJ":  (48.4284, -71.0537),
    "CIUSSS-Saguenay":     (48.3800, -71.1000),
    "CISSS-CoteNord":      (50.2000, -66.3800),
    "CISSS-Gaspesie":      (48.8300, -64.4800),
    "CISSS-Abitibi":       (48.2500, -79.0000),
    "CUSM-Hopital":        (45.4735, -73.6100),
    "CHU-Sainte-Justine":  (45.5020, -73.6200),
    "CISSS-Laval-CHSLD":   (45.6200, -73.7300),
    "CIUSSS-Centre-Ouest": (45.4900, -73.6000),
    "CISSS-Richelieu-Yam": (45.4000, -72.7300),
    "CISSS-Nunavik":       (58.1000, -68.4000),
}

# Mapping établissement → CD
ETAB_TO_CD = {
    "CHUM": "CD-Montreal", "McGill-Univ-Health": "CD-Montreal",
    "CIUSSS-NordMTL": "CD-Montreal", "CISSS-Laval": "CD-Montreal",
    "CISSS-Monteregie-O": "CD-Montreal", "CISSS-Monteregie-C": "CD-Montreal",
    "CISSS-Monteregie-E": "CD-Montreal", "CISSS-Lanaudiere": "CD-Montreal",
    "CISSS-Laurentides": "CD-Montreal", "CHSLD-Longueuil": "CD-Montreal",
    "CUSM-Hopital": "CD-Montreal", "CHU-Sainte-Justine": "CD-Montreal",
    "CISSS-Laval-CHSLD": "CD-Montreal", "CIUSSS-Centre-Ouest": "CD-Montreal",
    "CISSS-Richelieu-Yam": "CD-Montreal",
    "CIUSSS-Estrie-CHUS": "CD-Sherbrooke", "CISSS-Monteregie-Est2": "CD-Sherbrooke",
    "CISSS-Outaouais": "CD-Gatineau", "CISSS-Laurentides-N": "CD-Gatineau",
    "CIUSSS-Capitale-Nat": "CD-Quebec", "IUCPQ": "CD-Quebec",
    "CIUSSS-Mauricie": "CD-Quebec", "CISSS-ChaudiereApp": "CD-Quebec",
    "CISSS-Bas-StLaurent": "CD-Quebec", "CISSS-Saguenay-LSJ": "CD-Quebec",
    "CIUSSS-Saguenay": "CD-Quebec", "CISSS-CoteNord": "CD-Quebec",
    "CISSS-Gaspesie": "CD-Quebec", "CISSS-Abitibi": "CD-Quebec",
    "CISSS-Nunavik": "CD-Quebec",
}

# ─── Azure OpenAI ─────────────────────────────────────────────
try:
    from openai import AzureOpenAI
    AZURE_KEY = os.environ.get("AZURE_OPENAI_KEY", "")
    AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt4o-aria")
    USE_AI = bool(AZURE_KEY and AZURE_ENDPOINT)
    if USE_AI:
        client = AzureOpenAI(api_key=AZURE_KEY, azure_endpoint=AZURE_ENDPOINT, api_version="2024-02-01")
except Exception:
    USE_AI = False

# ─── CONFIG ───────────────────────────────────────────────────
st.set_page_config(page_title="ARIA-ND | KPI Dashboard", page_icon="🏥", layout="wide")

SEUILS_FILE = "seuils_valides.csv"
SEUILS_DEFAULT = {
    "CHUM": (98.0, 7), "McGill-Univ-Health": (98.0, 7),
    "CIUSSS-NordMTL": (96.0, 5), "CISSS-Laval": (96.0, 5),
    "CISSS-Monteregie-O": (96.0, 3), "CISSS-Monteregie-C": (96.0, 3),
    "CISSS-Monteregie-E": (96.0, 3), "CISSS-Lanaudiere": (96.0, 3),
    "CISSS-Laurentides": (96.0, 3), "CHSLD-Longueuil": (96.0, 5),
}

# ─── FONCTIONS ────────────────────────────────────────────────
def load_seuils():
    dtype_map = {
        "Etablissement": str,
        "Taux_service_cible": float,
        "Frequence_optimale": int,
        "Valide_par": str,
        "Date_validation": str,
        "Statut": str,
    }
    if os.path.exists(SEUILS_FILE):
        df = pd.read_csv(SEUILS_FILE, dtype=dtype_map)
        # S'assurer que les colonnes texte ne contiennent pas de NaN
        df["Valide_par"] = df["Valide_par"].fillna("").astype(str)
        df["Date_validation"] = df["Date_validation"].fillna("").astype(str)
        df["Statut"] = df["Statut"].fillna("EN_ATTENTE").astype(str)
        return df
    rows = []
    for etab, (ts, fo) in SEUILS_DEFAULT.items():
        rows.append({"Etablissement": etab, "Taux_service_cible": ts,
                     "Frequence_optimale": fo, "Valide_par": "",
                     "Date_validation": "", "Statut": "EN_ATTENTE"})
    return pd.DataFrame(rows)

def save_seuils(df):
    df.to_csv(SEUILS_FILE, index=False)

def get_seuil(df_seuils, etab):
    row = df_seuils[df_seuils["Etablissement"] == etab]
    if not row.empty and row.iloc[0]["Statut"] == "VALIDE":
        return float(row.iloc[0]["Taux_service_cible"]), int(row.iloc[0]["Frequence_optimale"])
    return SEUILS_DEFAULT.get(etab, (96.0, 3))

def generer_rapport_ia(df, df_seuils):
    resume = []
    for _, row in df.groupby("Etablissement").last().iterrows():
        etab = row.name if hasattr(row, 'name') else "N/A"
        resume.append(f"{etab}: taux={row['Taux_service_reel']}%, cible={row['Taux_service_cible']}%")
    prompt = f"""Tu es analyste en réseau de distribution pour Santé Québec.
Génère un rapport exécutif de 200 mots en français sur la performance du réseau.
Données : {chr(10).join(resume[:10])}
Structure : SITUATION GLOBALE, ALERTES PRIORITAIRES (max 3), RECOMMANDATIONS (3 actions).
Termine par l'impact estimé sur les soins."""
    try:
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500, temperature=0.3)
        return response.choices[0].message.content, True
    except Exception as e:
        return f"""RAPPORT EXÉCUTIF — RÉSEAU SANTÉ QUÉBEC
Semaine du {datetime.now().strftime('%d %B %Y')}

SITUATION GLOBALE
Le réseau de distribution provincial affiche une performance variable selon les régions.
Les établissements urbains maintiennent leurs cibles. Les régions éloignées présentent
des écarts de fréquence à surveiller.

ALERTES PRIORITAIRES
1. Fréquence sous-optimale détectée sur 3 corridors éloignés
2. Taux de service sous la cible sur 2 établissements régionaux
3. Données manquantes pour 2 établissements cette semaine

RECOMMANDATIONS
1. Augmenter la fréquence de livraison sur les corridors Bas-Saint-Laurent et Saguenay
2. Valider les seuils EN_ATTENTE avec la direction avant prochain cycle
3. Contacter les établissements sans données pour résoudre les lacunes

Impact estimé : +8% taux de service, -15% coûts transport si recommandations appliquées.

[Mode démo — API Azure non connectée]""", False

# ─── HEADER ──────────────────────────────────────────────────
st.markdown("""
<div style='background:linear-gradient(135deg,#1F3864,#2E75B6);padding:20px;border-radius:10px;margin-bottom:20px'>
<h1 style='color:white;margin:0;font-size:26px'>🏥 ARIA-ND — KPI Dashboard</h1>
<p style='color:#BDD7EE;margin:4px 0 0 0;font-size:13px'>
Analyse Réseau Intelligence Agentique — Network Design | Santé Québec</p>
</div>
""", unsafe_allow_html=True)

# ─── SIDEBAR ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    ai_status = "✅ Azure OpenAI Canada East" if USE_AI else "ℹ️ Mode démo"
    st.markdown(f"**IA:** {ai_status}")
    st.markdown("---")
    uploaded = st.file_uploader("📂 Charger sample_kpis.csv", type="csv")
    st.markdown("---")
    st.markdown("### 🔗 ARIA-ND GitHub")
    st.markdown("[github.com/goranandrea15/ARIA-ND](https://github.com/goranandrea15/ARIA-ND)")

# ─── ONGLETS ─────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard KPIs",
    "🔐 Validation des seuils (Human in the Loop)",
    "📝 Rapport exécutif IA",
    "🗺️ Carte du réseau O-D"
])

# ─── CHARGEMENT DONNÉES ──────────────────────────────────────
if uploaded:
    df = pd.read_csv(uploaded)
else:
    if os.path.exists("sample_kpis.csv"):
        df = pd.read_csv("sample_kpis.csv")
    else:
        st.warning("⚠️ Aucun fichier de données trouvé. Chargez sample_kpis.csv.")
        st.stop()

df_seuils = load_seuils()

# ═══════════════════════ TAB 1 : DASHBOARD ═══════════════════
with tab1:
    # Métriques globales
    derniere_semaine = df["Semaine"].max()
    df_last = df[df["Semaine"] == derniere_semaine]

    seuils_valides = len(df_seuils[df_seuils["Statut"] == "VALIDE"])
    seuils_attente = len(df_seuils[df_seuils["Statut"] == "EN_ATTENTE"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        taux_moyen = df_last["Taux_service_reel"].mean()
        delta = taux_moyen - df_last["Taux_service_cible"].mean()
        st.metric("Taux de service moyen", f"{taux_moyen:.1f}%", f"{delta:+.1f}% vs cible")
    with col2:
        lignes = df_last["Lignes_traitees"].sum()
        st.metric("Lignes traitées (semaine)", f"{lignes:,}")
    with col3:
        sous_cible = len(df_last[df_last["Taux_service_reel"] < df_last["Taux_service_cible"]])
        st.metric("Établissements sous cible", sous_cible,
                  delta_color="inverse")
    with col4:
        if seuils_attente > 0:
            st.metric("Seuils en attente validation", seuils_attente,
                      "⚠️ Action requise", delta_color="inverse")
        else:
            st.metric("Seuils validés", seuils_valides, "✅ Tous validés")

    # Alerte Human in the Loop
    if seuils_attente > 0:
        st.warning(f"""⚠️ **HUMAN IN THE LOOP — {seuils_attente} seuil(s) en attente de validation**

Les seuils suivants ont été calculés par ARIA-ND-Simulator mais **n'ont pas encore été validés** par la direction.
Le dashboard utilise les seuils par défaut en attendant. 
→ **Aller dans l'onglet "Validation des seuils"** pour approuver ou ajuster.""")

    st.markdown(f"#### Performance réseau — Semaine {derniere_semaine}")

    # Tableau de performance
    display_data = []
    for _, row in df_last.iterrows():
        etab = row["Etablissement"]
        taux_cible, freq_opt = get_seuil(df_seuils, etab)
        statut_seuil = "✅ Validé" if len(df_seuils[
            (df_seuils["Etablissement"] == etab) &
            (df_seuils["Statut"] == "VALIDE")]) > 0 else "⚠️ Défaut"
        ecart = row["Taux_service_reel"] - taux_cible
        status = "🟢" if ecart >= 0 else ("🟡" if ecart >= -2 else "🔴")
        freq_ecart = row["Frequence_livraison_reelle"] - freq_opt
        display_data.append({
            "Statut": status,
            "Établissement": etab,
            "Taux réel (%)": f"{row['Taux_service_reel']:.1f}",
            "Cible (%)": f"{taux_cible:.1f}",
            "Écart": f"{ecart:+.1f}",
            "Fréq. réelle": int(row["Frequence_livraison_reelle"]),
            "Fréq. optimale": freq_opt,
            "Écart fréq.": f"{freq_ecart:+d}",
            "Seuil": statut_seuil,
        })

    df_display = pd.DataFrame(display_data)
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Évolution temporelle
    st.markdown("#### Évolution du taux de service — 12 semaines")
    pivot = df.pivot_table(index="Semaine", columns="Etablissement",
                           values="Taux_service_reel", aggfunc="mean")
    st.line_chart(pivot)

# ═══════════════════ TAB 2 : HUMAN IN THE LOOP ════════════════
with tab2:
    st.markdown("""
    <div style='background:#FFF3CD;border-left:5px solid #FFC107;padding:15px;border-radius:5px;margin-bottom:20px'>
    <h4 style='margin:0;color:#856404'>🔐 HUMAN IN THE LOOP — Validation des seuils de performance</h4>
    <p style='margin:8px 0 0 0;color:#856404;font-size:13px'>
    Les seuils ci-dessous ont été calculés automatiquement par ARIA-ND-Simulator.
    <strong>Ils ne seront utilisés dans le dashboard que lorsqu'un responsable les aura validés.</strong>
    Aucune décision automatique n'est prise sans approbation humaine.
    </p>
    </div>
    """, unsafe_allow_html=True)

    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.info(f"**{seuils_valides}** seuil(s) validé(s) ✅")
    with col_info2:
        st.warning(f"**{seuils_attente}** seuil(s) en attente ⚠️")

    st.markdown("---")
    st.markdown("#### Seuils calculés par ARIA-ND-Simulator — En attente de validation")

    # Formulaire de validation
    nom_validateur = st.text_input("Votre nom (responsable de la validation)",
                                    placeholder="Ex: Azzedine Abderrahim")

    df_seuils_edit = df_seuils.copy()

    cols_header = st.columns([2.5, 1.5, 1.5, 1.5, 1])
    cols_header[0].markdown("**Établissement**")
    cols_header[1].markdown("**Taux cible (%)**")
    cols_header[2].markdown("**Fréq. optimale**")
    cols_header[3].markdown("**Statut actuel**")
    cols_header[4].markdown("**Valider**")

    changes = {}
    for idx, row in df_seuils.iterrows():
        cols = st.columns([2.5, 1.5, 1.5, 1.5, 1])
        etab = row["Etablissement"]
        cols[0].write(etab)
        new_taux = cols[1].number_input("", value=float(row["Taux_service_cible"]),
                                         min_value=85.0, max_value=100.0, step=0.5,
                                         key=f"taux_{idx}", label_visibility="collapsed")
        new_freq = cols[2].number_input("", value=int(row["Frequence_optimale"]),
                                         min_value=1, max_value=14, step=1,
                                         key=f"freq_{idx}", label_visibility="collapsed")
        statut = row["Statut"]
        if statut == "VALIDE":
            cols[3].success("✅ VALIDÉ")
        else:
            cols[3].warning("⚠️ EN ATTENTE")
        valider = cols[4].checkbox("", key=f"val_{idx}", value=(statut == "VALIDE"))
        changes[idx] = {"taux": new_taux, "freq": new_freq, "valider": valider}

    st.markdown("---")
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 3])
    with col_btn1:
        if st.button("✅ Enregistrer les validations", type="primary", use_container_width=True):
            if not nom_validateur.strip():
                st.error("⚠️ Entrez votre nom avant de valider.")
            else:
                for idx, change in changes.items():
                    df_seuils_edit.at[idx, "Taux_service_cible"] = change["taux"]
                    df_seuils_edit.at[idx, "Frequence_optimale"] = change["freq"]
                    if change["valider"]:
                        df_seuils_edit.at[idx, "Statut"] = "VALIDE"
                        df_seuils_edit.at[idx, "Valide_par"] = nom_validateur
                        df_seuils_edit.at[idx, "Date_validation"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    else:
                        df_seuils_edit.at[idx, "Statut"] = "EN_ATTENTE"
                        df_seuils_edit.at[idx, "Valide_par"] = ""
                        df_seuils_edit.at[idx, "Date_validation"] = ""
                save_seuils(df_seuils_edit)
                st.success(f"✅ Seuils enregistrés par {nom_validateur}")
                st.rerun()
    with col_btn2:
        if st.button("✅ Tout valider", use_container_width=True):
            if not nom_validateur.strip():
                st.error("⚠️ Entrez votre nom avant de valider.")
            else:
                for idx in df_seuils_edit.index:
                    df_seuils_edit.at[idx, "Statut"] = "VALIDE"
                    df_seuils_edit.at[idx, "Valide_par"] = nom_validateur
                    df_seuils_edit.at[idx, "Date_validation"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                save_seuils(df_seuils_edit)
                st.success(f"✅ Tous les seuils validés par {nom_validateur}")
                st.rerun()

    # Historique
    if len(df_seuils[df_seuils["Statut"] == "VALIDE"]) > 0:
        st.markdown("---")
        st.markdown("#### Historique des validations")
        df_historique = df_seuils[df_seuils["Statut"] == "VALIDE"][
            ["Etablissement", "Taux_service_cible", "Frequence_optimale", "Valide_par", "Date_validation"]]
        st.dataframe(df_historique, use_container_width=True, hide_index=True)

# ═══════════════════ TAB 3 : RAPPORT IA ══════════════════════
with tab3:
    st.markdown("#### Rapport exécutif IA — Narration automatique du réseau")

    if seuils_attente > 0:
        st.warning(f"⚠️ {seuils_attente} seuil(s) non validé(s) — le rapport utilise les seuils par défaut. Validez les seuils dans l'onglet précédent pour un rapport précis.")

    col_r1, col_r2 = st.columns([3, 1])
    with col_r2:
        semaine_sel = st.selectbox("Semaine", sorted(df["Semaine"].unique(), reverse=True))
    with col_r1:
        st.markdown(f"Rapport basé sur les données de la semaine **{semaine_sel}**")

    if st.button("🤖 Générer le rapport exécutif", type="primary", use_container_width=True):
        df_sel = df[df["Semaine"] == semaine_sel]
        with st.spinner("ARIA-ND génère le rapport via Azure OpenAI Canada East..."):
            rapport, ia_utilisee = generer_rapport_ia(df_sel, df_seuils)

        source = "✅ Généré par GPT-4o via API Azure OpenAI Canada East — Conforme Loi 25" if ia_utilisee else "ℹ️ Mode démo — rapport pré-généré"
        st.markdown(f"""
        <div style='background:#F0F8FF;border-left:5px solid #2E75B6;padding:20px;border-radius:8px;margin-top:10px'>
        <h4 style='color:#1F3864;margin-top:0'>📋 RAPPORT EXÉCUTIF — RÉSEAU SANTÉ QUÉBEC</h4>
        <p style='color:#666;font-size:11px;margin-bottom:15px'>{source}</p>
        <div style='white-space:pre-wrap;font-family:Calibri;font-size:14px;color:#1F3864;line-height:1.6'>{rapport}</div>
        </div>
        """, unsafe_allow_html=True)

        # Statut des seuils dans le rapport
        st.markdown("---")
        st.markdown("**Statut des seuils utilisés dans ce rapport :**")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.success(f"✅ {seuils_valides} seuil(s) validé(s) par la direction")
        with col_s2:
            if seuils_attente > 0:
                st.warning(f"⚠️ {seuils_attente} seuil(s) en attente — seuils par défaut utilisés")

# ═══════════════════ TAB 4 : CARTE O-D ══════════════════════
with tab4:
    st.markdown("#### 🗺️ Carte du réseau Origine-Destination — Santé Québec")

    if not HAS_PLOTLY:
        st.error("❌ Plotly requis. Installer avec : `pip install plotly`")
    else:
        # Contrôles
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)
        with col_ctrl1:
            afficher_routes = st.checkbox("Afficher les routes O-D", value=True)
        with col_ctrl2:
            filtrer_cd = st.selectbox("Filtrer par CD",
                ["Tous"] + ["CD-Montreal", "CD-Quebec", "CD-Sherbrooke", "CD-Gatineau"])
        with col_ctrl3:
            derniere_sem_map = df["Semaine"].max()
            sem_map = st.selectbox("Semaine KPI", sorted(df["Semaine"].unique(), reverse=True),
                                    key="sem_map")

        # Données KPI pour coloration
        df_map = df[df["Semaine"] == sem_map].copy()
        df_map["Ecart"] = df_map["Taux_service_reel"] - df_map["Taux_service_cible"]
        df_map["Couleur_status"] = df_map["Ecart"].apply(
            lambda x: "Objectif atteint" if x >= 0 else ("Ecart faible" if x >= -2 else "Sous la cible"))

        fig = go.Figure()

        # ── ROUTES O-D ──────────────────────────────────────────
        if afficher_routes:
            etabs_a_afficher = [e for e in ETAB_TO_CD.keys()
                                if filtrer_cd == "Tous" or ETAB_TO_CD[e] == filtrer_cd]
            for etab in etabs_a_afficher:
                cd = ETAB_TO_CD[etab]
                if etab in COORDS and cd in COORDS:
                    lat_etab, lon_etab = COORDS[etab]
                    lat_cd, lon_cd = COORDS[cd]
                    # Couleur selon performance KPI
                    row_kpi = df_map[df_map["Etablissement"] == etab]
                    if not row_kpi.empty:
                        status = row_kpi.iloc[0]["Couleur_status"]
                        couleur = "#2ECC71" if status == "Objectif atteint" else \
                                  "#F39C12" if status == "Ecart faible" else "#E74C3C"
                        width = 2.5
                    else:
                        couleur = "#95A5A6"
                        width = 1.5
                    fig.add_trace(go.Scattergeo(
                        lon=[lon_cd, lon_etab, None],
                        lat=[lat_cd, lat_etab, None],
                        mode="lines",
                        line=dict(width=width, color=couleur),
                        hoverinfo="skip",
                        showlegend=False,
                    ))

        # ── CENTRES DE DISTRIBUTION ─────────────────────────────
        cds = ["CD-Montreal", "CD-Quebec", "CD-Sherbrooke", "CD-Gatineau"]
        cd_lats = [COORDS[cd][0] for cd in cds if cd in COORDS]
        cd_lons = [COORDS[cd][1] for cd in cds if cd in COORDS]
        cd_noms = [cd for cd in cds if cd in COORDS]
        fig.add_trace(go.Scattergeo(
            lon=cd_lons, lat=cd_lats,
            mode="markers+text",
            marker=dict(size=18, color="#1F3864", symbol="square",
                       line=dict(width=2, color="white")),
            text=[cd.replace("CD-", "") for cd in cd_noms],
            textposition="top center",
            textfont=dict(size=10, color="#1F3864", family="Arial Black"),
            name="Centres de distribution",
            hovertemplate="<b>%{text}</b><extra></extra>",
        ))

        # ── ÉTABLISSEMENTS avec KPIs ─────────────────────────────
        for status, couleur, symbole in [
            ("Objectif atteint", "#2ECC71", "circle"),
            ("Ecart faible", "#F39C12", "circle"),
            ("Sous la cible", "#E74C3C", "circle"),
            ("Sans données", "#95A5A6", "circle-open"),
        ]:
            if status == "Sans données":
                etabs_status = [e for e in ETAB_TO_CD.keys()
                                if e not in df_map["Etablissement"].values
                                and (filtrer_cd == "Tous" or ETAB_TO_CD.get(e) == filtrer_cd)]
            else:
                etabs_df = df_map[df_map["Couleur_status"] == status]["Etablissement"].tolist()
                etabs_status = [e for e in etabs_df
                                if filtrer_cd == "Tous" or ETAB_TO_CD.get(e) == filtrer_cd]

            if not etabs_status:
                continue

            lats = [COORDS[e][0] for e in etabs_status if e in COORDS]
            lons = [COORDS[e][1] for e in etabs_status if e in COORDS]
            noms = [e for e in etabs_status if e in COORDS]

            if status != "Sans données":
                hover_texts = []
                for e in noms:
                    row = df_map[df_map["Etablissement"] == e]
                    if not row.empty:
                        r = row.iloc[0]
                        hover_texts.append(
                            f"<b>{e}</b><br>"
                            f"Taux: {r['Taux_service_reel']:.1f}% (cible: {r['Taux_service_cible']:.1f}%)<br>"
                            f"Écart: {r['Ecart']:+.1f}%<br>"
                            f"Fréq: {int(r['Frequence_livraison_reelle'])}/sem<br>"
                            f"CD: {ETAB_TO_CD.get(e,'N/A')}"
                        )
                    else:
                        hover_texts.append(e)
            else:
                hover_texts = [f"<b>{e}</b><br>Données non disponibles" for e in noms]

            fig.add_trace(go.Scattergeo(
                lon=lons, lat=lats,
                mode="markers",
                marker=dict(size=10, color=couleur, symbol=symbole,
                           line=dict(width=1.5, color="white")),
                name=status,
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_texts,
            ))

        # ── MISE EN PAGE ─────────────────────────────────────────
        fig.update_layout(
            geo=dict(
                scope="north america",
                resolution=50,
                showland=True, landcolor="#F8F9FA",
                showocean=True, oceancolor="#EBF5FB",
                showlakes=True, lakecolor="#EBF5FB",
                showrivers=True, rivercolor="#AED6F1",
                showcountries=True, countrycolor="#BDC3C7",
                showsubunits=True, subunitcolor="#D5D8DC",
                center=dict(lat=48.5, lon=-72.0),
                projection_scale=5.5,
            ),
            height=600,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1,
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="#BDC3C7", borderwidth=1,
            ),
            title=dict(
                text=f"Réseau O-D Santé Québec — {filtrer_cd} — Semaine {sem_map}",
                font=dict(size=14, color="#1F3864"),
                x=0.5,
            ),
        )

        st.plotly_chart(fig, use_container_width=True)

        # Légende explicative
        col_leg1, col_leg2, col_leg3, col_leg4 = st.columns(4)
        col_leg1.markdown("🟦 **Centre de distribution**")
        col_leg2.markdown("🟢 **Objectif atteint** (≥ cible)")
        col_leg3.markdown("🟠 **Écart faible** (< 2%)")
        col_leg4.markdown("🔴 **Sous la cible** (> 2%)")

        # Stats réseau
        st.markdown("---")
        st.markdown("#### Statistiques du réseau")
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        nb_etabs = len([e for e in ETAB_TO_CD if filtrer_cd == "Tous" or ETAB_TO_CD[e] == filtrer_cd])
        nb_cds = len(set(ETAB_TO_CD.values())) if filtrer_cd == "Tous" else 1
        nb_corridors = len([e for e in ETAB_TO_CD if filtrer_cd == "Tous" or ETAB_TO_CD[e] == filtrer_cd])
        dist_max = max([850, 420, 380, 320]) if filtrer_cd in ["Tous", "CD-Quebec"] else 80

        col_s1.metric("Établissements", nb_etabs)
        col_s2.metric("Centres de distribution", nb_cds)
        col_s3.metric("Corridors actifs", nb_corridors)
        col_s4.metric("Distance max (km)", dist_max)

# ─── FOOTER ──────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center;color:#666;font-size:11px'>
ARIA-ND v2.0 | Analyse Réseau Intelligence Agentique — Network Design |
Azure OpenAI Canada East | Conforme Loi 25 |
<a href='https://github.com/goranandrea15/ARIA-ND'>github.com/goranandrea15/ARIA-ND</a>
</div>
""", unsafe_allow_html=True)
