import { useState } from 'react';

import { Icon } from './Icon';

/**
 * La barre de saisie, dans l'esprit de Gemini : une grande pilule posée en bas
 * de la conversation, avec les actions à l'intérieur plutôt qu'autour.
 *
 * Elle est volontairement désactivée sur la démonstration hors ligne : la
 * conversation est pré-calculée, et un champ qui accepte du texte sans rien en
 * faire serait un mensonge d'interface. Le placeholder le dit.
 */
export function Composer({
  disabled = false,
  onSend,
}: {
  disabled?: boolean;
  onSend?: (text: string) => void;
}) {
  const [value, setValue] = useState('');
  const canSend = value.trim().length > 0 && !disabled;

  const submit = () => {
    if (!canSend) return;
    onSend?.(value.trim());
    setValue('');
  };

  return (
    <div className="gl-composer">
      <form
        className="gl-composer-field"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <button
          type="button"
          className="gl-icon-button gl-state-layer"
          aria-label="Joindre un scénario"
          disabled={disabled}
        >
          <Icon name="attach" size={22} />
        </button>

        <input
          className="gl-body-large gl-composer-input"
          value={value}
          disabled={disabled}
          placeholder={
            disabled
              ? 'Démonstration hors ligne — la conversation est pré-calculée'
              : 'Déposez un scénario ou posez une question sur un verdict'
          }
          onChange={(e) => setValue(e.target.value)}
          aria-label="Message"
        />

        <button
          type="submit"
          className="gl-send gl-state-layer"
          disabled={!canSend}
          aria-label="Envoyer"
        >
          <Icon name="send" size={20} />
        </button>
      </form>

      <p className="gl-body-small gl-composer-note">
        GREENLIGHT ne remplace pas le rapport de clearance exigé par l’assureur E&amp;O.
      </p>
    </div>
  );
}
