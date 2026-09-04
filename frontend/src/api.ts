/**
 * Le client de l'API GREENLIGHT.
 *
 * L'interface ne calcule rien et ne devine rien : elle dépose un scénario, lit
 * le flux de progression, et affiche ce que le serveur rend. L'ordre des
 * entités, les verdicts, les chiffres — tout appartient au backend. C'est ce
 * qui garantit que l'écran et le rapport disent la même chose.
 *
 * L'adresse du serveur vient de `VITE_API_BASE`. Vide, on tape la même origine :
 * c'est le cas du développement local avec le proxy Vite, et celui d'un
 * déploiement où l'API et l'interface partagent le domaine.
 */
import type { Report } from './types';

export const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

const url = (path: string) => `${API_BASE}${path}`;

export interface Health {
  status: string;
  /** Vrai quand l'instance appelle réellement Gemini et Parallel. */
  live: boolean;
  fixtureMode: 'live' | 'record' | 'replay';
  credentials: boolean;
  fixtures: { gemini: number; parallelSearch: number };
  /**
   * Faux quand l'instance rejoue le disque sans rien avoir enregistré : elle ne
   * peut alors produire aucun rapport, et l'écran doit le dire avant le clic.
   */
  canAnalyze: boolean;
  models: { extract: string; classify: string };
  runsHeld: number;
}

export interface Sample {
  id: string;
  title: string;
  subtitle: string;
  scenes: number;
  pages: number;
  previousOf: string | null;
}

export interface PhaseEvent {
  phase: string;
  message: string;
  [key: string]: unknown;
}

export interface Answer {
  answerable: boolean;
  answer: string;
  entityIds: string[];
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url(path), init);
  if (!response.ok) {
    // Le message du serveur plutôt qu'un code nu : « 404 » n'apprend rien à
    // celui qui lit l'écran.
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const getHealth = () => json<Health>('/api/health');
export const getSamples = () => json<Sample[]>('/api/samples');
export const getRun = (runId: string) => json<Report>(`/api/runs/${runId}`);

export const askAboutRun = (runId: string, question: string) =>
  json<Answer>('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runId, question }),
  });

export interface AnalyzeRequest {
  text?: string;
  sampleId?: string;
  previousRunId?: string;
}

export interface AnalyzeHandlers {
  onStarted?: (data: { scenes: number }) => void;
  onPhase?: (event: PhaseEvent) => void;
  signal?: AbortSignal;
}

/**
 * Lance une analyse et rend le rapport, en signalant chaque phase au passage.
 *
 * Le flux est du `text/event-stream` lu à la main plutôt qu'avec `EventSource` :
 * celui-ci ne sait faire que du GET, or une analyse envoie un scénario entier en
 * corps de requête. Le découpage ci-dessous est le format SSE, rien de plus —
 * des blocs séparés par une ligne vide, `event:` puis `data:`.
 */
export async function analyze(
  request: AnalyzeRequest,
  handlers: AnalyzeHandlers = {},
): Promise<Report> {
  const response = await fetch(url('/api/analyze'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal: handlers.signal,
  });
  if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let report: Report | null = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf('\n\n');

      let name = 'message';
      const data: string[] = [];
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) name = line.slice(7);
        else if (line.startsWith('data: ')) data.push(line.slice(6));
      }
      if (!data.length) continue;
      const payload = JSON.parse(data.join('\n'));

      if (name === 'started') handlers.onStarted?.(payload);
      else if (name === 'phase') handlers.onPhase?.(payload as PhaseEvent);
      else if (name === 'report') report = payload as Report;
      else if (name === 'error') throw new Error(payload.message);
    }
  }

  if (!report) throw new Error('Le serveur a fermé le flux sans rendre de rapport.');
  return report;
}
