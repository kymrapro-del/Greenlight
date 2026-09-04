import type { ReactNode } from 'react';

import { Icon } from './Icon';

/**
 * Un tour de conversation.
 *
 * La dissymétrie est volontaire et reprend celle de Gemini : le message de
 * l'utilisateur est une bulle compacte alignée à droite, la réponse occupe
 * toute la colonne et n'a pas de bulle. Une réponse qui contient un rapport
 * entier ne tiendrait pas dans une bulle, et l'encadrer la ferait paraître
 * secondaire alors que c'est le contenu principal.
 */
export function UserMessage({ children }: { children: ReactNode }) {
  return (
    <div className="gl-turn is-user">
      <div className="gl-bubble gl-body-large">{children}</div>
    </div>
  );
}

export function AssistantMessage({
  children,
  pending = false,
}: {
  children?: ReactNode;
  pending?: boolean;
}) {
  return (
    <div className="gl-turn is-assistant">
      <span className="gl-avatar" aria-hidden="true">
        <span className="gl-avatar-mark" />
      </span>
      <div className="gl-response">
        {pending ? (
          <p className="gl-body-large gl-pending" role="status">
            <span className="gl-dot" />
            <span className="gl-dot" />
            <span className="gl-dot" />
            <span className="gl-visually-hidden">Analyse en cours</span>
          </p>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

/** Les actions sous une réponse, comme la barre d'icônes de Gemini. */
export function ResponseActions({ note }: { note?: string }) {
  return (
    <div className="gl-response-actions">
      {(['thumb_up', 'thumb_down', 'copy'] as const).map((name) => (
        <button
          key={name}
          type="button"
          className="gl-icon-button gl-state-layer"
          aria-label={
            name === 'thumb_up'
              ? 'Bonne réponse'
              : name === 'thumb_down'
                ? 'Mauvaise réponse'
                : 'Copier'
          }
        >
          <Icon name={name} size={18} />
        </button>
      ))}
      {note && <span className="gl-body-small gl-response-note">{note}</span>}
    </div>
  );
}
