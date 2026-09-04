/**
 * Système de couleur M3, généré — jamais écrit à la main.
 *
 * Une seule couleur source produit les palettes tonales, les deux schémas et
 * toutes les paires `container` / `on-container`. Les contrastes sont garantis
 * par construction : c'est l'algorithme M3 qui les calcule, pas un choix
 * esthétique à re-vérifier à chaque écran.
 *
 * **`SchemeTonalSpot` + `MaterialDynamicColors`, et non `themeFromSourceColor`.**
 * Ce dernier rend le schéma hérité de la librairie, antérieur aux rôles de
 * surface introduits depuis : il ne produit ni `surface-container`, ni
 * `surface-container-low`, ni `surface-container-high`. Une interface qui les
 * utilise se retrouve alors avec des fonds transparents — barre supérieure et
 * volets invisibles — sans aucune erreur nulle part, parce qu'une variable CSS
 * absente ne se plaint pas. Le schéma dynamique rend les 57 rôles, ceux-là
 * compris.
 *
 * Les couleurs de verdict passent par le mécanisme M3 des couleurs
 * personnalisées harmonisées, et non par des hex bruts : l'ambre
 * d'avertissement est ramené vers la source, donc il reste reconnaissable comme
 * un avertissement tout en appartenant à la même famille que le reste.
 */

import {
  argbFromHex,
  customColor,
  Hct,
  hexFromArgb,
  MaterialDynamicColors,
  SchemeTonalSpot,
} from '@material/material-color-utilities';

/** Le vert du feu vert de studio — l'autorisation de tourner. */
export const SOURCE_COLOR = '#1B7F3B';

/**
 * M3 ne définit pas de rôle `warning` : il s'arrête à `error`. Un rapport de
 * clearance a pourtant besoin d'un cran entre « à surveiller » et « à changer ».
 */
export const WARNING_SOURCE = '#B8860B';

/** Helper de calcul exposé aux côtés des rôles, pas un rôle lui-même. */
const NOT_A_ROLE = new Set(['highestSurface', 'length', 'name', 'prototype']);

const kebab = (name: string) => name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();

type Vars = Record<string, string>;
type DynamicColor = { getArgb(scheme: unknown): number };

function roleVars(source: string, dark: boolean): Vars {
  const scheme = new SchemeTonalSpot(Hct.fromInt(argbFromHex(source)), dark, 0);
  const colors = MaterialDynamicColors as unknown as Record<string, DynamicColor>;

  const vars: Vars = {};
  for (const name of Object.getOwnPropertyNames(MaterialDynamicColors)) {
    if (NOT_A_ROLE.has(name)) continue;
    const role = colors[name];
    // Certaines propriétés statiques sont des réglages, pas des couleurs.
    if (!role || typeof role.getArgb !== 'function') continue;
    vars[`--md-sys-color-${kebab(name)}`] = hexFromArgb(role.getArgb(scheme));
  }
  return vars;
}

function warningVars(source: string, dark: boolean): Vars {
  const group = customColor(argbFromHex(source), {
    value: argbFromHex(WARNING_SOURCE),
    name: 'warning',
    blend: true,
  });
  const tones = dark ? group.dark : group.light;
  return {
    '--md-sys-color-warning': hexFromArgb(tones.color),
    '--md-sys-color-on-warning': hexFromArgb(tones.onColor),
    '--md-sys-color-warning-container': hexFromArgb(tones.colorContainer),
    '--md-sys-color-on-warning-container': hexFromArgb(tones.onColorContainer),
  };
}

export function buildScheme(mode: 'light' | 'dark', source = SOURCE_COLOR): Vars {
  const dark = mode === 'dark';
  return { ...roleVars(source, dark), ...warningVars(source, dark) };
}

const block = (selector: string, vars: Vars, indent = '') =>
  `${indent}${selector} {\n${Object.entries(vars)
    .map(([k, v]) => `${indent}  ${k}: ${v};`)
    .join('\n')}\n${indent}}`;

/**
 * Feuille de style complète, dans les trois états que M3 attend : le schéma
 * clair par défaut, le sombre sous `prefers-color-scheme`, et une bascule
 * explicite qui l'emporte dans les deux sens.
 */
export function buildThemeCss(source = SOURCE_COLOR): string {
  const light = buildScheme('light', source);
  const dark = buildScheme('dark', source);
  return [
    '/* Généré par src/theme/color.ts — ne pas éditer à la main. */',
    `/* Couleur source : ${source} · avertissement harmonisé : ${WARNING_SOURCE} */`,
    '',
    block(':root', light),
    '',
    '@media (prefers-color-scheme: dark) {',
    block(":root:not([data-theme='light'])", dark, '  '),
    '}',
    '',
    block(":root[data-theme='dark']", dark),
    '',
  ].join('\n');
}
