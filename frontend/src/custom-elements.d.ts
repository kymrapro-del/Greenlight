/**
 * Typage des composants Material Web utilisés dans le JSX.
 *
 * Ce sont des éléments personnalisés, pas des composants React : sans cette
 * déclaration, TypeScript les refuse. On ne déclare que les propriétés
 * réellement employées, plutôt qu'un `any` fourre-tout.
 *
 * Le nom `CustomElementProps` n'est pas cosmétique : appeler cet alias
 * `Element` masquerait le type `JSX.Element` dans tout le module et ferait
 * échouer le typage des composants.
 */
import type { DetailedHTMLProps, HTMLAttributes } from 'react';

type CustomElementProps<T = Record<string, unknown>> = DetailedHTMLProps<
  HTMLAttributes<HTMLElement> & T,
  HTMLElement
>;

/** L'élément qu'un `click` sur `md-filter-chip` porte : il a déjà basculé. */
export interface FilterChipElement extends HTMLElement {
  selected: boolean;
}

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'md-ripple': CustomElementProps<{ disabled?: boolean }>;
      'md-focus-ring': CustomElementProps<{ inward?: boolean }>;
      'md-chip-set': CustomElementProps;
      'md-filter-chip': CustomElementProps<{
        label?: string;
        selected?: boolean;
        disabled?: boolean;
      }>;
    }
  }
}
