import { Composer } from './Composer';
import { StateLayer } from './StateLayer';

/**
 * L'état d'accueil : un titre, la saisie, et des amorces.
 *
 * Les amorces ne sont pas décoratives. Le jury n'a que deux minutes et ne va
 * pas déposer son propre scénario : chacune ouvre une analyse déjà calculée,
 * donc un rapport complet apparaît en un clic.
 */
export function Welcome({
  name,
  suggestions,
  onPick,
}: {
  name: string;
  suggestions: { id: string; label: string; hint: string }[];
  onPick: (id: string) => void;
}) {
  return (
    <div className="gl-welcome">
      <div className="gl-glow" aria-hidden="true" />

      <h2 className="gl-greeting">
        Salut {name}, <span className="gl-greeting-accent">commençons</span>
      </h2>

      <div className="gl-welcome-composer">
        <Composer disabled autoFocus />
      </div>

      <div className="gl-suggestions">
        {suggestions.map((s) => (
          <button
            key={s.id}
            type="button"
            className="gl-suggestion gl-state-layer"
            onClick={() => onPick(s.id)}
          >
            <StateLayer />
            <span className="gl-body-large">{s.label}</span>
            <span className="gl-body-small gl-suggestion-hint">{s.hint}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
