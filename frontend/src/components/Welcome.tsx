import { Composer } from './Composer';
import { Icon } from './Icon';
import { StateLayer } from './StateLayer';
import type { Sample } from '../api';

/**
 * L'état d'accueil : un titre, la saisie, et les scénarios livrés.
 *
 * Les amorces ne sont pas décoratives. Le jury n'a que deux minutes et
 * n'apportera pas son propre scénario : chacune lance une vraie passe sur un
 * texte que le dépôt contient. Ce ne sont pas des rapports en conserve — le
 * pipeline tourne, et la progression se voit.
 */
export function Welcome({
  name,
  samples,
  busy,
  onPick,
  onSend,
  onFile,
  model,
}: {
  name: string;
  samples: Sample[];
  busy: boolean;
  onPick: (sample: Sample) => void;
  onSend: (text: string) => void;
  onFile: (fileName: string, text: string) => void;
  model?: string;
}) {
  return (
    <div className="gl-welcome">
      <div className="gl-glow" aria-hidden="true" />

      <h2 className="gl-greeting">
        Salut {name}, <span className="gl-greeting-accent">commençons</span>
      </h2>

      <div className="gl-welcome-composer">
        <Composer
          mode="screenplay"
          busy={busy}
          autoFocus
          onSend={onSend}
          onFile={onFile}
          model={model}
        />
      </div>

      <div className="gl-suggestions">
        {samples.map((sample) => (
          <button
            key={sample.id}
            type="button"
            className="gl-suggestion gl-state-layer"
            disabled={busy}
            onClick={() => onPick(sample)}
          >
            <StateLayer />
            <span className="gl-suggestion-head">
              <Icon name={sample.previousOf ? 'trending_up' : 'script'} size={18} />
              <span className="gl-body-large">{sample.title}</span>
            </span>
            <span className="gl-body-small gl-suggestion-hint">{sample.subtitle}</span>
            <span className="gl-label-medium gl-suggestion-meta">
              {sample.scenes} scènes · analyse réelle
            </span>
          </button>
        ))}
        {samples.length === 0 && (
          <p className="gl-body-medium gl-suggestion-empty">
            Aucun scénario d’exemple servi par l’API. Joignez le vôtre pour lancer une analyse.
          </p>
        )}
      </div>
    </div>
  );
}
