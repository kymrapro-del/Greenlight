import '@material/web/list/list.js';
import '@material/web/list/list-item.js';
import '@material/web/divider/divider.js';

import { VERDICT_STYLES, type Verdict } from '../theme/verdicts';
import { TYPE_LABELS, type Finding } from '../types';
import { VerdictChip } from './VerdictChip';

/**
 * Le volet liste, sur `md-list` / `md-list-item`.
 *
 * Ce sont les composants de la librairie officielle, pas une liste faite main.
 * La différence n'est pas cosmétique : `md-list-item` en `type="button"` apporte
 * le ripple, la state layer et l'anneau de focus de M3, plus la sémantique
 * clavier — flèches haut/bas, `Home`, `End` — que `md-list` gère pour nous. Une
 * réimplémentation aurait eu à refaire tout ça, moins bien.
 *
 * Chaque ligne porte une barre latérale à la couleur du verdict : la sévérité
 * se lit au balayage, avant même d'avoir lu un nom.
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
    return <p className="gl-body-medium gl-empty">Aucune entité ne correspond à ces filtres.</p>;
  }

  return (
    <md-list className="gl-finding-list" aria-label="Entités analysées">
      {findings.map((finding, i) => {
        const selected = finding.id === selectedId;
        return (
          <div key={finding.id}>
            {i > 0 && <md-divider inset />}
            <md-list-item
              type="button"
              className="gl-finding-row"
              data-selected={selected ? 'true' : undefined}
              aria-current={selected ? 'true' : undefined}
              onClick={() => onSelect(finding.id)}
            >
              <span
                slot="start"
                className="gl-finding-rail"
                style={{ background: VERDICT_STYLES[finding.verdict as Verdict].container }}
                aria-hidden="true"
              />

              <span slot="headline" className="gl-finding-name">
                {finding.name}
              </span>

              <span slot="supporting-text" className="gl-finding-meta">
                {TYPE_LABELS[finding.type] ?? finding.type}
                {' · '}
                {finding.scenes.length === 1
                  ? `scène ${finding.scenes[0]}`
                  : `scènes ${finding.scenes.join(', ')}`}
                {finding.escalatedFrom ? ' · verdict remonté' : ''}
                {finding.reusedFromPreviousDraft && (
                  <span
                    className="gl-reused"
                    title="Verdict repris de la version précédente : rien n'a été recherché à nouveau"
                  >
                    {' · '}repris
                  </span>
                )}
              </span>

              <span slot="end">
                <VerdictChip verdict={finding.verdict as Verdict} dense />
              </span>
            </md-list-item>
          </div>
        );
      })}
    </md-list>
  );
}
