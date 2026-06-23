"""
Benchmark stratégique personnalisé pour une mission consultant RH.
Deux modes :
  - Rapide  : 1 appel Claude (max_tokens=4096) — outil mission_benchmark
  - Approfondi : 3 appels Claude (max_tokens=8192) — outils mission_part_a/b/c
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

# Anthropic et Google Generative AI sont importés en lazy dans leurs fonctions d'appel

# ─────────────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT (dynamique — formaté à l'appel)
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_MISSION = """Tu es un expert senior en transformation RH et organisationnelle, associé chez LMS ORH — cabinet de conseil au Maroc & Afrique.

MISSION : Produire un benchmark RH factuel et actionnable pour la mission "{nom_mission}".
Entreprise cible : {entreprise_cible} — Secteur : {secteur} — Géographie : {geographie}
Question centrale : {angle_strategique_rh}
Référence comparative : {concurrent_reference}
(Si vide, compare aux leaders reconnus du secteur dans la géographie indiquée)

FILTRE RH OBLIGATOIRE PAR AXE :
1. BUSINESS MODEL → compétences émergentes/obsolètes, nouveaux profils, impacts pyramide des âges
2. ORGANISATION → évolution effectifs, nouveaux modèles org (agile, matriciel, plateforme), rôles créés/supprimés/transformés
3. GOUVERNANCE → instances RH (CODIR, comités sociaux), politiques sociales, conformité droit du travail
4. INNOVATION MANAGÉRIALE → pratiques différenciantes, outils RH innovants (IA RH, SIRH, analytics), expérience employé

RÈGLES ABSOLUES — NON NÉGOCIABLES :
1. Chaque axe cite OBLIGATOIREMENT au moins 2 chiffres récents (année ≥ 2023) avec leur source [N]
2. Chaque axe nomme OBLIGATOIREMENT au moins 2 entreprises réelles du secteur avec un fait précis
3. Chaque "So what ?" est SPÉCIFIQUE à {entreprise_cible} — jamais générique
4. Si "concurrent_reference" est renseigné, une comparaison explicite apparaît dans chaque axe
5. INTERDIT : "a tendance à", "doit mettre en place", "les entreprises du secteur généralement" sans fait concret issu des sources
6. Commence chaque axe par un chiffre clé ou un fait vérifiable
7. Champ "analyse" : 3-4 phrases MAX — format PPT consultant, pas un article de fond. Chaque phrase = 1 fait + 1 implication.
8. INTERDIT dans les champs texte : NE PAS écrire [confirmé], [probable] ou [à vérifier] — ce sont des notes internes, pas du texte livrable.
9. Les chiffres macro-économiques généraux (PIB, inflation, taux directeur) ne doivent apparaître QUE dans le slide Contexte — pas répétés dans chaque axe.
10. Langue : français, registre consultant senior"""


SYSTEM_PROMPT_MISSION_ORG = """Tu es un expert senior en transformation organisationnelle et gouvernance opérationnelle, associé chez LMS ORH — cabinet de conseil au Maroc & Afrique.

MISSION : Produire un benchmark organisationnel factuel et actionnable pour la mission "{nom_mission}".
Entreprise cible : {entreprise_cible} — Secteur : {secteur} — Géographie : {geographie}
Question centrale : {angle_strategique_rh}
Référence comparative : {concurrent_reference}
(Si vide, compare aux leaders reconnus du secteur dans la géographie indiquée)

AXES OBLIGATOIRES :
1. MODÈLES CSP — Structures et gouvernance des centres de prestation partagés comparables (taille, périmètre fonctionnel délégué, positionnement hiérarchique)
2. PROCESSUS DOUANIERS — Best practices de gestion des processus import/export et douaniers (procédures, habilitations, outils, points de contrôle, risques)
3. INTERFACE FILIALE/SIÈGE — Modèles de relation entre CSP filiale et siège Groupe (niveaux d'autonomie, reporting, délégations, protocoles de validation)
4. FORMALISATION & AUDIT-READINESS — Pratiques de documentation (RACI, fiches de fonctions, référentiels), niveaux de maturité opérationnelle, critères d'un audit interne Groupe réussi

RÈGLES ABSOLUES — NON NÉGOCIABLES :
1. Chaque axe cite OBLIGATOIREMENT au moins 2 chiffres récents (année ≥ 2023) avec leur source [N]
2. Chaque axe nomme OBLIGATOIREMENT au moins 2 organisations/entreprises réelles avec un fait précis
3. Chaque "So what ?" cible DEUX HORIZONS pour {entreprise_cible} : court terme (avant audit Groupe) + moyen terme (évolution structurelle)
4. Si "concurrent_reference" est renseigné, une comparaison explicite apparaît dans chaque axe
5. INTERDIT : généraliser sans fait concret issu des sources
6. Commence chaque axe par un fait vérifiable ou une donnée chiffrée
7. Champ "analyse" : 3-4 phrases MAX — format PPT consultant, pas un article de fond. Chaque phrase = 1 fait + 1 implication.
8. INTERDIT dans les champs texte : NE PAS écrire [confirmé], [probable] ou [à vérifier] — ce sont des notes internes, jamais dans le texte livrable.
9. Les chiffres macro-économiques généraux (PIB, inflation, taux directeur) ne doivent apparaître QUE dans le slide Contexte — pas répétés dans chaque axe.
10. Langue : français, registre consultant senior"""


# ─────────────────────────────────────────────────────────────────────────────
#  PROMPTS SPÉCIFIQUES PAR SLIDE OPTIONNELLE
# ─────────────────────────────────────────────────────────────────────────────

PROMPTS_SLIDES_OPTIONNELLES = {
    "effectifs_dimensionnement": (
        "Effectifs & dimensionnement — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Effectif moyen des acteurs du secteur de taille similaire à {entreprise_cible}\n"
        "- Ratio cadres / non-cadres observé dans le secteur\n"
        "- Tendance des effectifs sur 3 ans (croissance / réduction / stabilité)\n"
        "- Fonctions externalisées vs internalisées les plus fréquentes\n"
        "- Benchmark avec {concurrent_reference} si disponible\n"
        "Cite tes sources [N] et l'année de chaque donnée. INTERDIT d'inventer des chiffres."
    ),
    "recrutement_talent": (
        "Recrutement & talent acquisition — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Délai moyen de recrutement (time-to-hire) dans le secteur\n"
        "- Top 3 postes en tension (difficiles à recruter en 2024-2025)\n"
        "- Canaux de recrutement privilégiés par les leaders du secteur\n"
        "- Fourchettes salariales pour 3 profils RH clés\n"
        "- Pratique innovante de recrutement observée chez un acteur nommé\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
    "formation_competences": (
        "Formation & développement des compétences — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Budget formation moyen (% masse salariale) dans le secteur\n"
        "- Compétences prioritaires financées en formation (top 5 en 2024-2025)\n"
        "- Modalités dominantes : présentiel, e-learning, blended, coaching\n"
        "- Exemple d'académie interne ou programme phare d'un acteur nommé\n"
        "- Réglementations formation applicables en {geographie}\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
    "culture_engagement": (
        "Culture organisationnelle & engagement — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Taux d'engagement moyen dans le secteur (si données disponibles)\n"
        "- Pratiques de reconnaissance et fidélisation observées\n"
        "- Classements Great Place to Work ou équivalent dans le secteur\n"
        "- Exemple concret de transformation culturelle réussie (acteur nommé + résultats mesurés)\n"
        "- Principaux facteurs de démission identifiés dans le secteur\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
    "remuneration_social": (
        "Rémunération & politique sociale — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Fourchettes de rémunération pour 3 postes RH de référence\n"
        "- Avantages sociaux différenciants observés dans le secteur\n"
        "- Politique d'intéressement / participation / actionnariat si applicable\n"
        "- Évolution des salaires sur 2 ans dans le secteur\n"
        "- Comparaison rémunération fixe vs variable (mix observé)\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
    "sirh_digitalisation": (
        "SIRH & digitalisation RH — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Solutions SIRH les plus déployées dans le secteur (top 3 avec % adoption)\n"
        "- Use cases IA RH déjà déployés chez des acteurs nommés\n"
        "- ROI ou bénéfices mesurés après déploiement SIRH (si données)\n"
        "- Obstacles à la digitalisation RH identifiés dans le secteur\n"
        "- Benchmark {concurrent_reference} sur la maturité digitale RH\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
    "diversite_inclusion": (
        "Diversité, équité & inclusion — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Taux de féminisation des postes de direction dans le secteur\n"
        "- Engagements DEI formalisés par les leaders du secteur\n"
        "- Réglementations DEI applicables en {geographie}\n"
        "- Exemple de programme DEI reconnu (acteur nommé + indicateurs)\n"
        "- Indicateurs DEI suivis par les entreprises les plus avancées\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
    "relations_sociales": (
        "Relations sociales & dialogue social — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Taux de syndicalisation moyen dans le secteur\n"
        "- Principaux accords collectifs récents dans le secteur (2023-2025)\n"
        "- Conflits sociaux notables si applicable\n"
        "- Pratiques de dialogue social innovantes (acteur nommé)\n"
        "- Cadre légal du dialogue social applicable en {geographie}\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
}

PROMPTS_SLIDES_ORG = {
    "supply_chain_interne": (
        "Supply chain & flux internes — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Modèles de coordination entre CSP filiale et usine/production observés\n"
        "- Outils de gestion des flux utilisés dans des structures similaires\n"
        "- Indicateurs de performance supply chain typiques (taux de service, délais)\n"
        "- Exemple concret d'optimisation réussie (acteur nommé + résultats mesurés)\n"
        "- Points de friction les plus fréquents et solutions adoptées\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
    "gouvernance_financiere": (
        "Gouvernance financière & contrôle interne — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Modèles de contrôle financier dans les CSP filiales (délégations, seuils de validation)\n"
        "- Pratiques de reporting financier filiale/siège observées\n"
        "- Outils et systèmes financiers les plus déployés (ERP, consolidation)\n"
        "- Pratiques de prévention des risques financiers et de fraude\n"
        "- Benchmark {concurrent_reference} si disponible\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
    "conformite_reglementaire": (
        "Conformité réglementaire douanière & fiscale — recherche et fournis pour [{geographie}] :\n"
        "- Cadre légal douanier marocain applicable (Code des douanes, agréments OEA, CTS)\n"
        "- Évolutions réglementaires récentes (2023-2025) impactant l'import/export\n"
        "- Risques de non-conformité les plus fréquents et sanctions observées\n"
        "- Pratiques de conformité proactive adoptées par des acteurs leaders\n"
        "- Exigences spécifiques pour les filiales de groupes internationaux au Maroc\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
    "matrice_risques": (
        "Risques opérationnels — recherche et fournis pour [{secteur}] / [{geographie}] :\n"
        "- Top 5 risques opérationnels identifiés dans des CSP similaires\n"
        "- Risques spécifiques aux processus douaniers et import/export\n"
        "- Pratiques de cartographie et de mitigation des risques observées\n"
        "- Exemple de crise/incident opérationnel géré (acteur nommé + leçons tirées)\n"
        "- Indicateurs de risque (KRI) typiquement suivis dans le secteur\n"
        "Cite tes sources [N] et l'année de chaque donnée."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
#  OUTIL MODE RAPIDE
# ─────────────────────────────────────────────────────────────────────────────

TOOL_MISSION_RAPIDE = {
    "name": "mission_benchmark",
    "description": "Stocke le benchmark RH stratégique complet pour la mission.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contexte_mission": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "angle_rh": {"type": "string"},
                },
                "required": ["texte", "angle_rh"],
            },
            "business_model_rh": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "competences_emergentes": {"type": "array", "items": {"type": "string"}},
                    "competences_obsoletes": {"type": "array", "items": {"type": "string"}},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "competences_emergentes", "competences_obsoletes", "so_what"],
            },
            "organisation_dimensionnement": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "tendances_effectifs": {"type": "string"},
                    "nouveaux_roles": {"type": "array", "items": {"type": "string"}},
                    "externalisation": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "tendances_effectifs", "nouveaux_roles", "externalisation", "so_what"],
            },
            "gouvernance_rh": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "instances_rh": {"type": "string"},
                    "politiques_sociales": {"type": "string"},
                    "conformite": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "instances_rh", "politiques_sociales", "conformite", "so_what"],
            },
            "innovation_manageriale": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "pratiques_differenciantes": {"type": "array", "items": {"type": "string"}},
                    "outils_rh": {"type": "array", "items": {"type": "string"}},
                    "experience_employe": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "pratiques_differenciantes", "outils_rh", "experience_employe", "so_what"],
            },
            "signaux_faibles": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "signal": {"type": "string"},
                        "implication_rh": {"type": "string"},
                        "horizon": {"type": "string"},
                        "pertinence_mission": {"type": "string"},
                    },
                    "required": ["signal", "implication_rh", "horizon", "pertinence_mission"],
                },
            },
            "recommandations_mission": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "justification": {"type": "string"},
                        "priorite": {"type": "string", "enum": ["Haute", "Moyenne", "Faible"]},
                        "kpi": {"type": "string"},
                        "horizon": {"type": "string"},
                    },
                    "required": ["action", "justification", "priorite", "kpi", "horizon"],
                },
            },
            "slides_optionnelles": {
                "type": "array",
                "description": "Slides thématiques optionnelles demandées (1 item par thème coché)",
                "items": {
                    "type": "object",
                    "properties": {
                        "cle": {"type": "string"},
                        "titre": {"type": "string"},
                        "observation": {"type": "string"},
                        "benchmark_sectoriel": {"type": "string"},
                        "implication_rh": {"type": "string"},
                        "so_what": {"type": "string"},
                    },
                    "required": ["cle", "titre", "observation", "benchmark_sectoriel", "implication_rh", "so_what"],
                },
            },
        },
            "index_sources": {
                "type": "array",
                "description": "Index de toutes les sources citées dans le benchmark",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "titre": {"type": "string"},
                        "source": {"type": "string"},
                        "url": {"type": "string"},
                        "date": {"type": "string"},
                        "pertinence": {"type": "string", "enum": ["Directe", "Contextuelle"]},
                    },
                    "required": ["id", "titre", "source", "pertinence"],
                },
            },
        "required": [
            "contexte_mission",
            "business_model_rh",
            "organisation_dimensionnement",
            "gouvernance_rh",
            "innovation_manageriale",
            "signaux_faibles",
            "recommandations_mission",
            "slides_optionnelles",
            "index_sources",
        ],
    },
}

TOOL_MISSION_ORG_RAPIDE = {
    "name": "mission_benchmark_org",
    "description": "Stocke le benchmark organisationnel et processus pour la mission.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contexte_mission": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "angle_organisationnel": {"type": "string"},
                },
                "required": ["texte", "angle_organisationnel"],
            },
            "modeles_csp": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "structures_types": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Types de structures CSP observés dans le secteur/géographie",
                    },
                    "gouvernance_observee": {"type": "string"},
                    "perimetre_fonctionnel": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "structures_types", "gouvernance_observee", "perimetre_fonctionnel", "so_what"],
            },
            "processus_douaniers": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "bonnes_pratiques": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Best practices de gestion douanière import/export",
                    },
                    "outils_systemes": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Outils et systèmes utilisés (ERP, douane, plateformes)",
                    },
                    "risques_frequents": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Risques opérationnels douaniers les plus fréquents",
                    },
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "bonnes_pratiques", "outils_systemes", "risques_frequents", "so_what"],
            },
            "interface_filiale_siege": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "modeles_delegation": {"type": "string"},
                    "protocoles_validation": {"type": "string"},
                    "reporting_type": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "modeles_delegation", "protocoles_validation", "reporting_type", "so_what"],
            },
            "formalisation_audit_readiness": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "niveaux_maturite": {"type": "string"},
                    "referentiels_utilises": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Référentiels et standards utilisés (RACI, ISO, normes Groupe)",
                    },
                    "criteres_audit_groupe": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Critères typiques d'un audit interne Groupe",
                    },
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "niveaux_maturite", "referentiels_utilises", "criteres_audit_groupe", "so_what"],
            },
            "signaux_faibles": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "signal": {"type": "string"},
                        "implication_organisationnelle": {"type": "string"},
                        "horizon": {"type": "string"},
                        "pertinence_mission": {"type": "string"},
                    },
                    "required": ["signal", "implication_organisationnelle", "horizon", "pertinence_mission"],
                },
            },
            "recommandations_mission": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "justification": {"type": "string"},
                        "priorite": {"type": "string", "enum": ["Haute", "Moyenne", "Faible"]},
                        "kpi": {"type": "string"},
                        "horizon": {"type": "string"},
                    },
                    "required": ["action", "justification", "priorite", "kpi", "horizon"],
                },
            },
            "slides_optionnelles": {
                "type": "array",
                "description": "Slides thématiques optionnelles",
                "items": {
                    "type": "object",
                    "properties": {
                        "cle": {"type": "string"},
                        "titre": {"type": "string"},
                        "observation": {"type": "string"},
                        "benchmark_sectoriel": {"type": "string"},
                        "implication_rh": {"type": "string"},
                        "so_what": {"type": "string"},
                    },
                    "required": ["cle", "titre", "observation", "benchmark_sectoriel", "implication_rh", "so_what"],
                },
            },
        },
            "index_sources": {
                "type": "array",
                "description": "Index de toutes les sources citées dans le benchmark",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "titre": {"type": "string"},
                        "source": {"type": "string"},
                        "url": {"type": "string"},
                        "date": {"type": "string"},
                        "pertinence": {"type": "string", "enum": ["Directe", "Contextuelle"]},
                    },
                    "required": ["id", "titre", "source", "pertinence"],
                },
            },
        "required": [
            "contexte_mission", "modeles_csp", "processus_douaniers",
            "interface_filiale_siege", "formalisation_audit_readiness",
            "signaux_faibles", "recommandations_mission", "slides_optionnelles",
            "index_sources",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  OUTILS MODE APPROFONDI
# ─────────────────────────────────────────────────────────────────────────────

TOOL_MISSION_PART_A = {
    "name": "mission_part_a",
    "description": "Partie A : contexte_mission, business_model_rh, organisation_dimensionnement.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contexte_mission": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "angle_rh": {"type": "string"},
                },
                "required": ["texte", "angle_rh"],
            },
            "business_model_rh": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "competences_emergentes": {"type": "array", "items": {"type": "string"}},
                    "competences_obsoletes": {"type": "array", "items": {"type": "string"}},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "competences_emergentes", "competences_obsoletes", "so_what"],
            },
            "organisation_dimensionnement": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "tendances_effectifs": {"type": "string"},
                    "nouveaux_roles": {"type": "array", "items": {"type": "string"}},
                    "externalisation": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "tendances_effectifs", "nouveaux_roles", "externalisation", "so_what"],
            },
        },
        "required": ["contexte_mission", "business_model_rh", "organisation_dimensionnement"],
    },
}

TOOL_MISSION_ORG_PART_A = {
    "name": "mission_org_part_a",
    "description": "Partie A Org : contexte_mission, modeles_csp, processus_douaniers.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contexte_mission": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "angle_organisationnel": {"type": "string"},
                },
                "required": ["texte", "angle_organisationnel"],
            },
            "modeles_csp": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "structures_types": {"type": "array", "items": {"type": "string"}},
                    "gouvernance_observee": {"type": "string"},
                    "perimetre_fonctionnel": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "structures_types", "gouvernance_observee", "perimetre_fonctionnel", "so_what"],
            },
            "processus_douaniers": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "bonnes_pratiques": {"type": "array", "items": {"type": "string"}},
                    "outils_systemes": {"type": "array", "items": {"type": "string"}},
                    "risques_frequents": {"type": "array", "items": {"type": "string"}},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "bonnes_pratiques", "outils_systemes", "risques_frequents", "so_what"],
            },
        },
        "required": ["contexte_mission", "modeles_csp", "processus_douaniers"],
    },
}

TOOL_MISSION_PART_B = {
    "name": "mission_part_b",
    "description": "Partie B : gouvernance_rh, innovation_manageriale, signaux_faibles.",
    "input_schema": {
        "type": "object",
        "properties": {
            "gouvernance_rh": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "instances_rh": {"type": "string"},
                    "politiques_sociales": {"type": "string"},
                    "conformite": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "instances_rh", "politiques_sociales", "conformite", "so_what"],
            },
            "innovation_manageriale": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "pratiques_differenciantes": {"type": "array", "items": {"type": "string"}},
                    "outils_rh": {"type": "array", "items": {"type": "string"}},
                    "experience_employe": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "pratiques_differenciantes", "outils_rh", "experience_employe", "so_what"],
            },
            "signaux_faibles": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "signal": {"type": "string"},
                        "implication_rh": {"type": "string"},
                        "horizon": {"type": "string"},
                        "pertinence_mission": {"type": "string"},
                    },
                    "required": ["signal", "implication_rh", "horizon", "pertinence_mission"],
                },
            },
        },
        "required": ["gouvernance_rh", "innovation_manageriale", "signaux_faibles"],
    },
}

TOOL_MISSION_ORG_PART_B = {
    "name": "mission_org_part_b",
    "description": "Partie B Org : interface_filiale_siege, formalisation_audit_readiness, signaux_faibles.",
    "input_schema": {
        "type": "object",
        "properties": {
            "interface_filiale_siege": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "modeles_delegation": {"type": "string"},
                    "protocoles_validation": {"type": "string"},
                    "reporting_type": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "modeles_delegation", "protocoles_validation", "reporting_type", "so_what"],
            },
            "formalisation_audit_readiness": {
                "type": "object",
                "properties": {
                    "analyse": {"type": "string"},
                    "niveaux_maturite": {"type": "string"},
                    "referentiels_utilises": {"type": "array", "items": {"type": "string"}},
                    "criteres_audit_groupe": {"type": "array", "items": {"type": "string"}},
                    "so_what": {"type": "string"},
                },
                "required": ["analyse", "niveaux_maturite", "referentiels_utilises", "criteres_audit_groupe", "so_what"],
            },
            "signaux_faibles": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "signal": {"type": "string"},
                        "implication_organisationnelle": {"type": "string"},
                        "horizon": {"type": "string"},
                        "pertinence_mission": {"type": "string"},
                    },
                    "required": ["signal", "implication_organisationnelle", "horizon", "pertinence_mission"],
                },
            },
        },
        "required": ["interface_filiale_siege", "formalisation_audit_readiness", "signaux_faibles"],
    },
}


def _build_tool_part_c(slides_optionnelles: List[str]) -> Dict:
    """Construit l'outil mission_part_c dynamiquement selon les slides cochées."""
    slides_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "cle": {"type": "string", "description": "Identifiant de la slide optionnelle"},
                "titre": {"type": "string"},
                "observation": {"type": "string"},
                "benchmark_sectoriel": {"type": "string"},
                "implication_rh": {"type": "string"},
                "so_what": {"type": "string"},
            },
            "required": ["cle", "titre", "observation", "benchmark_sectoriel", "implication_rh", "so_what"],
        },
    }

    return {
        "name": "mission_part_c",
        "description": "Partie C : recommandations_mission, slides_optionnelles, index_sources.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recommandations_mission": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "justification": {"type": "string"},
                            "priorite": {"type": "string", "enum": ["Haute", "Moyenne", "Faible"]},
                            "kpi": {"type": "string"},
                            "horizon": {"type": "string"},
                        },
                        "required": ["action", "justification", "priorite", "kpi", "horizon"],
                    },
                },
                "slides_optionnelles": slides_schema,
                "index_sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "titre": {"type": "string"},
                            "source": {"type": "string"},
                            "url": {"type": "string"},
                            "date": {"type": "string"},
                            "pertinence": {"type": "string", "enum": ["Directe", "Contextuelle"]},
                        },
                        "required": ["id", "titre", "source", "pertinence"],
                    },
                },
            },
            "required": ["recommandations_mission", "slides_optionnelles", "index_sources"],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS (calqués sur analyzer.py)
# ─────────────────────────────────────────────────────────────────────────────

def _format_articles(articles: List[Dict], summary_len: int = 400) -> str:
    lines = [f"## {len(articles)} sources numérotées — citer via [N]\n"]
    for i, a in enumerate(articles, 1):
        date = a.get("date", "N/A")
        age = ""
        if date != "N/A":
            try:
                months = (datetime.now() - datetime.fromisoformat(date)).days // 30
                age = f" ({months}m)"
            except Exception:
                pass
        lines.append(f"[{i}] {a['source']} {date}{age} | {a['title']}")
        if a.get("summary"):
            lines.append(f"     {a['summary'][:summary_len]}")
        lines.append("")
    return "\n".join(lines)


def _call_anthropic(client, model: str, max_tokens: int, system_text: str,
                    tool: dict, tool_name: str, user_prompt: str) -> dict:
    """Appel Anthropic avec tool_use pour sortie JSON structurée."""
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": enriched_prompt}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == tool_name:
            logger.info(
                f"{tool_name} (Anthropic) — {resp.usage.input_tokens} in / "
                f"{resp.usage.output_tokens} out "
                f"(cache: {getattr(resp.usage, 'cache_read_input_tokens', 0)})"
            )
            return block.input
    raise RuntimeError(f"Anthropic n'a pas retourné de résultat pour {tool_name}.")


def _call_gemini(model_name: str, max_tokens: int, system_text: str,
                 tool: dict, tool_name: str, user_prompt: str) -> dict:
    """Appel Google Gemini avec JSON mode (google-genai SDK v2+)."""
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise ImportError(
            "google-genai non installé. "
            "Exécuter : pip install google-genai>=1.0.0"
        )

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY manquant. Ajoutez GEMINI_API_KEY dans le fichier .env "
            "(obtenir sur https://aistudio.google.com/app/apikey)."
        )

    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1beta"},
    )

    schema = tool.get("input_schema", {})

    combined_prompt = (
        f"{system_text}\n\n"
        f"⚠️ CONCISION : chaque champ texte = 1-2 phrases max. Listes : 3-5 items max.\n\n"
        f"{user_prompt}"
    )

    response = client.models.generate_content(
        model=model_name,
        contents=combined_prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=max_tokens,
            temperature=0.3,
        ),
    )

    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    result = json.loads(raw)
    logger.info(f"{tool_name} (Gemini/{model_name}) — réponse JSON reçue")
    return result


_GROQ_OUTPUT_FORMAT = """\
Tu dois retourner un objet JSON valide avec exactement ces clés.
Chaque champ entre [crochets] doit être remplacé par du contenu réel et substantiel (jamais vide).

{
  "contexte_mission": {
    "texte": "[3-4 phrases sur le contexte sectoriel, les dynamiques de marché, les chiffres clés du secteur avec sources]",
    "angle_rh": "[2-3 phrases sur les enjeux RH spécifiques de l'angle stratégique de la mission]"
  },
  "business_model_rh": {
    "analyse": "[3-4 phrases analysant le business model sous l'angle RH : impacts sur les compétences, les métiers, la pyramide des âges — citer au moins 1 chiffre et 1 entreprise réelle]",
    "competences_emergentes": ["[compétence émergente 1]", "[compétence émergente 2]", "[compétence émergente 3]"],
    "competences_obsoletes": ["[compétence obsolète 1]", "[compétence obsolète 2]"],
    "so_what": "[2-3 phrases sur les implications directes pour l'entreprise cible]"
  },
  "organisation_dimensionnement": {
    "analyse": "[3-4 phrases sur l'organisation et le dimensionnement RH dans le secteur — effectifs, structures, modèles]",
    "tendances_effectifs": "[2-3 phrases sur les tendances d'évolution des effectifs dans le secteur avec chiffres]",
    "nouveaux_roles": ["[nouveau rôle 1]", "[nouveau rôle 2]", "[nouveau rôle 3]"],
    "externalisation": "[2 phrases sur les pratiques d'externalisation observées dans le secteur]",
    "so_what": "[2-3 phrases sur les implications directes pour l'entreprise cible]"
  },
  "gouvernance_rh": {
    "analyse": "[3-4 phrases sur la gouvernance RH dans le secteur : instances, politiques, conformité]",
    "instances_rh": "[2 phrases sur les instances RH (CODIR, comités sociaux) observées dans le secteur]",
    "politiques_sociales": "[2 phrases sur les politiques sociales et avantages observés dans le secteur]",
    "conformite": "[2 phrases sur la conformité réglementaire RH dans la géographie ciblée]",
    "so_what": "[2-3 phrases sur les implications directes pour l'entreprise cible]"
  },
  "innovation_manageriale": {
    "analyse": "[3-4 phrases sur l'innovation managériale et les pratiques RH innovantes dans le secteur]",
    "pratiques_differenciantes": ["[pratique 1]", "[pratique 2]", "[pratique 3]"],
    "outils_rh": ["[outil RH 1]", "[outil RH 2]", "[outil RH 3]"],
    "experience_employe": "[2-3 phrases sur l'expérience employé dans le secteur avec exemples concrets]",
    "so_what": "[2-3 phrases sur les implications directes pour l'entreprise cible]"
  },
  "signaux_faibles": [
    {
      "signal": "[signal faible 1 — tendance émergente non encore mainstream]",
      "implication_rh": "[implication RH de ce signal]",
      "horizon": "[court / moyen / long terme]",
      "pertinence_mission": "[en quoi ce signal est pertinent pour la mission]"
    },
    {
      "signal": "[signal faible 2]",
      "implication_rh": "[implication RH]",
      "horizon": "[horizon]",
      "pertinence_mission": "[pertinence]"
    }
  ],
  "recommandations_mission": [
    {
      "action": "[recommandation 1 — action concrète et spécifique]",
      "justification": "[pourquoi cette action, appuyé sur les faits du benchmark]",
      "priorite": "Haute",
      "kpi": "[indicateur de mesure de succès]",
      "horizon": "[ex : 6 mois, 12 mois, 18 mois]"
    },
    {
      "action": "[recommandation 2]",
      "justification": "[justification]",
      "priorite": "Moyenne",
      "kpi": "[kpi]",
      "horizon": "[horizon]"
    },
    {
      "action": "[recommandation 3]",
      "justification": "[justification]",
      "priorite": "Moyenne",
      "kpi": "[kpi]",
      "horizon": "[horizon]"
    }
  ],
  "slides_optionnelles": [],
  "index_sources": [
    {"id": 1, "titre": "[titre de la source 1]", "source": "[nom du média/rapport]", "url": "[url si disponible]", "date": "[date YYYY-MM]", "pertinence": "Directe"},
    {"id": 2, "titre": "[titre de la source 2]", "source": "[nom du média/rapport]", "url": "", "date": "[date YYYY-MM]", "pertinence": "Contextuelle"}
  ]
}
"""

_GROQ_OUTPUT_FORMAT_ORG = """\
Tu dois retourner un objet JSON valide avec exactement ces clés.
Chaque champ entre [crochets] doit être remplacé par du contenu réel et substantiel (jamais vide).

{
  "contexte_mission": {
    "texte": "[3-4 phrases sur le contexte sectoriel, les dynamiques de marché, les enjeux organisationnels avec chiffres clés]",
    "angle_organisationnel": "[2-3 phrases sur l'angle organisationnel central de la mission]"
  },
  "modeles_csp": {
    "analyse": "[3-4 phrases analysant les modèles CSP comparables — citer 1 chiffre et 2 entreprises réelles]",
    "structures_types": ["[type CSP 1]", "[type CSP 2]", "[type CSP 3]"],
    "gouvernance_observee": "[2-3 phrases sur les pratiques de gouvernance dans des CSP similaires]",
    "perimetre_fonctionnel": "[2 phrases sur le périmètre fonctionnel typiquement délégué]",
    "so_what": "[court terme : ce qu'il faut avant l'audit Groupe] [moyen terme : évolution structurelle cible]"
  },
  "processus_douaniers": {
    "analyse": "[3-4 phrases sur les best practices douanières — citer 1 chiffre et 2 acteurs nommés]",
    "bonnes_pratiques": ["[bonne pratique 1]", "[bonne pratique 2]", "[bonne pratique 3]"],
    "outils_systemes": ["[outil 1]", "[outil 2]"],
    "risques_frequents": ["[risque 1]", "[risque 2]", "[risque 3]"],
    "so_what": "[court terme : priorité avant audit] [moyen terme : sécurisation des processus]"
  },
  "interface_filiale_siege": {
    "analyse": "[3-4 phrases sur les modèles d'interface filiale/siège observés]",
    "modeles_delegation": "[2-3 phrases sur les niveaux de délégation et d'autonomie observés]",
    "protocoles_validation": "[2 phrases sur les protocoles de validation typiques]",
    "reporting_type": "[2 phrases sur les pratiques de reporting filiale/siège]",
    "so_what": "[court terme : clarifications urgentes] [moyen terme : formalisation des interfaces]"
  },
  "formalisation_audit_readiness": {
    "analyse": "[3-4 phrases sur les pratiques de formalisation et la maturité opérationnelle]",
    "niveaux_maturite": "[2-3 phrases sur les niveaux de maturité observés dans des structures similaires]",
    "referentiels_utilises": ["[référentiel 1]", "[référentiel 2]"],
    "criteres_audit_groupe": ["[critère audit 1]", "[critère audit 2]", "[critère audit 3]"],
    "so_what": "[court terme : livrables à préparer avant l'audit] [moyen terme : maturité cible]"
  },
  "signaux_faibles": [
    {
      "signal": "[signal faible 1 — tendance émergente dans la gouvernance des CSP]",
      "implication_organisationnelle": "[implication organisationnelle concrète]",
      "horizon": "[court / moyen / long terme]",
      "pertinence_mission": "[en quoi ce signal est pertinent pour la mission]"
    },
    {
      "signal": "[signal faible 2]",
      "implication_organisationnelle": "[implication]",
      "horizon": "[horizon]",
      "pertinence_mission": "[pertinence]"
    }
  ],
  "recommandations_mission": [
    {
      "action": "[recommandation 1 — action prioritaire avant audit Groupe]",
      "justification": "[pourquoi, basé sur le benchmark]",
      "priorite": "Haute",
      "kpi": "[indicateur de succès]",
      "horizon": "[ex : avant juillet 2026]"
    },
    {
      "action": "[recommandation 2]",
      "justification": "[justification]",
      "priorite": "Moyenne",
      "kpi": "[kpi]",
      "horizon": "[horizon]"
    },
    {
      "action": "[recommandation 3]",
      "justification": "[justification]",
      "priorite": "Moyenne",
      "kpi": "[kpi]",
      "horizon": "[horizon]"
    }
  ],
  "slides_optionnelles": [],
  "index_sources": [
    {"id": 1, "titre": "[titre CSP ou douane source 1]", "source": "[nom du média/rapport]", "url": "[url si disponible]", "date": "[date YYYY-MM]", "pertinence": "Directe"},
    {"id": 2, "titre": "[titre source 2]", "source": "[nom]", "url": "", "date": "[date]", "pertinence": "Contextuelle"}
  ]
}
"""


def _check_empty(data: dict) -> tuple[bool, int, int]:
    """Retourne (est_vide, nb_champs_vides, nb_champs_total) pour les champs texte imbriqués."""
    TEXT_KEYS = {"texte", "analyse", "so_what", "tendances_effectifs",
                 "instances_rh", "politiques_sociales", "conformite",
                 "externalisation", "experience_employe", "signal",
                 "implication_rh", "action", "justification",
                 # type Organisationnel
                 "angle_organisationnel", "gouvernance_observee", "perimetre_fonctionnel",
                 "modeles_delegation", "protocoles_validation", "reporting_type",
                 "niveaux_maturite", "implication_organisationnelle",
                 }
    empty, total = 0, 0
    def _walk(obj):
        nonlocal empty, total
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in TEXT_KEYS and isinstance(v, str):
                    total += 1
                    if not v.strip() or v.strip().startswith("[") or len(v.strip()) < 30:
                        empty += 1
                else:
                    _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)
    _walk(data)
    is_empty = total > 0 and (empty / total) > 0.4
    return is_empty, empty, total


def _call_groq(model_name: str, max_tokens: int, system_text: str,
               tool: dict, tool_name: str, user_prompt: str,
               output_format: str = None) -> dict:
    """
    Appel Groq avec JSON mode.
    Utilise une description humaine des champs (pas le schéma JSON brut)
    pour éviter que le modèle 'remplisse le template' avec des chaînes vides.
    output_format : gabarit JSON humain à utiliser (défaut : _GROQ_OUTPUT_FORMAT).
    """
    try:
        from groq import Groq
    except ImportError:
        raise ImportError("groq non installé. Exécuter : pip install groq>=0.9.0")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY manquant. Ajoutez votre clé dans le fichier .env.")

    client = Groq(api_key=api_key)

    fmt = output_format if output_format is not None else _GROQ_OUTPUT_FORMAT
    system_final = (
        f"{system_text}\n\n"
        f"FORMAT DE RÉPONSE :\n"
        f"{fmt}\n"
        f"RAPPEL : Remplace TOUS les textes entre [crochets] par du vrai contenu. "
        f"Ne retourne pas de crochets dans ta réponse. "
        f"Chaque champ texte = minimum 2 phrases avec des faits concrets."
    )

    last_error = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_final},
                    {"role": "user",   "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                temperature=0.4 + attempt * 0.1,
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)
            in_tok  = response.usage.prompt_tokens
            out_tok = response.usage.completion_tokens
            logger.info(
                f"{tool_name} (Groq/{model_name}) tentative {attempt+1} — "
                f"{in_tok} in / {out_tok} out"
            )
            is_empty, n_empty, n_total = _check_empty(result)
            logger.info(f"  → champs vides : {n_empty}/{n_total}")
            if is_empty:
                logger.warning(
                    f"Réponse Groq majoritairement vide ({n_empty}/{n_total}) — "
                    f"{'retry…' if attempt == 0 else 'on garde quand même.'}"
                )
                if attempt == 0:
                    continue
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"Groq tentative {attempt+1} échouée : {e}")
            if attempt == 0:
                continue

    raise RuntimeError(
        f"Groq n'a pas produit de résultat utilisable après 2 tentatives. "
        f"Dernière erreur : {last_error}"
    )


def _call_llm(provider: str, model: str, max_tokens: int, system_text: str,
              tool: dict, tool_name: str, user_prompt: str,
              client=None, output_format: str = None) -> dict:
    """Dispatcher : appelle Anthropic, Gemini ou Groq selon le provider."""
    if provider == "gemini":
        return _call_gemini(model, max_tokens, system_text, tool, tool_name, user_prompt)
    elif provider == "groq":
        return _call_groq(model, max_tokens, system_text, tool, tool_name, user_prompt,
                          output_format=output_format)
    else:
        if client is None:
            raise ValueError("client Anthropic requis pour provider='anthropic'.")
        return _call_anthropic(client, model, max_tokens, system_text, tool, tool_name, user_prompt)


def _tmp_path(reports_dir: Path, entreprise: str, part: str) -> Path:
    safe = "".join(c if c.isalnum() else "_" for c in entreprise)
    return reports_dir / f".tmp_mission_{safe}_{part}.json"


def _save_tmp(path: Path, data: dict) -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Sauvegarde tmp → {path.name}")
    except Exception as e:
        logger.warning(f"Impossible de sauvegarder tmp {path.name} : {e}")


def _load_tmp(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.info(f"Reprise depuis tmp existant → {path.name}")
            return data
    except Exception as e:
        logger.warning(f"tmp {path.name} illisible, on recalcule : {e}")
    return None


def _clear_tmp(paths: list) -> None:
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def analyze_mission(
    mission_config: Dict,
    articles: List[Dict],
    settings: Dict,
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Génère un benchmark stratégique RH personnalisé pour une mission consultant.

    mission_config keys:
      nom_mission, entreprise_cible, secteur, angle_strategique_rh,
      periode, mode ("Rapide" | "Approfondi"), sources, slides_optionnelles

    progress_callback(step, total, msg) — appelé après chaque étape Claude.
    """
    analysis_cfg = settings.get("analysis", {})
    provider = (
        os.environ.get("LLM_PROVIDER")
        or analysis_cfg.get("provider", "anthropic")
    ).lower()

    client = None
    if provider == "gemini":
        model = (
            os.environ.get("GEMINI_MODEL")
            or analysis_cfg.get("gemini_model", "gemini-2.5-flash")
        )
        logger.info(f"Provider : Gemini — modèle : {model}")
    elif provider == "groq":
        model = (
            os.environ.get("GROQ_MODEL")
            or analysis_cfg.get("groq_model", "llama-3.3-70b-versatile")
        )
        logger.info(f"Provider : Groq — modèle : {model}")
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY manquant. Ajoutez votre clé dans le fichier .env.")
        model = (
            os.environ.get("CLAUDE_MODEL")
            or analysis_cfg.get("model", "claude-sonnet-4-6")
        )
        try:
            import anthropic as _ant
        except ImportError:
            raise ImportError("anthropic non installé. Exécuter : pip install anthropic>=0.40.0")
        client = _ant.Anthropic(api_key=api_key)
        logger.info(f"Provider : Anthropic — modèle : {model}")

    nom_mission = mission_config.get("nom_mission", "Mission RH")
    entreprise_cible = mission_config.get("entreprise_cible", "Entreprise")
    secteur = mission_config.get("secteur", "")
    geographie = mission_config.get("geographie", "Maroc")
    angle = mission_config.get("angle_strategique_rh", "")
    concurrent_reference = mission_config.get("concurrent_reference", "") or "Non renseigné"
    periode = mission_config.get("periode", "6 derniers mois")
    mode = mission_config.get("mode", "Rapide")
    slides_optionnelles = mission_config.get("slides_optionnelles", [])
    mission_type = mission_config.get("type", "RH").upper()
    is_org = (mission_type == "ORGANISATIONNEL")

    _prompt_tpl = SYSTEM_PROMPT_MISSION_ORG if is_org else SYSTEM_PROMPT_MISSION
    system_text = _prompt_tpl.format(
        nom_mission=nom_mission,
        entreprise_cible=entreprise_cible,
        secteur=secteur,
        geographie=geographie,
        angle_strategique_rh=angle,
        concurrent_reference=concurrent_reference,
    )
    slides_source = PROMPTS_SLIDES_ORG if is_org else PROMPTS_SLIDES_OPTIONNELLES

    # Pour Gemini / Groq free tier : limiter articles et longueur des résumés
    articles_for_llm = articles
    summary_len = 400
    if provider == "gemini":
        max_art = analysis_cfg.get("gemini_max_articles", 12)
        summary_len = analysis_cfg.get("gemini_summary_len", 150)
        articles_for_llm = articles[:max_art]
        logger.info(f"Gemini mission : {len(articles_for_llm)}/{len(articles)} articles, résumés ≤{summary_len} chars")
    elif provider == "groq":
        max_art = analysis_cfg.get("groq_max_articles", 10)
        summary_len = analysis_cfg.get("groq_summary_len", 200)
        articles_for_llm = articles[:max_art]
        logger.info(f"Groq mission : {len(articles_for_llm)}/{len(articles)} articles, résumés ≤{summary_len} chars")

    articles_text = _format_articles(articles_for_llm, summary_len=summary_len)
    reports_dir = Path(settings.get("reporting", {}).get("output_dir", "reports"))
    reports_dir.mkdir(exist_ok=True)

    # Prompts spécifiques pour les slides optionnelles demandées
    slides_prompts_extra = ""
    for sl_key in slides_optionnelles:
        if sl_key in slides_source:
            prompt_tpl = slides_source[sl_key]
            slides_prompts_extra += (
                f"\n\n--- SLIDE OPTIONNELLE : {sl_key} ---\n"
                + prompt_tpl.format(
                    secteur=secteur,
                    geographie=geographie,
                    entreprise_cible=entreprise_cible,
                    concurrent_reference=concurrent_reference,
                )
            )

    concurrent_line = (
        f"\nRéférence comparative : **{concurrent_reference}** "
        "(comparer explicitement dans chaque axe)"
        if concurrent_reference and concurrent_reference != "Non renseigné"
        else ""
    )

    _bench_label = "Organisationnel" if is_org else "RH"
    _so_what_rule = (
        f'- "So what ?" cible DEUX HORIZONS pour {entreprise_cible} : '
        f'court terme (avant audit Groupe) + moyen terme (évolution structurelle)'
        if is_org else
        f'- "So what ?" SPÉCIFIQUE à {entreprise_cible} sur chaque slide'
    )
    base_prompt = f"""Benchmark {_bench_label} Mission — **{nom_mission}**
Entreprise cible : **{entreprise_cible}** — Secteur : **{secteur}** — Géographie : **{geographie}**
Angle stratégique : {angle}
Période couverte : {periode}{concurrent_line}

RAPPEL RÈGLES ABSOLUES :
- Citer au minimum 2 chiffres réels (≥ 2023) avec source [N] par axe
- Nommer au minimum 2 entreprises réelles du secteur par axe
{_so_what_rule}
- INTERDIT de généraliser sans fait concret issu des sources ci-dessous

**Sources collectées (citer via [N]) :**
{articles_text}{slides_prompts_extra}"""

    # ─────────────────────────────────────────────────────────────────────────
    #  MODE RAPIDE : 1 appel
    # ─────────────────────────────────────────────────────────────────────────
    if mode == "Rapide":
        if provider == "gemini":
            max_tokens = analysis_cfg.get("gemini_max_tokens", 4096)
        elif provider == "groq":
            max_tokens = analysis_cfg.get("groq_max_tokens", 8192)
        else:
            max_tokens = 4096
        tmp = _tmp_path(reports_dir, entreprise_cible, "rapide")
        result = _load_tmp(tmp)
        if result is None:
            if progress_callback:
                progress_callback(0, 1, f"Appel {provider.title()} unique — Mode Rapide…")
            slides_labels = ", ".join(slides_optionnelles) if slides_optionnelles else "aucune"
            if is_org:
                _tool_rapide = TOOL_MISSION_ORG_RAPIDE
                _tool_name_rapide = "mission_benchmark_org"
                _sections_rapide = (
                    "contexte_mission, modeles_csp, processus_douaniers, "
                    "interface_filiale_siege, formalisation_audit_readiness, "
                    "signaux_faibles (max 3), recommandations_mission (exactement 3), "
                    "index_sources (toutes les sources [N] citées)"
                )
                _groq_fmt = _GROQ_OUTPUT_FORMAT_ORG
            else:
                _tool_rapide = TOOL_MISSION_RAPIDE
                _tool_name_rapide = "mission_benchmark"
                _sections_rapide = (
                    "contexte_mission, business_model_rh, organisation_dimensionnement, "
                    "gouvernance_rh, innovation_manageriale, signaux_faibles (max 3), "
                    "recommandations_mission (exactement 3), "
                    "index_sources (toutes les sources [N] citées)"
                )
                _groq_fmt = None
            prompt = (
                base_prompt
                + f"\n\nUtilise `{_tool_name_rapide}` pour produire le benchmark complet en un seul appel : "
                + _sections_rapide + "."
                + (
                    f"\n\nSlides optionnelles demandées : {slides_labels}. "
                    f"Remplis slides_optionnelles avec 1 item par thème coché "
                    f"(cle, titre, observation, benchmark_sectoriel, implication_rh, so_what)."
                    if slides_optionnelles else
                    "\n\nAucune slide optionnelle demandée : slides_optionnelles = []."
                )
            )
            result = _call_llm(
                provider, model, max_tokens, system_text,
                _tool_rapide, _tool_name_rapide, prompt, client,
                output_format=_groq_fmt,
            )
            _save_tmp(tmp, result)

        if progress_callback:
            progress_callback(1, 1, "Benchmark Rapide généré.")

        result["_meta"] = {
            "provider": provider, "model": model,
            "mode": "Rapide",
            "type": mission_type,
            "mission": nom_mission,
            "entreprise": entreprise_cible,
            "generated_at": datetime.now().isoformat(),
            "nb_sources_analysees": len(articles),
        }
        _clear_tmp([tmp])
        return result

    # ─────────────────────────────────────────────────────────────────────────
    #  MODE APPROFONDI : 3 appels
    # ─────────────────────────────────────────────────────────────────────────
    if provider == "gemini":
        max_tokens = analysis_cfg.get("gemini_max_tokens", 4096)
    elif provider == "groq":
        max_tokens = analysis_cfg.get("groq_max_tokens", 8192)
    else:
        max_tokens = 8192

    # Sélection des outils selon le type de benchmark
    if is_org:
        _tool_a, _name_a = TOOL_MISSION_ORG_PART_A, "mission_org_part_a"
        _tool_b, _name_b = TOOL_MISSION_ORG_PART_B, "mission_org_part_b"
        _label_a = "Contexte, Modèles CSP, Processus douaniers"
        _label_b = "Interface Filiale/Siège, Formalisation & Audit-readiness, Signaux faibles"
        _sections_a = (
            "1. contexte_mission (résumé de la mission et de l'angle organisationnel)\n"
            "2. modeles_csp (structures CSP comparables, gouvernance, périmètre, so_what pour "
            + entreprise_cible + ")\n"
            "3. processus_douaniers (best practices import/export, outils, risques, so_what pour "
            + entreprise_cible + ")"
        )
        _sections_b = (
            "1. interface_filiale_siege (délégation, protocoles, reporting, so_what pour "
            + entreprise_cible + ")\n"
            "2. formalisation_audit_readiness (maturité, référentiels, critères audit Groupe, so_what pour "
            + entreprise_cible + ")\n"
            "3. signaux_faibles (max 3 : signal, implication_organisationnelle, horizon, pertinence_mission)"
        )
        _groq_fmt_approfondi = _GROQ_OUTPUT_FORMAT_ORG
    else:
        _tool_a, _name_a = TOOL_MISSION_PART_A, "mission_part_a"
        _tool_b, _name_b = TOOL_MISSION_PART_B, "mission_part_b"
        _label_a = "Contexte, Business Model RH, Organisation"
        _label_b = "Gouvernance RH, Innovation managériale, Signaux faibles"
        _sections_a = (
            "1. contexte_mission (résumé de la mission et de l'angle RH)\n"
            "2. business_model_rh (analyse, compétences émergentes/obsolètes, so_what pour "
            + entreprise_cible + ")\n"
            "3. organisation_dimensionnement (analyse, tendances effectifs, nouveaux rôles, "
            "externalisation, so_what pour " + entreprise_cible + ")"
        )
        _sections_b = (
            "1. gouvernance_rh (analyse, instances RH, politiques sociales, conformité, so_what pour "
            + entreprise_cible + ")\n"
            "2. innovation_manageriale (analyse, pratiques différenciantes, outils RH, expérience employé, "
            "so_what pour " + entreprise_cible + ")\n"
            "3. signaux_faibles (max 3 : signal, implication_rh, horizon, pertinence_mission)"
        )
        _groq_fmt_approfondi = None

    tmp_a = _tmp_path(reports_dir, entreprise_cible, "part_a")
    tmp_b = _tmp_path(reports_dir, entreprise_cible, "part_b")
    tmp_c = _tmp_path(reports_dir, entreprise_cible, "part_c")

    # -- Part A --
    part_a = _load_tmp(tmp_a)
    if part_a is None:
        if progress_callback:
            progress_callback(0, 3, f"Appel 1/3 — {_label_a}…")
        prompt_a = (
            base_prompt
            + f"\n\nUtilise `{_name_a}` pour les sections :\n"
            + _sections_a
        )
        part_a = _call_llm(
            provider, model, max_tokens, system_text,
            _tool_a, _name_a, prompt_a, client,
            output_format=_groq_fmt_approfondi,
        )
        _save_tmp(tmp_a, part_a)
    else:
        if progress_callback:
            progress_callback(1, 3, "Part A rechargée depuis cache — Appel 2/3 en cours…")

    # -- Part B --
    part_b = _load_tmp(tmp_b)
    if part_b is None:
        if progress_callback:
            progress_callback(1, 3, f"Appel 2/3 — {_label_b}…")
        prompt_b = (
            base_prompt
            + f"\n\nUtilise `{_name_b}` pour les sections :\n"
            + _sections_b
        )
        part_b = _call_llm(
            provider, model, max_tokens, system_text,
            _tool_b, _name_b, prompt_b, client,
            output_format=_groq_fmt_approfondi,
        )
        _save_tmp(tmp_b, part_b)
    else:
        if progress_callback:
            progress_callback(2, 3, "Part B rechargée depuis cache — Appel 3/3 en cours…")

    # -- Part C --
    tool_part_c = _build_tool_part_c(slides_optionnelles)
    part_c = _load_tmp(tmp_c)
    if part_c is None:
        if progress_callback:
            progress_callback(2, 3, "Appel 3/3 — Recommandations, Slides optionnelles, Index sources…")

        slides_instruction = ""
        if slides_optionnelles:
            slides_labels = ", ".join(slides_optionnelles)
            slides_instruction = (
                f"\nPour les slides_optionnelles, produis une entrée par thème demandé "
                f"({slides_labels}) avec les champs : cle (identifiant), titre, observation, "
                f"benchmark_sectoriel, implication_rh, so_what."
            )

        prompt_c = (
            base_prompt
            + "\n\nUtilise `mission_part_c` pour les sections :\n"
            "1. recommandations_mission (exactement 3 : action, justification, priorite, kpi, horizon)\n"
            + slides_instruction
            + "\n2. index_sources : toutes les sources citées [N] dans ce benchmark "
            "(id, titre, source, url, date, pertinence : Directe/Contextuelle)"
        )
        part_c = _call_llm(
            provider, model, max_tokens, system_text,
            tool_part_c, "mission_part_c", prompt_c, client,
        )
        _save_tmp(tmp_c, part_c)

    if progress_callback:
        progress_callback(3, 3, "Fusion et finalisation du benchmark…")

    # -- Fusion --
    result = {**part_a, **part_b, **part_c}
    result["_meta"] = {
        "provider": provider, "model": model,
        "mode": "Approfondi",
        "type": mission_type,
        "mission": nom_mission,
        "entreprise": entreprise_cible,
        "generated_at": datetime.now().isoformat(),
        "nb_sources_analysees": len(articles),
    }

    _clear_tmp([tmp_a, tmp_b, tmp_c])
    logger.info("Benchmark mission complet — trois appels fusionnés.")
    return result
