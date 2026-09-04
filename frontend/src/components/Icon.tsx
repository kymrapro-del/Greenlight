/**
 * Icônes en SVG inline.
 *
 * Volontairement pas la police Material Symbols. Une police d'icônes qui ne
 * charge pas affiche le nom de l'icône en toutes lettres — « error », « warning »
 * — au milieu de l'interface. Sur un réseau de salle de conférence, c'est ce que
 * le jury verrait. Le SVG inline n'a pas ce mode de défaillance : il n'y a rien
 * à télécharger.
 *
 * Tracé sur la grille 24 × 24 de M3, en contour à `currentColor` : chaque icône
 * prend donc la couleur du rôle qui la contient, sans réglage supplémentaire.
 */

const PATHS: Record<string, string> = {
  // Cercle + exclamation — à changer.
  error: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18M12 7.6v5.2M12 16.4h.01',
  // Triangle + exclamation — à surveiller.
  warning: 'M12 3.6 21.4 20H2.6zM12 10v3.8M12 16.9h.01',
  // Cercle + coche — conforme.
  check_circle: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18M8 12.2l2.8 2.8L16.4 9.4',
  // Cercle + C — licence requise.
  copyright: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18M14.9 9.7a3.7 3.7 0 1 0 0 4.6',
  // Cercle + interrogation — non tranché.
  help: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18M9.5 9.6a2.6 2.6 0 1 1 3.3 2.5c-.6.2-.8.7-.8 1.3v.4M12 16.6h.01',
  // Flèche montante — verdict remonté.
  trending_up: 'M3.6 16.6 10 10.2l3.5 3.5 6.9-6.9M15.5 6.8h5v5',
  // Coche + trait — tranché par règle.
  rule: 'M3.6 8.4 6 10.8l4.4-4.4M13.6 8.6h6.8M14.4 15.4l5 5M19.4 15.4l-5 5',
  // Cercle + coche, cerclé — remplacement re-vérifié.
  verified: 'M12 2.8 14.3 5l3.1.3.3 3.1 2.2 2.3-2.2 2.3-.3 3.1-3.1.3-2.3 2.2-2.3-2.2-3.1-.3-.3-3.1L3.9 11l2.4-2.4.3-3.1L9.7 5zM9 11.4l2.2 2.2 3.9-4',
  // Lien externe.
  open_in_new: 'M14 4h6v6M20 4l-8.5 8.5M18 14.2V19a1.6 1.6 0 0 1-1.6 1.6H5.6A1.6 1.6 0 0 1 4 19V8.2a1.6 1.6 0 0 1 1.6-1.6h4.8',
  // Document — état vide.
  document: 'M6.5 3.6h6.6l4.9 4.9v11.9H6.5zM13.1 3.6v4.9H18',
  // Fiole — données de démonstration.
  science: 'M10 3.6v5.8L4.9 18a1.6 1.6 0 0 0 1.4 2.4h11.4a1.6 1.6 0 0 0 1.4-2.4L14 9.4V3.6M9 3.6h6',
  // Coquille du chat.
  menu: 'M4 6.5h16M4 12h16M4 17.5h16',
  add: 'M12 5v14M5 12h14',
  attach: 'M20 11.5 12.4 19a4.6 4.6 0 0 1-6.5-6.5l7.6-7.6a3.1 3.1 0 0 1 4.4 4.4l-7.6 7.6a1.5 1.5 0 0 1-2.2-2.2l7-7',
  send: 'M4.5 12 20 4.5l-4 15.5-4.2-6.1z M11.8 13.9 20 4.5',
  expand_more: 'M6.5 9.5 12 15l5.5-5.5',
  expand_less: 'M6.5 14.5 12 9l5.5 5.5',
  thumb_up: 'M7 10.5v9.5H4.6a1.1 1.1 0 0 1-1.1-1.1v-7.3a1.1 1.1 0 0 1 1.1-1.1zM7 10.5l4.3-7.1a2 2 0 0 1 3.6 1.6l-.9 3.9h4.6a2 2 0 0 1 2 2.4l-1.3 6.2a2 2 0 0 1-2 1.5H7',
  thumb_down: 'M7 13.5V4H4.6a1.1 1.1 0 0 0-1.1 1.1v7.3a1.1 1.1 0 0 0 1.1 1.1zM7 13.5l4.3 7.1a2 2 0 0 0 3.6-1.6l-.9-3.9h4.6a2 2 0 0 0 2-2.4l-1.3-6.2a2 2 0 0 0-2-1.5H7',
  copy: 'M9 9h9.5v11.5H9zM15 9V4.5H5.5V16H9',
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const path = PATHS[name];
  if (!path) return null;
  return (
    <svg
      className="gl-icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={path} />
    </svg>
  );
}
