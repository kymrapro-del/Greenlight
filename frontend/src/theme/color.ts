/**
 * Système de couleur M3, généré — jamais écrit à la main.
 *
 * Une seule couleur source produit les six palettes tonales, les deux schémas
 * (clair et sombre) et toutes les paires `container` / `on-container`. Les
 * contrastes sont garantis par construction : c'est l'algorithme M3 qui les
 * calcule, pas un choix esthétique à re-vérifier à chaque écran.
 *
 * Les couleurs de verdict passent par le mécanisme M3 des couleurs
 * personnalisées harmonisées, et non par des hex bruts. Une teinte harmonisée
 * est ramenée vers la source : l'ambre d'avertissement reste reconnaissable
 * comme un avertissement, tout en appartenant visiblement à la même famille que
 * le reste de l'interface.
 */

import {
  argbFromHex,
  hexFromArgb,
  themeFromSourceColor,
} from '@material/material-color-utilities';

/** Le vert du feu vert de studio — l'autorisation de tourner. */
export const SOURCE_COLOR = '#1B7F3B';

/**
 * M3 ne définit pas de rôle `warning` : il s'arrête à `error`. Un rapport de
 * clearance a pourtant besoin d'un cran entre « à surveiller » et « à changer ».
 * On l'ajoute par le mécanisme prévu pour ça plutôt qu'en peignant un hex.
 */
export const WARNING_SOURCE = '#B8860B';

const CUSTOM_COLORS = [
  { name: 'warning', value: argbFromHex(WARNING_SOURCE), blend: true },
];

const kebab = (name: string) => name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();

type Vars = Record<string, string>;

function schemeVars(scheme: Record<string, number>): Vars {
  const vars: Vars = {};
  for (const [role, argb] of Object.entries(scheme)) {
    vars[`--md-sys-color-${kebab(role)}`] = hexFromArgb(argb);
  }
  return vars;
}

function customVars(
  group: { color: { name: string }; light: Record<string, number>; dark: Record<string, number> },
  mode: 'light' | 'dark',
): Vars {
  const name = kebab(group.color.name);
  const source = group[mode];
  return {
    [`--md-sys-color-${name}`]: hexFromArgb(source.color),
    [`--md-sys-color-on-${name}`]: hexFromArgb(source.onColor),
    [`--md-sys-color-${name}-container`]: hexFromArgb(source.colorContainer),
    [`--md-sys-color-on-${name}-container`]: hexFromArgb(source.onColorContainer),
  };
}

export function buildScheme(mode: 'light' | 'dark', source = SOURCE_COLOR): Vars {
  const theme = themeFromSourceColor(argbFromHex(source), CUSTOM_COLORS);
  return {
    ...schemeVars(theme.schemes[mode].toJSON() as Record<string, number>),
    ...theme.customColors.reduce<Vars>(
      (acc, group) => ({ ...acc, ...customVars(group as never, mode) }),
      {},
    ),
  };
}

const block = (selector: string, vars: Vars) =>
  `${selector} {\n${Object.entries(vars)
    .map(([k, v]) => `  ${k}: ${v};`)
    .join('\n')}\n}`;

/**
 * Feuille de style complète, dans les trois états que le M3 attend : le schéma
 * clair par défaut, le sombre sous `prefers-color-scheme`, et un bascule
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
    `@media (prefers-color-scheme: dark) {\n${block('  :root:not([data-theme="light"])', dark)
      .split('\n')
      .map((l) => (l.startsWith('  ') ? l : `  ${l}`))
      .join('\n')}\n}`,
    '',
    block(':root[data-theme="dark"]', dark),
    '',
  ].join('\n');
}
