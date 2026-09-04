import '@material/web/button/filled-tonal-button.js';
import '@material/web/iconbutton/icon-button.js';

import { Icon } from './Icon';

export interface Thread {
  id: string;
  title: string;
  subtitle: string;
}

/**
 * Le volet de navigation, dans l'esprit de Gemini.
 *
 * Un bouton d'action proéminent en haut, puis l'historique. Le volet se replie
 * sous 1200 px : en dessous, la conversation a besoin de toute la largeur.
 *
 * Ce n'est pas un `navigation drawer` M3 au sens strict — M3 en attend un quand
 * il y a plusieurs destinations, alors qu'ici tout mène à la même vue. C'est un
 * volet d'historique, bâti sur les mêmes tokens.
 */
export function NavDrawer({
  threads,
  activeId,
  open,
  onSelect,
  onToggle,
}: {
  threads: Thread[];
  activeId: string;
  open: boolean;
  onSelect: (id: string) => void;
  onToggle: () => void;
}) {
  return (
    <aside className={`gl-drawer ${open ? 'is-open' : 'is-collapsed'}`}>
      <div className="gl-drawer-head">
        <button
          type="button"
          className="gl-icon-button gl-state-layer"
          onClick={onToggle}
          aria-label={open ? 'Replier le volet' : 'Déplier le volet'}
          aria-expanded={open}
        >
          <Icon name="menu" size={22} />
        </button>
      </div>

      <button type="button" className="gl-new-analysis gl-label-large gl-state-layer">
        <Icon name="add" size={20} />
        {open && <span>Nouvelle analyse</span>}
      </button>

      {open && (
        <nav className="gl-thread-list" aria-label="Analyses récentes">
          <p className="gl-label-medium gl-drawer-legend">Récent</p>
          {threads.map((thread) => (
            <button
              key={thread.id}
              type="button"
              className={`gl-thread gl-state-layer ${thread.id === activeId ? 'is-active' : ''}`}
              aria-current={thread.id === activeId ? 'true' : undefined}
              onClick={() => onSelect(thread.id)}
            >
              <Icon name="document" size={18} />
              <span className="gl-thread-text">
                <span className="gl-body-medium gl-thread-title">{thread.title}</span>
                <span className="gl-body-small gl-thread-sub">{thread.subtitle}</span>
              </span>
            </button>
          ))}
        </nav>
      )}

      {open && (
        <p className="gl-body-small gl-drawer-foot">
          Triage en amont, pas un avis juridique.
        </p>
      )}
    </aside>
  );
}
