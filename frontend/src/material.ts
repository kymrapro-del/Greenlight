/**
 * Les composants Material Web réellement montés par l'application.
 *
 * Un seul point d'import, chargé par `main.tsx` avant le premier rendu : ce
 * sont des éléments personnalisés, ils doivent être définis dans le registre
 * du navigateur avant que React n'écrive leurs propriétés.
 *
 * Ce que la librairie apporte et qu'on ne réécrit pas à la main :
 *
 * - `md-ripple` — la couche d'état M3 complète. Un `::after` maison fait le
 *   survol et le focus, mais pas l'onde de pression : elle part du point de
 *   contact, sa taille dépend de celle du conteneur et sa sortie dure plus
 *   longtemps que son entrée. C'est le retour tactile de M3, et le
 *   réimplémenter serait recopier la librairie moins bien.
 * - `md-focus-ring` — l'anneau de focus, avec son animation de croissance et
 *   son décrochage du conteneur. Il s'affiche sur `:focus-visible` seulement,
 *   donc jamais après un clic souris.
 * - `md-filter-chip` — les filtres de verdict *sont* des filter chips M3 :
 *   même rôle, même sémantique `aria-pressed`, même coche à la sélection.
 *
 * `md-ripple` et `md-focus-ring` s'attachent tout seuls à leur élément parent
 * (`AttachableController`) : il suffit de les poser dans un conteneur
 * positionné, sans identifiant ni câblage.
 */
import '@material/web/ripple/ripple.js';
import '@material/web/focus/md-focus-ring.js';
import '@material/web/chips/chip-set.js';
import '@material/web/chips/filter-chip.js';
