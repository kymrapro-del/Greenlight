import { useCallback, useEffect, useRef, useState } from 'react';

import {
  analyze,
  askAboutRun,
  getHealth,
  getSamples,
  type Health,
  type PhaseEvent,
  type Sample,
} from './api';
import { Composer } from './components/Composer';
import { DiffStrip } from './components/DiffStrip';
import { Icon } from './components/Icon';
import { AssistantMessage, ResponseActions, UserMessage } from './components/Message';
import { NavDrawer, type Thread } from './components/NavDrawer';
import { ReportCard } from './components/ReportCard';
import { RunProgress } from './components/RunProgress';
import { StateLayer } from './components/StateLayer';
import { Welcome } from './components/Welcome';
import type { Report } from './types';

/**
 * GREENLIGHT — l'interface conversationnelle.
 *
 * Deux états, comme un assistant : l'accueil, titre et saisie centrés, puis la
 * conversation. Rien n'est pré-calculé — un scénario part vers l'API, les huit
 * phases tournent, la progression remonte pendant qu'elles tournent, et le
 * rapport s'affiche **dans** la réponse. C'est ainsi qu'un assistant rend un
 * résultat structuré, et les verdicts gardent leurs affordances de lecture sans
 * quitter le fil.
 *
 * Le fil garde son `runId` : une question de suivi s'y ancre, et une réécriture
 * s'y compare pour ne réanalyser que ce que le scénariste a réellement touché.
 */

type Turn =
  | { kind: 'user'; id: string; text: string }
  | {
      kind: 'analysis';
      id: string;
      status: 'running' | 'done' | 'error';
      scenes?: number;
      phases: PhaseEvent[];
      report?: Report;
      error?: string;
    }
  | {
      kind: 'answer';
      id: string;
      status: 'running' | 'done' | 'error';
      text?: string;
      entityIds?: string[];
      error?: string;
    };

interface Conversation {
  id: string;
  title: string;
  turns: Turn[];
  /** La dernière passe du fil : ce sur quoi portent les questions et le diff. */
  runId?: string;
  /** L'identifiant du scénario livré, quand le fil vient d'une amorce. */
  sampleId?: string;
}

const newId = () => Math.random().toString(36).slice(2, 10);

/**
 * Le titre du fil pour un scénario déposé : la page de titre Fountain quand
 * elle existe, sinon la première scène. Les capitales de la page de titre sont
 * ramenées à une casse de phrase — le volet ne crie pas.
 */
function title(text: string): string {
  const titled = /^\s*Title:\s*(.+)$/im.exec(text)?.[1]?.trim();
  const heading = /^\s*(INT\.|EXT\.)\s*(.+)$/im.exec(text)?.[2]?.trim();
  const raw = titled || heading || 'Scénario sans titre';
  return raw === raw.toUpperCase()
    ? raw.charAt(0) + raw.slice(1).toLowerCase()
    : raw;
}

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  // M3 : au-dessus de 840 dp le volet est permanent, en dessous il est modal et
  // donc fermé par défaut. La valeur initiale se lit avant le premier rendu
  // plutôt qu'après, pour ne pas montrer un volet qui se referme aussitôt.
  const [drawerOpen, setDrawerOpen] = useState(
    () => !window.matchMedia('(max-width: 839px)').matches,
  );
  const [samples, setSamples] = useState<Sample[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const active = conversations.find((c) => c.id === activeId) ?? null;

  useEffect(() => {
    Promise.all([getHealth(), getSamples()])
      .then(([h, s]) => {
        setHealth(h);
        setSamples(s);
        setReachable(true);
      })
      .catch(() => setReachable(false));
  }, []);

  // Le passage d'une classe de fenêtre à l'autre change la nature du volet :
  // permanent au-dessus de 840 dp, modal en dessous. L'état suit.
  useEffect(() => {
    const narrow = window.matchMedia('(max-width: 839px)');
    const sync = (e: MediaQueryListEvent | MediaQueryList) => setDrawerOpen(!e.matches);
    narrow.addEventListener('change', sync);
    return () => narrow.removeEventListener('change', sync);
  }, []);

  // La conversation suit le dernier tour, comme dans n'importe quel fil.
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [conversations, activeId]);

  const patch = useCallback((conversationId: string, change: Partial<Conversation>) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === conversationId ? { ...c, ...change } : c)),
    );
  }, []);

  const patchTurn = useCallback((conversationId: string, turnId: string, change: object) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id !== conversationId
          ? c
          : {
              ...c,
              turns: c.turns.map((t) => (t.id === turnId ? ({ ...t, ...change } as Turn) : t)),
            },
      ),
    );
  }, []);

  const append = useCallback((conversationId: string, ...turns: Turn[]) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === conversationId ? { ...c, turns: [...c.turns, ...turns] } : c)),
    );
  }, []);

  /** Lance une passe et raccroche chaque événement au tour qui l'attend. */
  const runAnalysis = useCallback(
    async (
      conversationId: string,
      request: { text?: string; sampleId?: string; previousRunId?: string },
      prompt: string,
    ) => {
      const analysisId = newId();
      append(
        conversationId,
        { kind: 'user', id: newId(), text: prompt },
        { kind: 'analysis', id: analysisId, status: 'running', phases: [] },
      );
      setBusy(true);

      try {
        const report = await analyze(request, {
          onStarted: ({ scenes }) => patchTurn(conversationId, analysisId, { scenes }),
          onPhase: (phase) =>
            setConversations((prev) =>
              prev.map((c) =>
                c.id !== conversationId
                  ? c
                  : {
                      ...c,
                      turns: c.turns.map((t) =>
                        t.id === analysisId && t.kind === 'analysis'
                          ? { ...t, phases: [...t.phases, phase] }
                          : t,
                      ),
                    },
              ),
            ),
        });
        patchTurn(conversationId, analysisId, { status: 'done', report });
        // Le titre du fil vient de l'amorce quand il y en a une : celui du
        // scénario est écrit en capitales sur sa page de titre, et le volet
        // n'a aucune raison de crier.
        patch(conversationId, { runId: report.runId });
        return report;
      } catch (error) {
        patchTurn(conversationId, analysisId, {
          status: 'error',
          error: error instanceof Error ? error.message : String(error),
        });
        return null;
      } finally {
        setBusy(false);
      }
    },
    [append, patch, patchTurn],
  );

  const startConversation = useCallback((title: string, sampleId?: string) => {
    const conversation: Conversation = { id: newId(), title, turns: [], sampleId };
    setConversations((prev) => [conversation, ...prev]);
    setActiveId(conversation.id);
    return conversation.id;
  }, []);

  /**
   * Une amorce lance une vraie passe. Pour la réécriture, la version 1 part
   * d'abord : le diff n'a de sens qu'avec une version précédente, et le montrer
   * en deux tours est exactement la démonstration qu'il faut faire.
   */
  const pickSample = useCallback(
    async (sample: Sample) => {
      const conversationId = startConversation(sample.title, sample.id);

      if (sample.previousOf) {
        const first = await runAnalysis(
          conversationId,
          { sampleId: sample.previousOf },
          'Analyse la première version avant qu’on la verrouille.',
        );
        if (!first?.runId) return;
        await runAnalysis(
          conversationId,
          { sampleId: sample.id, previousRunId: first.runId },
          'Voici la réécriture. Qu’est-ce qui change côté clearance ?',
        );
        return;
      }

      await runAnalysis(
        conversationId,
        { sampleId: sample.id },
        `Analyse ce scénario avant qu’on le verrouille : ${sample.title}.`,
      );
    },
    [runAnalysis, startConversation],
  );

  const submitScreenplay = useCallback(
    async (text: string, label: string) => {
      const conversationId =
        active?.runId || activeId === null ? startConversation(title(text)) : activeId;
      await runAnalysis(conversationId, { text }, label);
    },
    [active, activeId, runAnalysis, startConversation],
  );

  const submitQuestion = useCallback(
    async (question: string) => {
      if (!active?.runId) return;
      const answerId = newId();
      append(
        active.id,
        { kind: 'user', id: newId(), text: question },
        { kind: 'answer', id: answerId, status: 'running' },
      );
      setBusy(true);
      try {
        const answer = await askAboutRun(active.runId, question);
        patchTurn(active.id, answerId, {
          status: 'done',
          text: answer.answerable
            ? answer.answer
            : `${answer.answer}\n\nCette question sort de ce que le rapport contient.`,
          entityIds: answer.entityIds,
        });
      } catch (error) {
        patchTurn(active.id, answerId, {
          status: 'error',
          error: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setBusy(false);
      }
    },
    [active, append, patchTurn],
  );

  const send = (text: string) => {
    if (active?.runId) return submitQuestion(text);
    return submitScreenplay(text, 'Analyse ce scénario avant qu’on le verrouille.');
  };

  const receiveFile = (fileName: string, text: string) =>
    submitScreenplay(text, `Analyse ${fileName} avant qu’on le verrouille.`);

  // Un volet modal se referme sur le choix qu'on vient d'y faire ; un volet
  // permanent reste ouvert. Le même geste, deux comportements, comme M3 le veut.
  const closeIfModal = () => {
    if (window.matchMedia('(max-width: 839px)').matches) setDrawerOpen(false);
  };

  const threads: Thread[] = conversations.map((c) => ({ id: c.id, title: c.title }));
  const model = health?.models.classify;

  return (
    <div className="gl-shell">
      <NavDrawer
        threads={threads}
        activeId={activeId}
        open={drawerOpen}
        onSelect={(id) => {
          setActiveId(id);
          closeIfModal();
        }}
        onNew={() => {
          setActiveId(null);
          closeIfModal();
        }}
        onToggle={() => setDrawerOpen((v) => !v)}
      />

      {/* Le voile du volet modal. Il porte la fermeture, donc c'est un bouton :
          un `div` cliquable serait invisible au clavier et aux lecteurs. */}
      <button
        type="button"
        className={`gl-scrim ${drawerOpen ? 'is-visible' : ''}`}
        aria-label="Fermer le volet"
        tabIndex={drawerOpen ? 0 : -1}
        onClick={() => setDrawerOpen(false)}
      />

      <div className="gl-main">
        {/* Sur fenêtre étroite le bouton du volet part hors écran avec lui :
            cette barre le remet à portée. */}
        <header className="gl-topbar">
          <button
            type="button"
            className="gl-icon-button gl-state-layer"
            aria-label="Ouvrir le volet"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
          >
            <StateLayer />
            <Icon name="menu" size={20} />
          </button>
          <span className="gl-title-medium gl-topbar-title">
            {active?.title ?? 'GREENLIGHT'}
          </span>
        </header>

        {reachable === false && (
          <p className="gl-body-small gl-banner gl-offline" role="alert">
            <Icon name="cancel" size={16} />
            <span>
              L’API GREENLIGHT n’est pas joignable. L’interface ne montre pas de rapport en
              conserve à la place : il n’y a rien à analyser tant que le serveur ne répond pas.
            </span>
          </p>
        )}

        {/* Le diagnostic avant le clic. Laisser lancer une passe qui ne peut
            aboutir ferait perdre du temps et n'apprendrait rien. */}
        {health && !health.canAnalyze && (
          <p className="gl-body-small gl-banner gl-offline" role="alert">
            <Icon name="cancel" size={16} />
            {/* Un seul élément flex : sans ce span, chaque `code` deviendrait
                une colonne et la phrase se découperait en morceaux. */}
            <span>
              Ce serveur rejoue des appels enregistrés et n’en a aucun pour Gemini : toute analyse
              échouera. Renseignez <code>GOOGLE_API_KEY</code> et <code>PARALLEL_API_KEY</code>, ou
              enregistrez les fixtures avec <code>FIXTURE_MODE=record</code>.
            </span>
          </p>
        )}

        {active === null ? (
          <Welcome
            name="Kymra"
            samples={samples}
            busy={busy}
            onPick={pickSample}
            onSend={send}
            onFile={receiveFile}
            model={model}
          />
        ) : (
          <>
            <main className="gl-conversation">
              <div className="gl-conversation-column">
                {active.turns.map((turn) => (
                  <TurnView key={turn.id} turn={turn} live={health?.live ?? false} />
                ))}
                <div ref={bottom} />
              </div>
            </main>

            <div className="gl-composer">
              <Composer
                mode={active.runId ? 'question' : 'screenplay'}
                busy={busy}
                onSend={send}
                onFile={receiveFile}
                model={model}
              />
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

function TurnView({ turn, live }: { turn: Turn; live: boolean }) {
  if (turn.kind === 'user') return <UserMessage>{turn.text}</UserMessage>;

  if (turn.kind === 'answer') {
    if (turn.status === 'running') return <AssistantMessage pending />;
    return (
      <AssistantMessage>
        {turn.status === 'error' ? (
          <p className="gl-body-large">Réponse indisponible : {turn.error}</p>
        ) : (
          <>
            {turn.text?.split('\n\n').map((paragraph, i) => (
              <p key={i} className="gl-body-large">
                {paragraph}
              </p>
            ))}
            <ResponseActions />
          </>
        )}
      </AssistantMessage>
    );
  }

  if (turn.status === 'running') {
    return (
      <AssistantMessage>
        <RunProgress phases={turn.phases} scenes={turn.scenes} />
      </AssistantMessage>
    );
  }

  if (turn.status === 'error' || !turn.report) {
    return (
      <AssistantMessage>
        <p className="gl-body-large">L’analyse a échoué : {turn.error}</p>
      </AssistantMessage>
    );
  }

  const report = turn.report;
  const isRewrite = Boolean(report.diff);

  return (
    <AssistantMessage>
      <p className="gl-body-large gl-lede">
        {isRewrite ? (
          <>
            La réécriture change {report.diff?.reanalyzed ?? 0} entités sur {report.stats.entities}.
            J’ai repris les {report.diff?.reused ?? 0} autres verdicts sans les recalculer, et il
            reste <strong>{report.stats.flagged} points à traiter</strong> avant le tournage.
          </>
        ) : (
          <>
            J’ai relevé <strong>{report.stats.entities} entités nommées</strong> dans les{' '}
            {report.sceneCount} scènes. {report.stats.flagged} demandent une action avant le
            tournage, dont {report.stats.escalated} dont le verdict est monté d’un cran parce que
            la scène les met en cause.
          </>
        )}
      </p>

      {report.placeholder && (
        <p className="gl-body-small gl-banner">
          <Icon name="science" size={16} />
          <span>{live
            ? 'Passe réelle, mais le serveur la signale comme non validée.'
            : 'Le serveur ne joint pas les API : les huit phases tournent pour de vrai, les sources viennent du disque.'}</span>
        </p>
      )}

      {report.diff && <DiffStrip diff={report.diff} />}

      <ReportCard report={report} />

      <ResponseActions
        note={`${report.stats.resolvedByRule} entités tranchées par règle, sans recherche facturée · ${report.stats.elapsedS} s`}
      />
    </AssistantMessage>
  );
}
