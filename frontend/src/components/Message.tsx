import { useState, type ReactNode } from 'react';

import { Icon } from './Icon';
import { StateLayer } from './StateLayer';

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

/**
 * Les actions sous une réponse.
 *
 * Une seule, et elle marche. La barre d'icônes de Gemini porte aussi deux
 * pouces ; ils n'avaient ici nulle part où envoyer un avis, et un bouton qui ne
 * fait rien est pire qu'un bouton absent — le premier visiteur clique dessus.
 *
 * Copier, en revanche, est exactement ce qu'on veut faire d'un rapport de
 * clearance : le coller dans un mail au producteur.
 */
export function ResponseActions({ note, copy }: { note?: string; copy?: () => string }) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    if (!copy) return;
    try {
      await navigator.clipboard.writeText(copy());
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Presse-papiers refusé (contexte non sécurisé, permission) : ne rien
      // afficher de faux. Le bouton reste dans son état initial.
    }
  };

  return (
    <div className="gl-response-actions">
      {copy && (
        <button
          type="button"
          className="gl-icon-button gl-state-layer"
          aria-label={copied ? 'Copié' : 'Copier'}
          onClick={onCopy}
        >
          <StateLayer />
          <Icon name={copied ? 'done' : 'copy'} size={18} />
        </button>
      )}
      {note && <span className="gl-body-small gl-response-note">{note}</span>}
    </div>
  );
}
