import { useState } from 'react';

import type { TextFieldElement } from '../custom-elements';
import { VERDICTS, VERDICT_STYLES, type Verdict } from '../theme/verdicts';
import { TIER_LABELS, TYPE_LABELS, type Finding, type Report } from '../types';
import { Icon } from './Icon';
import { StateLayer } from './StateLayer';
import { VerdictChip } from './VerdictChip';

/**
 * Le rapport de clearance, rendu **dans** la réponse de l'assistant.
 *
 * C'est ainsi que Gemini rend un résultat structuré : pas un lien vers un autre
 * écran, mais du contenu riche posé dans la conversation. Un rapport de
 * clearance est une donnée structurée — verdicts, sources, occurrences — donc
 * il garde ses affordances de lecture : filtres par verdict, et une entité qui
 * s'ouvre sur place plutôt que de pousser vers une autre vue.
 */
/**
 * Réduit un texte à ce qui se compare : casse, accents et ponctuation sautent.
 *
 * Sans ça, chercher « oxycontin » ne trouverait pas « OxyContin », et « paper »
 * raterait « The Paper Lantern ». Un scénariste tape le nom dont il se souvient,
 * pas celui qui est écrit.
 */
const fold = (text: string) =>
  text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

export function ReportCard({ report }: { report: Report }) {
  const [active, setActive] = useState<Set<Verdict>>(new Set());
  const [query, setQuery] = useState('');
  const [openId, setOpenId] = useState<string | null>(report.findings[0]?.id ?? null);

  const counts = Object.fromEntries(VERDICTS.map((v) => [v, 0])) as Record<Verdict, number>;
  for (const f of report.findings) counts[f.verdict as Verdict] += 1;

  // Le rapport arrive déjà trié par sévérité puis par présence de sources :
  // cet ordre appartient au backend, on filtre sans jamais retrier.
  const needle = fold(query);
  const visible = report.findings.filter((f) => {
    if (active.size > 0 && !active.has(f.verdict as Verdict)) return false;
    if (!needle) return true;
    // Le nom, ses variantes d'écriture, et la catégorie telle qu'elle est
    // affichée : les trois choses qu'on a sous les yeux quand on cherche.
    const haystack = fold(
      [f.name, ...f.aliases, TYPE_LABELS[f.type] ?? f.type].join(' '),
    );
    return haystack.includes(needle);
  });

  const toggleFilter = (verdict: Verdict) =>
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(verdict)) next.delete(verdict);
      else next.add(verdict);
      return next;
    });

  return (
    <div className="gl-report">
      <div className="gl-report-stats">
        <Stat value={report.stats.entities} label="entités" />
        <Stat value={report.stats.flagged} label="à traiter" accent />
        <Stat value={report.stats.resolvedByRule} label="sans recherche" />
        <Stat value={report.stats.escalated} label="verdicts remontés" />
      </div>

      {/* Vingt-six entités ne se parcourent pas à l'œil. Le champ ne trie pas et
          ne réordonne rien : il ne fait que réduire ce qui est déjà là, pour
          que l'ordre du rapport reste celui du backend. */}
      {report.findings.length > 8 && (
        <md-outlined-text-field
          className="gl-report-search"
          label="Chercher une entité"
          value={query}
          onInput={(e) => setQuery((e.currentTarget as TextFieldElement).value)}
        >
          <Icon name="search" size={20} slot="leading-icon" />
        </md-outlined-text-field>
      )}

      {/* Des filter chips M3, au sens propre : la librairie porte la coche de
          sélection, le `aria-pressed`, la couche d'état et la navigation au
          clavier dans le jeu de puces. */}
      <md-chip-set className="gl-report-filters" aria-label="Filtrer par verdict">
        {VERDICTS.filter((v) => counts[v] > 0).map((verdict) => (
          <md-filter-chip
            key={verdict}
            className={`gl-filter is-${verdict.toLowerCase()}`}
            label={`${VERDICT_STYLES[verdict].label} (${counts[verdict]})`}
            selected={active.has(verdict)}
            onClick={() => toggleFilter(verdict)}
          >
            <Icon name={VERDICT_STYLES[verdict].icon} size={18} slot="icon" />
          </md-filter-chip>
        ))}
      </md-chip-set>

      <ul className="gl-findings">
        {visible.map((finding) => (
          <FindingRow
            key={finding.id}
            finding={finding}
            open={finding.id === openId}
            onToggle={() => setOpenId(finding.id === openId ? null : finding.id)}
          />
        ))}
      </ul>

      {visible.length === 0 && (
        <p className="gl-body-medium gl-empty">
          {needle
            ? `Aucune entité ne correspond à « ${query.trim()} ».`
            : 'Aucune entité ne correspond à ces filtres.'}
        </p>
      )}
    </div>
  );
}

function Stat({ value, label, accent }: { value: number; label: string; accent?: boolean }) {
  return (
    <div className={`gl-stat ${accent ? 'is-accent' : ''}`}>
      <span className="gl-headline-small">{value}</span>
      <span className="gl-label-medium">{label}</span>
    </div>
  );
}

/**
 * Une entité, repliée sur une ligne et dépliable sur place.
 *
 * L'ordre du détail est celui dans lequel un scénariste pose les questions :
 * qu'est-ce que je dois faire, pourquoi, et sur quelles preuves.
 */
function FindingRow({
  finding,
  open,
  onToggle,
}: {
  finding: Finding;
  open: boolean;
  onToggle: () => void;
}) {
  const verdict = finding.verdict as Verdict;
  const style = VERDICT_STYLES[verdict];

  return (
    <li className={`gl-finding ${open ? 'is-open' : ''}`}>
      <button
        type="button"
        className="gl-finding-head gl-state-layer"
        aria-expanded={open}
        onClick={onToggle}
      >
        {/* L'entité est rognée par sa carte : l'anneau de focus rentre à
            l'intérieur plutôt que d'être coupé. */}
        <StateLayer inward />
        <span
          className="gl-finding-rail"
          style={{ background: style.container }}
          aria-hidden="true"
        />
        <span className="gl-finding-id">
          <span className="gl-title-medium gl-finding-name">{finding.name}</span>
          <span className="gl-body-small gl-finding-meta">
            {TYPE_LABELS[finding.type] ?? finding.type}
            {' · '}
            {finding.scenes.length === 1
              ? `scène ${finding.scenes[0]}`
              : `scènes ${finding.scenes.join(', ')}`}
            {finding.escalatedFrom ? ' · verdict remonté' : ''}
            {finding.reusedFromPreviousDraft ? ' · repris' : ''}
          </span>
        </span>
        <VerdictChip verdict={verdict} dense />
        <Icon name={open ? 'expand_less' : 'expand_more'} size={20} />
      </button>

      {open && (
        <div className="gl-finding-detail">
          <p
            className="gl-body-large gl-detail-action"
            style={{ background: style.container, color: style.onContainer }}
          >
            {style.action}
          </p>

          <p className="gl-body-medium gl-detail-rationale">{finding.rationale}</p>

          {finding.escalatedFrom && (
            <p className="gl-body-small gl-detail-escalation">
              <Icon name="trending_up" />
              <span>
                Verdict remonté depuis{' '}
                <strong>{VERDICT_STYLES[finding.escalatedFrom].label}</strong> : les sources
                désignent une entité réelle précise, et la scène en fait le lieu d’un acte
                délictueux. L’existence et la dépiction sont deux signaux distincts, combinés ici.
              </span>
            </p>
          )}

          {finding.resolvedByRule && (
            <p className="gl-body-small gl-detail-rule">
              <Icon name="rule" />
              <span>Tranché par convention professionnelle, sans aucune recherche facturée.</span>
            </p>
          )}

          {finding.suggestedReplacement && (
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
          )}

          <div className="gl-detail-columns">
            <section>
              <h4 className="gl-label-large gl-detail-legend">
                Sources {finding.citations.length > 0 && `(${finding.citations.length})`}
              </h4>
              {finding.citations.length === 0 ? (
                <p className="gl-body-small gl-detail-muted">
                  Aucune source retenue. Un verdict défavorable sans source vérifiable est ramené
                  à « non tranché » plutôt qu’affirmé.
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
                        <Icon name="open_in_new" size={15} />
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <h4 className="gl-label-large gl-detail-legend">
                Dans le scénario ({finding.occurrences.length})
              </h4>
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
          </div>
        </div>
      )}
    </li>
  );
}
