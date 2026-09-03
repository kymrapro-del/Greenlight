/**
 * Les cinq verdicts, traduits en rôles de couleur M3.
 *
 * Aucun hex n'apparaît ici : chaque verdict pointe vers une paire
 * `container` / `on-container`, dont M3 garantit le contraste par construction.
 * Basculer la couleur source de l'application recolore donc le rapport entier
 * sans qu'aucune de ces valeurs ne bouge, et sans risque de régression de
 * lisibilité.
 *
 * La couleur ne porte jamais l'information seule. Chaque verdict a aussi un
 * libellé et une icône : un rapport de clearance se lit aussi en niveaux de
 * gris, et un daltonien doit pouvoir distinguer « à changer » de « conforme ».
 */

export const VERDICTS = [
  'CHANGE_RECOMMENDED',
  'LICENSE_REQUIRED',
  'CAUTION',
  'UNRESOLVED',
  'CLEAR',
] as const;

export type Verdict = (typeof VERDICTS)[number];

export interface VerdictStyle {
  /** Libellé court, tel qu'il apparaît sur la puce. */
  label: string;
  /** Ce que le scénariste doit en faire — en clair, sans jargon. */
  action: string;
  /** Material Symbols. Redondant avec la couleur, volontairement. */
  icon: string;
  container: string;
  onContainer: string;
}

export const VERDICT_STYLES: Record<Verdict, VerdictStyle> = {
  CHANGE_RECOMMENDED: {
    label: 'À changer',
    action: 'Renommer avant le tournage : la corriger maintenant ne coûte rien.',
    icon: 'error',
    container: 'var(--md-sys-color-error-container)',
    onContainer: 'var(--md-sys-color-on-error-container)',
  },
  LICENSE_REQUIRED: {
    label: 'Licence requise',
    action: "Obtenir l'autorisation, ou couper. Renommer ne règle rien ici.",
    icon: 'copyright',
    container: 'var(--md-sys-color-secondary-container)',
    onContainer: 'var(--md-sys-color-on-secondary-container)',
  },
  CAUTION: {
    // Le cran que M3 ne fournit pas : couleur personnalisée harmonisée.
    label: 'À surveiller',
    action: 'Rien de tranché, mais à relire avant de figer le scénario.',
    icon: 'warning',
    container: 'var(--md-sys-color-warning-container)',
    onContainer: 'var(--md-sys-color-on-warning-container)',
  },
  UNRESOLVED: {
    label: 'Non tranché',
    action: "La recherche n'a pas conclu. À vérifier à la main.",
    icon: 'help',
    container: 'var(--md-sys-color-surface-variant)',
    onContainer: 'var(--md-sys-color-on-surface-variant)',
  },
  CLEAR: {
    label: 'Conforme',
    action: 'Rien à faire.',
    icon: 'check_circle',
    container: 'var(--md-sys-color-tertiary-container)',
    onContainer: 'var(--md-sys-color-on-tertiary-container)',
  },
};

/** Ordre d'affichage du rapport : ce qui bloque le tournage en premier. */
export const VERDICT_ORDER: Record<Verdict, number> = Object.fromEntries(
  VERDICTS.map((v, i) => [v, i]),
) as Record<Verdict, number>;
