"""
ARIA-ND-KPI-Dashboard — Tableau de bord des indicateurs de performance réseau
==============================================================================
Résout le problème : "Développer des indicateurs de performance spécifiques au
réseau de distribution, construire des tableaux de bord Power BI, assurer la
qualité des données" (Affichage Santé Québec 25-NS-374, Champ d'action #3)

Indicateurs implémentés (ceux cités EXACTEMENT dans l'affichage 25-NS-374) :
  - Taux de respect des niveaux de service
  - Performance des centres de distribution
  - Nombre de lignes traitées
  - Fréquence de livraison optimale vs réelle
  + Narration automatique IA (rapport exécutif hebdomadaire)

Développé par : Andrea Goran
Candidature : Spécialiste en procédés administratifs — Réseau de distribution
Organisation : Santé Québec — Réf. 25-NS-374

Utilisation :
    streamlit run aria_kpi_dashboard.py
    streamlit run aria_kpi_dashboard.py -- --demo
"""

import streamlit as st
import pandas as pd
import os
import sys
from datetime import datetime

# Configuration de la page
st.set_page_config(
    page_title="ARIA-ND — KPI Réseau Distribution",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── STYLES ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background-color: #f0f4fb;
    border-radius: 8px;
    padding: 16px;
    border-left: 4px solid #1F3864;
    margin-bottom: 10px;
}
.alert-red {
    background-color: #FAECE7;
    border-left: 4px solid #993C1D;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
    color: #993C1D;
    font-size: 14px;
}
.alert-green {
    background-color: #E1F5EE;
    border-left: 4px solid #085041;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
    color: #085041;
    font-size: 14px;
}
.kpi-title {
    font-size: 13px;
    color: #4A4A4A;
    margin-bottom: 4px;
}
.narration-box {
    background-color: #E6F1FB;
    border: 1px solid #B5D4F4;
    border-radius: 8px;
    padding: 16px;
    margin-top: 10px;
    color: #0C447C;
    font-size: 14px;
    line-height: 1.7;
}
</style>
""", unsafe_allow_html=True)


# ─── NARRATION DEMO ──────────────────────────────────────────────────────────

NARRATION_DEMO = """
**RAPPORT EXÉCUTIF HEBDOMADAIRE — RÉSEAU DE DISTRIBUTION PROVINCIAL**
*Semaine du {semaine} | Généré par ARIA-ND-KPI-Dashboard*

**RÉSUMÉ DE PERFORMANCE**

Le réseau provincial affiche cette semaine un taux de service moyen de {taux_moyen:.1f}%, 
en progression par rapport à la semaine précédente. 
{nb_etab} établissements ont été desservis pour un total de {lignes_total:,} lignes traitées.

**ALERTES PRIORITAIRES**

{alertes}

**ANALYSE FRÉQUENCE DE LIVRAISON**

{freq_analyse}

**RECOMMANDATION POUR LA SEMAINE PROCHAINE**

Sur la base des données de cette semaine, trois actions prioritaires sont recommandées :
1. Réviser la fréquence de livraison pour les établissements dont l'écart fréquence réelle/optimale 
   dépasse 1 livraison/semaine — risque accru de rupture de stock.
2. Investiguer les causes des retards sur les corridors à faible taux de service (<90%) — 
   identifier si l'origine est opérationnelle, géographique ou liée aux données.
3. Mettre à jour les paramètres de volumétrie pour les 2 établissements dont les lignes traitées 
   ont varié de plus de 15% par rapport à la moyenne des 3 semaines.

*Rapport généré par ARIA-ND-KPI-Dashboard v1.0 — github.com/[user]/ARIA-ND*
*Santé Québec — Direction Logistique et excellence opérationnelle (VPALI)*
"""


# ─── FONCTIONS UTILITAIRES ───────────────────────────────────────────────────

@st.cache_data
def load_data(filepath):
    df = pd.read_csv(filepath)
    return df


def get_latest_week(df):
    return df['Semaine'].max()


def compute_kpis(df, semaine_selectionnee):
    df_s = df[df['Semaine'] == semaine_selectionnee]
    return {
        'taux_service_moyen': df_s['Taux_service_reel'].mean(),
        'taux_service_cible': df_s['Taux_service_cible'].mean(),
        'lignes_traitees': df_s['Lignes_traitees'].sum(),
        'nb_retards': df_s['Retards'].sum(),
        'cout_moyen': df_s['Cout_par_livraison'].mean(),
        'ecart_frequence': (df_s['Frequence_livraison_optimale'] - df_s['Frequence_livraison_reelle']).sum(),
        'nb_sous_cible': (df_s['Taux_service_reel'] < df_s['Taux_service_cible']).sum(),
        'nb_etablissements': len(df_s),
        'df_semaine': df_s,
    }


def call_claude_narration(kpis, df_semaine):
    """Narration via Azure OpenAI GPT-4o (Canada East) — conforme Loi 25."""
    try:
        from openai import AzureOpenAI
        api_key = os.environ.get('AZURE_OPENAI_KEY')
        if not api_key:
            return None
        client = AzureOpenAI(
            api_key=api_key,
            api_version="2024-02-01",
            azure_endpoint=os.environ.get('AZURE_OPENAI_ENDPOINT')
        )
        data_summary = df_semaine[['Etablissement','Taux_service_reel',
            'Lignes_traitees','Frequence_livraison_reelle',
            'Frequence_livraison_optimale','Retards']].to_string(index=False)
        prompt = f"""Tu es le specialiste en procedes administratifs du reseau de
distribution de Sante Quebec. Genere un rapport executif hebdomadaire
de 200 mots en francais.
Taux de service moyen : {kpis['taux_service_moyen']:.1f}%
Lignes traitees : {kpis['lignes_traitees']:,}
Retards : {kpis['nb_retards']}
Detail : {data_summary}
Format : Introduction + 2-3 alertes + 2 recommandations actionnables."""
        response = client.chat.completions.create(
            model=os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt4o-aria'),
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception:
        return None
        client = anthropic.Anthropic(api_key=api_key)
        
        data_summary = df_semaine[['Etablissement', 'Taux_service_reel', 'Lignes_traitees',
                                    'Frequence_livraison_reelle', 'Frequence_livraison_optimale',
                                    'Retards']].to_string(index=False)
        
        prompt = f"""Tu es le spécialiste en procédés administratifs du réseau de distribution de Santé Québec.
Génère un rapport exécutif hebdomadaire de 200 mots en français pour le directeur logistique.

Données KPI de la semaine :
- Taux de service moyen : {kpis['taux_service_moyen']:.1f}% (cible : {kpis['taux_service_cible']:.0f}%)
- Total lignes traitées : {kpis['lignes_traitees']:,}
- Établissements sous la cible : {kpis['nb_sous_cible']}/{kpis['nb_etablissements']}
- Retards cumulés : {kpis['nb_retards']}
- Écart fréquence optimale vs réelle : {kpis['ecart_frequence']} livraisons manquantes

Détail par établissement :
{data_summary}

Format : Introduction (état global) + 2-3 alertes spécifiques + 2 recommandations actionnables.
Ton : Direct, factuel, orienté décision. Style rapport de direction."""
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except Exception:
        return None


def generate_demo_narration(kpis, semaine):
    """Génère la narration de démonstration sans API."""
    alertes = ""
    df_s = kpis['df_semaine']
    sous_cible = df_s[df_s['Taux_service_reel'] < df_s['Taux_service_cible']]
    
    if len(sous_cible) > 0:
        for _, row in sous_cible.iterrows():
            alertes += f"- ⚠️ **{row['Etablissement']}** : taux de service {row['Taux_service_reel']:.1f}% "
            alertes += f"(cible {row['Taux_service_cible']:.0f}%) — {row['Retards']} retards cette semaine\n"
    else:
        alertes = "✅ Tous les établissements atteignent leur cible de service cette semaine."
    
    freq_etab = df_s[df_s['Frequence_livraison_reelle'] < df_s['Frequence_livraison_optimale']]
    if len(freq_etab) > 0:
        noms = ', '.join(freq_etab['Etablissement'].tolist())
        freq_analyse = f"{len(freq_etab)} établissement(s) reçoivent moins de livraisons que l'optimum : {noms}. Risque de tension sur les stocks identifié."
    else:
        freq_analyse = "Toutes les fréquences de livraison correspondent aux besoins optimaux identifiés."
    
    return NARRATION_DEMO.format(
        semaine=semaine,
        taux_moyen=kpis['taux_service_moyen'],
        nb_etab=kpis['nb_etablissements'],
        lignes_total=kpis['lignes_traitees'],
        alertes=alertes,
        freq_analyse=freq_analyse,
    )


# ─── INTERFACE PRINCIPALE ─────────────────────────────────────────────────────

def main():
    # Titre et description
    st.markdown("## 📊 ARIA-ND — Tableau de bord KPI Réseau de Distribution")
    st.markdown("""
    <div style="background:#E6F1FB;padding:10px 14px;border-radius:8px;border-left:4px solid #1F3864;margin-bottom:16px;font-size:13px;color:#0C447C">
    <strong>Indicateurs implémentés (tirés de l'affichage SQ 25-NS-374) :</strong>
    Taux de respect des niveaux de service · Performance des centres de distribution · 
    Nombre de lignes traitées · Fréquence de livraison optimale vs réelle · Narration IA automatique
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    st.sidebar.markdown("### ⚙️ Configuration")
    
    # Chargement des données
    csv_path = 'sample_kpis.csv'
    if not os.path.exists(csv_path):
        st.error(f"Fichier '{csv_path}' introuvable. Placer sample_kpis.csv dans le même répertoire.")
        st.stop()
    
    df = load_data(csv_path)
    semaines = sorted(df['Semaine'].unique())
    
    semaine_selectionnee = st.sidebar.selectbox(
        "Semaine de référence",
        semaines,
        index=len(semaines) - 1
    )
    
    etablissements = ['Tous'] + sorted(df['Etablissement'].unique().tolist())
    filtre_etab = st.sidebar.selectbox("Filtrer par établissement", etablissements)
    
    cible_override = st.sidebar.slider("Cible taux de service (%)", 90, 99, 96)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style="font-size:12px;color:#4A4A4A">
    <strong>ARIA-ND v1.0</strong><br>
    Candidature SQ 25-NS-374<br>
    Andrea Goran<br>
    github.com/[user]/ARIA-ND
    </div>
    """, unsafe_allow_html=True)
    
    # Calcul des KPIs
    kpis = compute_kpis(df, semaine_selectionnee)
    df_s = kpis['df_semaine'].copy()
    
    if filtre_etab != 'Tous':
        df_s = df_s[df_s['Etablissement'] == filtre_etab]
    
    # ── KPIs principaux ──────────────────────────────────────────────────────
    st.markdown(f"### Semaine {semaine_selectionnee} — Vue d'ensemble du réseau")
    
    col1, col2, col3, col4 = st.columns(4)
    
    taux_couleur = "normal" if kpis['taux_service_moyen'] >= cible_override else "inverse"
    col1.metric(
        "Taux de service moyen",
        f"{kpis['taux_service_moyen']:.1f}%",
        f"Cible : {cible_override}%",
        delta_color=taux_couleur
    )
    col2.metric("Lignes traitées", f"{kpis['lignes_traitees']:,}", "Total réseau")
    col3.metric(
        "Établissements sous cible",
        f"{kpis['nb_sous_cible']}/{kpis['nb_etablissements']}",
        delta_color="inverse"
    )
    col4.metric(
        "Écart fréquence livraison",
        f"{kpis['ecart_frequence']} liv. manquantes",
        "optimale vs réelle",
        delta_color="inverse" if kpis['ecart_frequence'] > 0 else "normal"
    )
    
    st.markdown("---")
    
    # ── Alertes ──────────────────────────────────────────────────────────────
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.markdown("#### 🔴 Alertes — Établissements sous la cible")
        sous_cible = df_s[df_s['Taux_service_reel'] < cible_override]
        if len(sous_cible) > 0:
            for _, row in sous_cible.iterrows():
                ecart = row['Taux_service_reel'] - cible_override
                st.markdown(f"""
                <div class="alert-red">
                <strong>{row['Etablissement']}</strong> — {row['Taux_service_reel']:.1f}% 
                ({ecart:.1f}% vs cible) · {row['Retards']} retards · {row['Lignes_traitees']:,} lignes
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-green">✅ Tous les établissements atteignent leur cible</div>', unsafe_allow_html=True)
    
    with col_right:
        st.markdown("#### 🚚 Fréquence de livraison — Optimale vs Réelle")
        df_freq = df_s[['Etablissement', 'Frequence_livraison_reelle', 'Frequence_livraison_optimale']].copy()
        df_freq['Écart'] = df_freq['Frequence_livraison_optimale'] - df_freq['Frequence_livraison_reelle']
        df_freq.columns = ['Établissement', 'Réelle', 'Optimale', 'Écart']
        
        def color_ecart(val):
            if val > 0: return 'color: #993C1D; font-weight: bold'
            elif val == 0: return 'color: #085041'
            return ''
        
        st.dataframe(
            df_freq.style.map(color_ecart, subset=['Écart']),
            hide_index=True,
            use_container_width=True
        )
    
    st.markdown("---")
    
    # ── Tableau de performance complet ───────────────────────────────────────
    st.markdown("#### 📋 Performance détaillée par établissement")
    
    df_display = df_s[['Etablissement', 'Lignes_traitees', 'Taux_service_reel',
                        'Taux_service_cible', 'Cout_par_livraison', 'Retards']].copy()
    df_display.columns = ['Établissement', 'Lignes traitées', 'Taux service %',
                           'Cible %', 'Coût/livraison $', 'Retards']
    
    def color_taux(row):
        styles = [''] * len(row)
        idx = list(row.index).index('Taux service %')
        cible_idx = list(row.index).index('Cible %')
        if row['Taux service %'] < row['Cible %']:
            styles[idx] = 'background-color: #FAECE7; color: #993C1D; font-weight: bold'
        else:
            styles[idx] = 'background-color: #E1F5EE; color: #085041'
        return styles
    
    st.dataframe(
        df_display.style.apply(color_taux, axis=1),
        hide_index=True,
        use_container_width=True
    )
    
    st.markdown("---")
    
    # ── Narration IA ─────────────────────────────────────────────────────────
    st.markdown("#### 🤖 Narration automatique — Rapport exécutif IA")
    
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        generer = st.button("🔄 Générer le rapport", type="primary", use_container_width=True)
    with col_info:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            st.markdown('<div style="font-size:12px;color:#085041">✅ API Azure OpenAI Canada East — rapport personnalisé</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:12px;color:#633806">ℹ️ Mode démo — rapport type (export ANTHROPIC_API_KEY=... pour activer l\'IA)</div>', unsafe_allow_html=True)
    
    if generer or True:  # Afficher automatiquement
        with st.spinner("Génération du rapport en cours..."):
            if api_key:
                narration = call_claude_narration(kpis, df_s)
                if not narration:
                    narration = generate_demo_narration(kpis, semaine_selectionnee)
            else:
                narration = generate_demo_narration(kpis, semaine_selectionnee)
        
        st.markdown(f'<div class="narration-box">{narration}</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="font-size:11px;color:#7A7A7A;text-align:center">
    ARIA-ND-KPI-Dashboard v1.0 · Développé par Andrea Goran · Candidature Santé Québec 25-NS-374<br>
    github.com/[user]/ARIA-ND · goran.andrea@yahoo.ca
    </div>
    """, unsafe_allow_html=True)


if __name__ == '__main__':
    main()
