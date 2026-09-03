import { Icon } from './Icon';
import { VERDICT_STYLES, type Verdict } from '../theme/verdicts';
import { TIER_LABELS, TYPE_LABELS, type Finding } from '../types';
import { VerdictChip } from './VerdictChip';

/**
 * Le volet détail.
 *
 * Il répond dans cet ordre à trois questions, parce que c'est l'ordre dans
 * lequel un scénariste les pose : qu'est-ce que je dois faire, pourquoi, et sur
 * quelles preuves. La trace d'escalade est affichée telle quelle — c'est le
 * raisonnement du système rendu visible, pas une couleur sortie d'une boîte
 * noire.
 */
export function FindingDetail({ finding }: { finding: Finding | null }) {
  if (!finding) {
    return (
      <div className="gl-detail gl-detail-empty">
        <Icon name="gavel" />
        <p className="gl-body-large">Sélectionnez une entité pour voir son verdict.</p>
      </div>
    );
  }

  const verdict = finding.verdict as Verdict;
  const style = VERDICT_STYLES[verdict];

  return (
    <article className="gl-detail" aria-live="polite">
      <header className="gl-detail-head">
        <VerdictChip verdict={verdict} />
        <h2 className="gl-headline-small gl-detail-title">{finding.name}</h2>
        <p className="gl-body-small gl-detail-sub">
          {TYPE_LABELS[finding.type] ?? finding.type}
          {finding.aliases.length > 0 && ` · aussi écrit ${finding.aliases.join(', ')}`}
        </p>
      </header>

      {/* 1. Ce qu'il faut faire. */}
      <p
        className="gl-body-large gl-detail-action"
        style={{ background: style.container, color: style.onContainer }}
      >
        {style.action}
      </p>

      {/* 2. Pourquoi. */}
      <section className="gl-detail-section">
        <h3 className="gl-label-large gl-detail-legend">Motif</h3>
        <p className="gl-body-medium">{finding.rationale}</p>

        {finding.escalatedFrom && (
          <p className="gl-body-small gl-detail-escalation">
            <Icon name="trending_up" />
            <span>
              Verdict remonté depuis{' '}
              <strong>{VERDICT_STYLES[finding.escalatedFrom].label}</strong> : les sources
              désignent une entité réelle précise, et la scène en fait le lieu d'un acte
              délictueux. L'existence et la dépiction sont deux signaux distincts, combinés ici.
            </span>
          </p>
        )}

        {finding.resolvedByRule && (
          <p className="gl-body-small gl-detail-rule">
            <Icon name="rule" />
            <span>Tranché par convention professionnelle, sans aucune recherche facturée.</span>
          </p>
        )}
      </section>

      {/* Le remplacement, quand il y en a un. */}
      {finding.suggestedReplacement && (
        <section className="gl-detail-section">
          <h3 className="gl-label-large gl-detail-legend">Remplacement proposé</h3>
          <div className="gl-replacement">
            <code className="gl-title-medium">{finding.suggestedReplacement}</code>
            <span
              className={`gl-label-small gl-replacement-mark ${
                finding.replacementVerified ? 'is-verified' : 'is-unverified'
              }`}
            >
              <Icon name={finding.replacementVerified ? 'verified' : 'help'} />
              {finding.replacementVerified
                ? 'Re-vérifié : la recherche ne le rattache à rien de réel'
                : 'Non vérifié — à relire avant de l’appliquer'}
            </span>
          </div>
        </section>
      )}

      {/* 3. Sur quelles preuves. */}
      <section className="gl-detail-section">
        <h3 className="gl-label-large gl-detail-legend">
          Sources {finding.citations.length > 0 && `(${finding.citations.length})`}
        </h3>
        {finding.citations.length === 0 ? (
          <p className="gl-body-small gl-detail-muted">
            Aucune source retenue. Un verdict défavorable sans source vérifiable est ramené à
            « non tranché » plutôt qu’affirmé.
          </p>
        ) : (
          <ul className="gl-citations">
            {finding.citations.map((citation) => (
              <li key={citation.url}>
                <a
                  className="gl-body-medium gl-citation-link"
                  href={citation.url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  {citation.title || citation.url}
                  <Icon name="open_in_new" />
                </a>
                {citation.excerpt && (
                  <p className="gl-body-small gl-citation-excerpt">{citation.excerpt}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Où ça apparaît dans le scénario. */}
      <section className="gl-detail-section">
        <h3 className="gl-label-large gl-detail-legend">
          Dans le scénario ({finding.occurrences.length})
        </h3>
        <ul className="gl-occurrences">
          {finding.occurrences.map((occurrence, i) => (
            <li key={`${occurrence.sceneId}-${i}`}>
              <span className="gl-label-medium gl-occurrence-scene">
                Scène {occurrence.sceneNumber}
              </span>
              <p className="gl-occurrence-quote">{occurrence.quote}</p>
              <span className="gl-body-small gl-detail-muted">
                {TIER_LABELS[occurrence.contextTier]}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}
