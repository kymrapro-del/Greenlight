import { useEffect, useMemo, useState } from 'react';
import '@material/web/chips/chip-set.js';
import '@material/web/chips/filter-chip.js';
import '@material/web/progress/circular-progress.js';

import { DiffStrip } from './components/DiffStrip';
import { FindingDetail } from './components/FindingDetail';
import { Icon } from './components/Icon';
import { FindingList } from './components/FindingList';
import { VERDICTS, VERDICT_STYLES, type Verdict } from './theme/verdicts';
import type { Report } from './types';

/**
 * Écran Rapport — l'écran principal, en layout list-detail.
 *
 * Le rapport est pré-calculé et chargé d'emblée : personne n'arrive sur un
 * formulaire vide. La première entité à traiter est sélectionnée
 * automatiquement, pour qu'on voie un verdict complet dès la première seconde.
 */
/**
 * Les deux versions du scénario de démonstration.
 *
 * Basculer de l'une à l'autre est la démonstration du mode diff : la v2 est une
 * réécriture réelle — deux entités renommées, un numéro corrigé, une scène
 * ajoutée, et une entité conservée mais redépeinte.
 */
const DRAFTS = [
  { id: 'v1', label: 'Version 1', file: 'demo-report.json' },
  { id: 'v2', label: 'Version 2 · réécriture', file: 'demo-report-v2.json' },
] as const;

type DraftId = (typeof DRAFTS)[number]['id'];

export default function App() {
  const [draftId, setDraftId] = useState<DraftId>('v1');
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<Set<Verdict>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const draft = DRAFTS.find((d) => d.id === draftId)!;
    let cancelled = false;

    setReport(null);
    setError(null);

    fetch(draft.file)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: Report) => {
        // Une réponse arrivée après un changement de version ne doit pas
        // écraser celle de la version affichée.
        if (cancelled) return;
        setReport(data);
        // Le rapport est déjà trié par sévérité : la première ligne est celle
        // qui bloque le tournage.
        setSelectedId(data.findings[0]?.id ?? null);
      })
      .catch((e: Error) => !cancelled && setError(e.message));

    return () => {
      cancelled = true;
    };
  }, [draftId]);

  const counts = useMemo(() => {
    const out = Object.fromEntries(VERDICTS.map((v) => [v, 0])) as Record<Verdict, number>;
    for (const f of report?.findings ?? []) out[f.verdict as Verdict] += 1;
    return out;
  }, [report]);

  /**
   * Le rapport arrive déjà trié : sévérité, puis constats sourcés avant entités
   * tranchées par règle. Cette règle appartient au backend, qui seul connaît la
   * sévérité relative des verdicts — la redériver ici créerait deux ordres
   * concurrents, et c'est précisément ce qui a fait divergier la liste du
   * détail. On filtre, on ne retrie pas.
   */
  const visible = useMemo(() => {
    const findings = report?.findings ?? [];
    return active.size === 0
      ? findings
      : findings.filter((f) => active.has(f.verdict as Verdict));
  }, [report, active]);

  const selected = visible.find((f) => f.id === selectedId) ?? visible[0] ?? null;

  const toggle = (verdict: Verdict) => {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(verdict)) next.delete(verdict);
      else next.add(verdict);
      return next;
    });
  };

  if (error) {
    return (
      <main className="gl-state">
        <h1 className="gl-headline-small">Rapport indisponible</h1>
        <p className="gl-body-medium">{error}</p>
      </main>
    );
  }

  if (!report) {
    return (
      <main className="gl-state">
        <md-circular-progress indeterminate aria-label="Chargement du rapport" />
      </main>
    );
  }


  const { stats } = report;

  return (
    <div className="gl-app">
      {/* Top app bar — @material/web ne la livre pas, elle est bâtie sur les tokens. */}
      <header className="gl-topbar">
        <div className="gl-topbar-identity">
          <span className="gl-mark" aria-hidden="true" />
          <div>
            <h1 className="gl-title-large">GREENLIGHT</h1>
            <p className="gl-body-small gl-topbar-sub">
              {report.title} · {report.sceneCount} scènes · pré-clearance
            </p>
          </div>
        </div>

        <div className="gl-topbar-end">
          <div className="gl-draft-switch" role="group" aria-label="Version du scénario">
            {DRAFTS.map((draft) => (
              <button
                key={draft.id}
                type="button"
                className="gl-draft-option gl-label-large gl-state-layer"
                aria-pressed={draft.id === draftId}
                onClick={() => setDraftId(draft.id)}
              >
                {draft.label}
              </button>
            ))}
          </div>

          <dl className="gl-metrics">
            <Metric value={stats.entities} label="entités" />
            <Metric value={stats.flagged} label="à traiter" accent />
            <Metric value={stats.resolvedByRule} label="sans recherche" />
            <Metric value={stats.escalated} label="verdicts remontés" />
          </dl>
        </div>
      </header>

      {report.placeholder && (
        <p className="gl-banner gl-body-small" role="status">
          <Icon name="science" />
          Données de démonstration : ce rapport vient du harnais de test hors ligne. Les verdicts
          et les sources seront ceux d’un vrai passage une fois les fixtures enregistrées.
        </p>
      )}

      {report.diff && <DiffStrip diff={report.diff} />}

      <main className="gl-panes">
        <section className="gl-pane gl-pane-list" aria-label="Liste des entités">
          <md-chip-set className="gl-filters" aria-label="Filtrer par verdict">
            {VERDICTS.filter((v) => counts[v] > 0).map((verdict) => (
              <md-filter-chip
                key={verdict}
                label={`${VERDICT_STYLES[verdict].label} (${counts[verdict]})`}
                selected={active.has(verdict) || undefined}
                onClick={() => toggle(verdict)}
              />
            ))}
          </md-chip-set>

          <FindingList findings={visible} selectedId={selected?.id ?? null} onSelect={setSelectedId} />
        </section>

        <section className="gl-pane gl-pane-detail" aria-label="Détail du verdict">
          <FindingDetail finding={selected} />
        </section>
      </main>

      <footer className="gl-footer gl-body-small">
        Triage en amont, pas un avis juridique. GREENLIGHT ne remplace pas le rapport de clearance
        exigé par l’assureur E&amp;O : il attrape les problèmes pendant l’écriture, quand les
        corriger est encore gratuit.
      </footer>
    </div>
  );
}

function Metric({ value, label, accent }: { value: number; label: string; accent?: boolean }) {
  return (
    <div className={`gl-metric ${accent ? 'is-accent' : ''}`}>
      <dt className="gl-headline-medium">{value}</dt>
      <dd className="gl-label-medium">{label}</dd>
    </div>
  );
}
