/** Contrat servi par `greenlight.api.report`. Une seule source de vérité. */

export type Verdict =
  | 'CHANGE_RECOMMENDED'
  | 'LICENSE_REQUIRED'
  | 'CAUTION'
  | 'UNRESOLVED'
  | 'CLEAR';

export type ContextTier = 'neutral' | 'unflattering' | 'illegal';

export interface Citation {
  url: string;
  title: string;
  excerpt: string;
  publishDate: string | null;
}

export interface Occurrence {
  sceneId: string;
  sceneNumber: number;
  contextTier: ContextTier;
  quote: string;
}

export interface Finding {
  id: string;
  entityId: string;
  name: string;
  type: string;
  aliases: string[];
  verdict: Verdict;
  confidence: number;
  rationale: string;
  contextTier: ContextTier;
  /** Verdict avant la règle de dépiction, quand elle l'a fait monter. */
  escalatedFrom: Verdict | null;
  searchMode: string | null;
  resolvedByRule: boolean;
  suggestedReplacement: string | null;
  replacementVerified: boolean;
  /** Verdict repris de la version précédente, sans nouvelle recherche. */
  reusedFromPreviousDraft: boolean;
  scenes: number[];
  occurrences: Occurrence[];
  citations: Citation[];
}

export interface ReportStats {
  entities: number;
  flagged: number;
  resolvedByRule: number;
  servedFromCache: number;
  billedSearches: number;
  droppedHallucinations: number;
  escalated: number;
  elapsedS: number;
}

export interface Report {
  /** Vrai tant que le rapport n'a pas été produit par un vrai passage. */
  placeholder: boolean;
  title: string;
  draftId: string;
  sceneCount: number;
  stats: ReportStats;
  usage: { search: Record<string, number | string>; gemini: Record<string, number | string> };
  findings: Finding[];
  diff?: {
    summary: string;
    reanalyzed: number;
    reused: number;
    added: string[];
    recontextualized: string[];
    removed: string[];
  };
}

export const TYPE_LABELS: Record<string, string> = {
  CHARACTER_NAME: 'Personnage',
  BUSINESS: 'Entreprise',
  PRODUCT_BRAND: 'Marque',
  PHONE: 'Téléphone',
  ADDRESS: 'Adresse',
  LICENSE_PLATE: 'Plaque',
  URL_EMAIL: 'URL / e-mail',
  SONG: 'Chanson',
  ARTWORK: 'Œuvre',
  PUBLICATION: 'Publication',
  INSTITUTION: 'Institution',
  REAL_PERSON: 'Personne réelle',
  REAL_EVENT: 'Événement réel',
  SPORTS_TEAM: 'Équipe sportive',
  VEHICLE: 'Véhicule',
  GOVERNMENT_AGENCY: 'Organisme public',
};

export const TIER_LABELS: Record<ContextTier, string> = {
  neutral: 'Dépiction neutre',
  unflattering: 'Dépiction défavorable',
  illegal: 'Acte délictueux dans la scène',
};
