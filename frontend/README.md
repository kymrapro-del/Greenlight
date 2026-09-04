# GREENLIGHT — l'interface

Un fil de conversation en Material 3, sur le modèle de Gemini. On y dépose un
scénario, on regarde les huit phases avancer, et le rapport de clearance
s'affiche **dans** la réponse. Ensuite on pose des questions dessus.

## Lancer

L'interface ne calcule rien : il lui faut l'API.

```bash
# L'API, depuis la racine du dépôt
PYTHONPATH=backend .venv/bin/python -m uvicorn greenlight.api.server:app --port 8000

# Ici
npm install
npm run theme   # régénère les palettes M3 depuis la couleur source
npm run dev     # proxie /api vers localhost:8000
```

`GREENLIGHT_API` change la cible du proxy en développement. En production,
`VITE_API_BASE` pointe sur le service déployé ; vide, le client tape la même
origine.

## Material 3

Aucune valeur de couleur, de rayon, de durée ni de taille de texte n'est écrite
en dur. Tout vient des tokens générés depuis **une** couleur source
(`#1B7F3B`) par `@material/material-color-utilities` — changer cette couleur
recolore l'application entière.

`@material/web` fournit les composants là où la librairie en a un :
`md-ripple` et `md-focus-ring` pour la couche d'état de chaque surface,
`md-filter-chip` pour les filtres de verdict, `md-linear-progress` pour une
passe en cours. La coquille conversationnelle — volet, saisie, tours — est
bâtie sur les tokens, parce que la librairie ne livre pas ces composants-là.

Les icônes sont des SVG inline plutôt que la police Material Symbols : une
police d'icônes qui ne charge pas affiche le *nom* de l'icône en toutes lettres.

## Fichiers

| | |
| --- | --- |
| `src/api.ts` | le client HTTP, dont la lecture du flux SSE |
| `src/App.tsx` | l'état du fil : tours, passes, questions |
| `src/components/` | les composants, un par rôle |
| `src/theme/` | les tokens M3 générés et les fichiers qui s'appuient dessus |
| `scripts/generate-theme.mjs` | régénère `theme/generated-color.css` |
