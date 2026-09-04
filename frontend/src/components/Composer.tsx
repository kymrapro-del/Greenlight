import { useRef, useState } from 'react';

import { Icon } from './Icon';
import { StateLayer } from './StateLayer';

/**
 * La barre de saisie.
 *
 * Une grande pilule qui porte ses actions à l'intérieur : le trombone à gauche,
 * le modèle et l'envoi à droite. Le bouton d'envoi n'apparaît qu'une fois du
 * texte saisi — tant qu'il n'y a rien à envoyer, il n'a pas de raison d'occuper
 * la place.
 *
 * Elle a deux régimes, et le placeholder dit lequel : tant qu'aucun rapport
 * n'existe dans le fil, ce qu'on envoie est un scénario ; ensuite, c'est une
 * question sur ce rapport. Un même champ qui ferait deux choses sans le dire
 * serait une interface qui piège son utilisateur.
 *
 * Le champ est un `textarea` qui grandit : on y colle un scénario entier, et
 * une ligne unique qui défile horizontalement rendrait ce geste illisible.
 */
export function Composer({
  mode,
  busy = false,
  autoFocus = false,
  onSend,
  onFile,
  model,
}: {
  mode: 'screenplay' | 'question';
  busy?: boolean;
  autoFocus?: boolean;
  onSend: (text: string) => void;
  onFile: (name: string, text: string) => void;
  model?: string;
}) {
  const [value, setValue] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  const canSend = value.trim().length > 0 && !busy;

  const submit = () => {
    if (!canSend) return;
    onSend(value.trim());
    setValue('');
  };

  return (
    <form
      className="gl-composer-field"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <input
        ref={fileInput}
        type="file"
        accept=".fountain,.txt,.spmd,text/plain"
        hidden
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          onFile(file.name, await file.text());
          e.target.value = '';
        }}
      />

      <button
        type="button"
        className="gl-icon-button gl-state-layer"
        aria-label="Joindre un scénario"
        disabled={busy}
        onClick={() => fileInput.current?.click()}
      >
        <StateLayer />
        <Icon name="attach" size={20} />
      </button>

      <textarea
        className="gl-body-large gl-composer-input"
        value={value}
        rows={1}
        disabled={busy}
        autoFocus={autoFocus}
        placeholder={
          mode === 'screenplay'
            ? 'Collez un scénario Fountain, ou joignez un fichier'
            : 'Posez une question sur ce rapport'
        }
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          // Entrée envoie, Maj+Entrée passe à la ligne : la convention d'un
          // champ de conversation, et il faut pouvoir coller du multiligne.
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        aria-label={mode === 'screenplay' ? 'Scénario' : 'Question'}
      />

      {/* Le modèle qui répond est une information, pas un réglage caché. */}
      {model && <span className="gl-model-select gl-label-large">{model}</span>}

      {canSend ? (
        <button type="submit" className="gl-send gl-state-layer" aria-label="Envoyer">
          <StateLayer />
          <Icon name="send" size={20} />
        </button>
      ) : (
        <button
          type="button"
          className="gl-icon-button gl-state-layer"
          aria-label="Joindre un scénario"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          <StateLayer />
          <Icon name="script" size={20} />
        </button>
      )}
    </form>
  );
}
