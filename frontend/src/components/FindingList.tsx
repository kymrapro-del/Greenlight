import { VERDICT_STYLES, type Verdict } from '../theme/verdicts';
import { TYPE_LABELS, type Finding } from '../types';
import { VerdictChip } from './VerdictChip';

/**
 * Le volet liste du layout list-detail.
 *
 * Chaque ligne porte une barre latérale à la couleur du verdict : la sévérité
 * se lit au balayage, avant même d'avoir lu un nom. La sélection déclenche le
 * morphing de forme d'Expressive — le rayon s'ouvre, ce qui donne un retour
 * indépendant de la couleur.
 */
export function FindingList({
  findings,
  selectedId,
  onSelect,
}: {
  findings: Finding[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (findings.length === 0) {
    return (
      <p className="gl-body-medium gl-empty">
        Aucune entité ne correspond à ces filtres.
      </p>
    );
  }

  return (
    <ul className="gl-finding-list" role="listbox" aria-label="Entités analysées">
      {findings.map((finding) => {
        const selected = finding.id === selectedId;
        return (
          <li key={finding.id}>
            <button
              type="button"
              role="option"
              aria-selected={selected}
              data-selected={selected}
              className="gl-finding-row gl-shape-morph"
              onClick={() => onSelect(finding.id)}
            >
              <span
                className="gl-finding-rail"
                style={{ background: VERDICT_STYLES[finding.verdict as Verdict].container }}
                aria-hidden="true"
              />
              <span className="gl-finding-body">
                <span className="gl-finding-head">
                  <span className="gl-title-medium gl-finding-name">{finding.name}</span>
                  <VerdictChip verdict={finding.verdict as Verdict} dense />
                </span>
                <span className="gl-body-small gl-finding-meta">
                  {TYPE_LABELS[finding.type] ?? finding.type}
                  {' · '}
                  {finding.scenes.length === 1
                    ? `scène ${finding.scenes[0]}`
                    : `scènes ${finding.scenes.join(', ')}`}
                  {finding.escalatedFrom ? ' · verdict remonté' : ''}
                  {finding.reusedFromPreviousDraft && (
                    <span className="gl-reused" title="Verdict repris de la version précédente : rien n'a été recherché à nouveau">
                      {' · '}repris
                    </span>
                  )}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
