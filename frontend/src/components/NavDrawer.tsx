import { Icon } from './Icon';

export interface Thread {
  id: string;
  title: string;
}

/**
 * Le volet, sur le modèle de Gemini.
 *
 * Trois zones empilées : l'action principale et les entrées de navigation en
 * haut, l'historique au milieu, le compte en bas. Les entrées sont des lignes
 * plates — icône + libellé, coin plein arrondi au survol — et non des cartes :
 * c'est ce qui donne au volet son calme, et ce qui laisse l'historique occuper
 * la hauteur.
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
          <Icon name="panel" size={20} />
        </button>
      </header>

      <button type="button" className="gl-nav-item is-primary gl-state-layer" onClick={onNew}>
        <Icon name="compose" size={20} />
        {open && <span className="gl-label-large">Nouvelle analyse</span>}
      </button>

      <nav className="gl-nav" aria-label="Sections">
        <button type="button" className="gl-nav-item gl-state-layer">
          <Icon name="search" size={20} />
          {open && <span className="gl-label-large">Rechercher une entité</span>}
        </button>
        <button type="button" className="gl-nav-item gl-state-layer">
          <Icon name="library" size={20} />
          {open && <span className="gl-label-large">Scénarios</span>}
        </button>
      </nav>

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
              {thread.title}
            </button>
          ))}
        </div>
      )}

      <button type="button" className="gl-nav-item gl-state-layer">
        <Icon name="history" size={20} />
        {open && <span className="gl-label-large">Activité</span>}
      </button>

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
              <Icon name="settings" size={18} />
            </button>
          </>
        )}
      </div>
    </aside>
  );
}
