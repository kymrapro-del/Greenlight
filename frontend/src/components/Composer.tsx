import { useState } from 'react';

import { Icon } from './Icon';
import { StateLayer } from './StateLayer';

/**
 * La barre de saisie.
 *
 * Une grande pilule qui porte ses actions à l'intérieur : ajout à gauche,
 * sélecteur de modèle et micro à droite. Le bouton d'envoi n'apparaît qu'une
 * fois du texte saisi — tant qu'il n'y a rien à envoyer, il n'a pas de raison
 * d'occuper la place.
 *
 * Elle est désactivée sur la démonstration hors ligne, et le placeholder le
 * dit : un champ qui accepte du texte sans rien en faire serait une interface
 * qui ment.
 */
export function Composer({
  disabled = false,
  autoFocus = false,
  onSend,
}: {
  disabled?: boolean;
  autoFocus?: boolean;
  onSend?: (text: string) => void;
}) {
  const [value, setValue] = useState('');
  const canSend = value.trim().length > 0 && !disabled;

  return (
    <form
      className="gl-composer-field"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSend) return;
        onSend?.(value.trim());
        setValue('');
      }}
    >
      <button
        type="button"
        className="gl-icon-button gl-state-layer"
        aria-label="Joindre un scénario"
        disabled={disabled}
      >
        <StateLayer />
        <Icon name="add" size={22} />
      </button>

      <input
        className="gl-body-large gl-composer-input"
        value={value}
        disabled={disabled}
        autoFocus={autoFocus}
        placeholder={
          disabled
            ? 'Démonstration hors ligne — les analyses sont pré-calculées'
            : 'Déposez un scénario ou posez une question sur un verdict'
        }
        onChange={(e) => setValue(e.target.value)}
        aria-label="Message"
      />

      {/* Le modèle qui répond est une information, pas un réglage caché. */}
      <button type="button" className="gl-model-select gl-label-large gl-state-layer">
        <StateLayer />
        Flash
        <Icon name="expand_more" size={18} />
      </button>

      {canSend ? (
        <button type="submit" className="gl-send gl-state-layer" aria-label="Envoyer">
          <StateLayer />
          <Icon name="send" size={20} />
        </button>
      ) : (
        <button
          type="button"
          className="gl-icon-button gl-state-layer"
          aria-label="Dicter"
          disabled={disabled}
        >
          <StateLayer />
          <Icon name="mic" size={20} />
        </button>
      )}
    </form>
  );
}
