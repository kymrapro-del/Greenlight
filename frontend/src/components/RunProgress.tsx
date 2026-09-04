import type { PhaseEvent } from '../api';
import { Icon } from './Icon';

/**
 * Une passe qui tourne, pendant qu'elle tourne.
 *
 * Le plan de démonstration interdit la seconde d'écran de chargement muet, et
 * c'est ce composant qui l'évite : chaque phase apparaît dès que le serveur
 * l'annonce, la précédente se coche. On voit le travail, pas une attente.
 *
 * `md-linear-progress` en mode indéterminé, parce que c'est la vérité : le
 * serveur sait quelle phase il traverse, pas combien de temps il lui reste.
 * Afficher une barre qui se remplit serait inventer une estimation.
 */
export function RunProgress({ phases, scenes }: { phases: PhaseEvent[]; scenes?: number }) {
  return (
    <div className="gl-run" role="status" aria-live="polite">
      <md-linear-progress className="gl-run-bar" indeterminate />

      <ol className="gl-run-phases">
        {phases.map((phase, i) => {
          const done = i < phases.length - 1;
          return (
            <li key={`${phase.phase}-${i}`} className={done ? 'is-done' : 'is-current'}>
              <Icon name={done ? 'check_circle' : 'pending'} size={16} />
              <span className="gl-body-medium">{phase.message}</span>
            </li>
          );
        })}
      </ol>

      {phases.length === 0 && (
        <p className="gl-body-medium gl-run-wait">
          {scenes ? `${scenes} scènes à analyser…` : 'Lecture du scénario…'}
        </p>
      )}
    </div>
  );
}
