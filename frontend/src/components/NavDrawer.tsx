import { Icon } from './Icon';
import { StateLayer } from './StateLayer';

export interface Thread {
  id: string;
  title: string;
}

/**
 * Le volet, sur le modèle de Gemini.
 *
 * Trois zones empilées : la nouvelle analyse en haut, l'historique au milieu,
 * le compte en bas. Les entrées sont des lignes plates — icône + libellé, coin
 * plein arrondi au survol — et non des cartes : c'est ce qui donne au volet son
 * calme, et ce qui laisse l'historique occuper la hauteur.
 *
 * Il n'y a rien d'autre. Une recherche d'entité, une bibliothèque de scénarios
 * et un journal d'activité y figuraient, et ne faisaient rien : trois boutons
 * morts que le premier visiteur clique. Un volet plus court qui tient ses
 * promesses vaut mieux qu'un volet complet qui n'en tient aucune.
 *
 * Ce n'est pas un `navigation drawer` M3 au sens strict, qui suppose plusieurs
 * destinations. C'est un volet d'historique, bâti sur les mêmes tokens.
 */
export function NavDrawer({
  threads,
  activeId,
  open,
  onSelect,
  onNew,
  onToggle,
}: {
  threads: Thread[];
  activeId: string | null;
  open: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onToggle: () => void;
}) {
  return (
    <aside className={`gl-drawer ${open ? 'is-open' : 'is-collapsed'}`}>
      <header className="gl-drawer-head">
        {open && (
          <span className="gl-brand">
            <span className="gl-mark" aria-hidden="true" />
            <span className="gl-title-large">GREENLIGHT</span>
          </span>
        )}
        <button
          type="button"
          className="gl-icon-button gl-state-layer"
          onClick={onToggle}
          aria-label={open ? 'Replier le volet' : 'Déplier le volet'}
          aria-expanded={open}
        >
          <StateLayer />
        <Icon name="panel" size={20} />
        </button>
      </header>

      <button type="button" className="gl-nav-item is-primary gl-state-layer" onClick={onNew}>
        <StateLayer />
        <Icon name="compose" size={20} />
        {open && <span className="gl-label-large">Nouvelle analyse</span>}
      </button>

      {open && (
        <div className="gl-recents">
          <p className="gl-label-medium gl-drawer-legend">Récentes</p>
          {threads.map((thread) => (
            <button
              key={thread.id}
              type="button"
              className={`gl-recent gl-body-medium gl-state-layer ${
                thread.id === activeId ? 'is-active' : ''
              }`}
              aria-current={thread.id === activeId ? 'true' : undefined}
              onClick={() => onSelect(thread.id)}
            >
              <StateLayer />
              {thread.title}
            </button>
          ))}
        </div>
      )}

      <div className="gl-account">
        <span className="gl-avatar-user" aria-hidden="true">
          K
        </span>
        {open && (
          <>
            <span className="gl-account-id">
              <span className="gl-body-medium">Kymra</span>
              <span className="gl-body-small gl-account-plan">Pré-clearance</span>
            </span>
            <button
              type="button"
              className="gl-icon-button gl-state-layer"
              aria-label="Paramètres"
            >
              <StateLayer />
              <Icon name="settings" size={18} />
            </button>
          </>
        )}
      </div>
    </aside>
  );
}
