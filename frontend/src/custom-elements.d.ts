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

/** Ce que porte l'événement `input` d'un `md-outlined-text-field`. */
export interface TextFieldElement extends HTMLElement {
  value: string;
}

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'md-ripple': CustomElementProps<{ disabled?: boolean }>;
      'md-focus-ring': CustomElementProps<{ inward?: boolean }>;
      'md-chip-set': CustomElementProps;
      'md-outlined-text-field': CustomElementProps<{
        label?: string;
        value?: string;
        type?: string;
        placeholder?: string;
      }>;
      'md-linear-progress': CustomElementProps<{
        indeterminate?: boolean;
        value?: number;
        max?: number;
      }>;
      'md-filter-chip': CustomElementProps<{
        label?: string;
        selected?: boolean;
        disabled?: boolean;
      }>;
    }
  }
}
