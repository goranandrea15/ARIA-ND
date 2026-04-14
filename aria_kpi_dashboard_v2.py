import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

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
tab1, tab2, tab3 = st.tabs([
    "📊 Dashboard KPIs",
    "🔐 Validation des seuils (Human in the Loop)",
    "📝 Rapport exécutif IA"
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

# ─── FOOTER ──────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center;color:#666;font-size:11px'>
ARIA-ND v2.0 | Analyse Réseau Intelligence Agentique — Network Design |
Azure OpenAI Canada East | Conforme Loi 25 |
<a href='https://github.com/goranandrea15/ARIA-ND'>github.com/goranandrea15/ARIA-ND</a>
</div>
""", unsafe_allow_html=True)
