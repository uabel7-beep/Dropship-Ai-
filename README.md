# DROPSHIP AI V12

V12 garde l'interface simple de V11 et ajoute deux priorités :

- recherche live anti-freeze (timeouts + bouton Réessayer)
- Profit Engine sur les détails produit

## Profit Engine

Quand tu ouvres un produit, V12 peut récupérer les détails ReefAPI, dont la livraison par destination. Il calcule :
- coût fournisseur
- livraison si connue
- prix de vente estimé
- frais plateforme (5% par défaut)
- publicité estimée (15% par défaut)
- bénéfice net estimé
- ROI
- marge nette

Une livraison inconnue reste « à vérifier » : elle n'est jamais considérée comme gratuite.

## Installation

1. Garde ton `token.env` actuel avec ta vraie `REEF_API_KEY`.
2. Lance `main.py`.
3. `/start` → Product Hunter → une niche.
4. Clique sur `🔍 #1` pour charger l'analyse détaillée.

Les valeurs `AD_COST_RATE` et `PLATFORM_FEE_RATE` sont dans `config.py` pour être modifiables plus tard sans changer l'interface.
