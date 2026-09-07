/**
 * Le choix clair / sombre, et sa mémoire.
 *
 * Trois états, pas deux. « Système » est celui par défaut, et il n'est pas la
 * même chose que « clair » : quelqu'un dont le téléphone bascule au coucher du
 * soleil veut que l'application bascule avec lui. La feuille de couleurs
 * générée porte déjà les trois cas — `prefers-color-scheme` quand rien n'est
 * imposé, `data-theme` quand l'utilisateur a tranché — donc il n'y a qu'un
 * attribut à poser sur la racine.
 *
 * Le choix survit au rechargement, et seulement pour ce navigateur : c'est une
 * préférence d'affichage, elle n'a rien à faire sur un serveur.
 */

export const SCHEMES = ['system', 'light', 'dark'] as const;
export type Scheme = (typeof SCHEMES)[number];

const KEY = 'greenlight:scheme';

export function readScheme(): Scheme {
  try {
    const stored = localStorage.getItem(KEY);
    return SCHEMES.includes(stored as Scheme) ? (stored as Scheme) : 'system';
  } catch {
    // Navigation privée, stockage bloqué : on retombe sur le système, ce qui
    // est exactement le bon défaut.
    return 'system';
  }
}

export function applyScheme(scheme: Scheme): void {
  const root = document.documentElement;
  if (scheme === 'system') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', scheme);
  try {
    localStorage.setItem(KEY, scheme);
  } catch {
    // Rien à faire : le thème est appliqué, il ne sera juste pas mémorisé.
  }
}

/** Ce que le bouton propose ensuite : système → clair → sombre → système. */
export function nextScheme(current: Scheme): Scheme {
  return SCHEMES[(SCHEMES.indexOf(current) + 1) % SCHEMES.length];
}

export const SCHEME_LABELS: Record<Scheme, string> = {
  system: 'Thème du système',
  light: 'Thème clair',
  dark: 'Thème sombre',
};

export const SCHEME_ICONS: Record<Scheme, string> = {
  system: 'contrast',
  light: 'light_mode',
  dark: 'dark_mode',
};
