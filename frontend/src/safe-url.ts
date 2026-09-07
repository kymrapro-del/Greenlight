/**
 * Le filtre d'URL des citations.
 *
 * Les URL du rapport viennent des résultats de recherche, donc du web ouvert.
 * React n'échappe pas un attribut `href` : `javascript:...` posé là devient du
 * code exécuté au clic, dans l'origine de l'application. C'est une injection à
 * un clic, et le chemin qui l'amène est exactement celui que ce produit
 * emprunte à chaque rapport.
 *
 * Le pipeline vérifie déjà qu'une URL citée apparaît bien dans les résultats de
 * recherche. Cette vérification-là dit « la source existe » ; elle ne dit rien
 * du schéma. Les deux sont nécessaires.
 *
 * Liste blanche, pas liste noire : `http` et `https` uniquement. Tout le reste —
 * `javascript:`, `data:`, `vbscript:`, un schéma exotique — est refusé, et
 * l'interface affiche l'URL en texte plutôt que de la rendre cliquable.
 */

const ALLOWED = new Set(['http:', 'https:']);

export function safeHref(url: string): string | null {
  try {
    // `URL` normalise avant de rendre le protocole, ce qui neutralise les
    // esquives par espaces, tabulations, casse ou encodage — là où une
    // comparaison de chaîne se ferait avoir par `JaVaScRiPt&#58;`.
    return ALLOWED.has(new URL(url).protocol) ? url : null;
  } catch {
    // Pas une URL absolue : rien à ouvrir.
    return null;
  }
}
