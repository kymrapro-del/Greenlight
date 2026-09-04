import { useEffect, useState } from 'react';

import { Composer } from './components/Composer';
import { DiffStrip } from './components/DiffStrip';
import { Icon } from './components/Icon';
import { AssistantMessage, ResponseActions, UserMessage } from './components/Message';
import { NavDrawer, type Thread } from './components/NavDrawer';
import { ReportCard } from './components/ReportCard';
import { Welcome } from './components/Welcome';
import type { Report } from './types';

/**
 * GREENLIGHT — interface conversationnelle.
 *
 * Deux états, comme un assistant : l'accueil, avec le titre et la saisie
 * centrés, et la conversation une fois qu'une analyse est ouverte.
 *
 * Le rapport de clearance est rendu **dans** la réponse plutôt que sur un autre
 * écran : c'est ainsi qu'un assistant rend un résultat structuré, et les
 * verdicts gardent leurs affordances de lecture sans quitter le fil.
 *
 * L'application ouvre directement sur une analyse. Le battle plan est
 * explicite : personne n'arrive sur un écran vide et n'attend un calcul.
 */
const THREADS: Thread[] = [
  { id: 'v1', title: 'Seventeen Minutes — pré-clearance v1' },
  { id: 'v2', title: 'Seventeen Minutes — réécriture v2' },
];

const SUGGESTIONS = [
  {
    id: 'v1',
    label: 'Analyser un scénario de 12 pages',
    hint: '15 entités · 10 à traiter avant le tournage',
  },
  {
    id: 'v2',
    label: 'Comparer deux versions',
    hint: '5 entités réanalysées sur 16 · 68 % de recherche évitée',
  },
];

const FILES: Record<string, string> = {
  v1: 'demo-report.json',
  v2: 'demo-report-v2.json',
};

export default function App() {
  const [threadId, setThreadId] = useState<string | null>('v1');
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!threadId) return;
    let cancelled = false;
    setReport(null);
    setError(null);

    fetch(FILES[threadId])
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: Report) => !cancelled && setReport(data))
      .catch((e: Error) => !cancelled && setError(e.message));

    return () => {
      cancelled = true;
    };
  }, [threadId]);

  const isRewrite = threadId === 'v2';

  return (
    <div className="gl-shell">
      <NavDrawer
        threads={THREADS}
        activeId={threadId}
        open={drawerOpen}
        onSelect={setThreadId}
        onNew={() => setThreadId(null)}
        onToggle={() => setDrawerOpen((v) => !v)}
      />

      <div className="gl-main">
        {threadId === null ? (
          <Welcome name="Kymra" suggestions={SUGGESTIONS} onPick={setThreadId} />
        ) : (
          <>
            <main className="gl-conversation">
              <div className="gl-conversation-column">
                <UserMessage>
                  {isRewrite
                    ? 'Voici la version 2 de Seventeen Minutes. Qu’est-ce qui change côté clearance ?'
                    : 'Analyse ce scénario avant qu’on le verrouille : Seventeen Minutes, 12 pages.'}
                </UserMessage>

                {error ? (
                  <AssistantMessage>
                    <p className="gl-body-large">Rapport indisponible : {error}</p>
                  </AssistantMessage>
                ) : !report ? (
                  <AssistantMessage pending />
                ) : (
                  <AssistantMessage>
                    <p className="gl-body-large gl-lede">
                      {isRewrite ? (
                        <>
                          La réécriture change {report.diff?.reanalyzed ?? 0} entités sur{' '}
                          {report.stats.entities}. J’ai repris les {report.diff?.reused ?? 0} autres
                          verdicts sans les recalculer, et il reste{' '}
                          <strong>{report.stats.flagged} points à traiter</strong> avant le
                          tournage.
                        </>
                      ) : (
                        <>
                          J’ai relevé <strong>{report.stats.entities} entités nommées</strong> dans
                          les {report.sceneCount} scènes. {report.stats.flagged} demandent une
                          action avant le tournage, dont {report.stats.escalated} dont le verdict
                          est monté d’un cran parce que la scène les met en cause.
                        </>
                      )}
                    </p>

                    {report.placeholder && (
                      <p className="gl-body-small gl-banner">
                        <Icon name="science" size={16} />
                        Données de démonstration : ce rapport vient du harnais de test hors ligne.
                        Les verdicts et les sources seront ceux d’un vrai passage une fois les
                        fixtures enregistrées.
                      </p>
                    )}

                    {report.diff && <DiffStrip diff={report.diff} />}

                    <ReportCard report={report} />

                    <ResponseActions
                      note={`${report.stats.resolvedByRule} entités tranchées par règle, sans recherche facturée.`}
                    />
                  </AssistantMessage>
                )}
              </div>
            </main>

            <div className="gl-composer">
              <Composer disabled />
              <p className="gl-body-small gl-composer-note">
                GREENLIGHT ne remplace pas le rapport de clearance exigé par l’assureur E&amp;O.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
