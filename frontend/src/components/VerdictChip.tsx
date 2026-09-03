import { Icon } from './Icon';
import { VERDICT_STYLES, type Verdict } from '../theme/verdicts';

/**
 * La puce de verdict.
 *
 * Icône + libellé + couleur, toujours les trois. La couleur seule ne porte
 * jamais l'information : un rapport de clearance doit rester lisible en niveaux
 * de gris et pour quelqu'un qui distingue mal les teintes.
 */
export function VerdictChip({ verdict, dense = false }: { verdict: Verdict; dense?: boolean }) {
  const style = VERDICT_STYLES[verdict];
  return (
    <span
      className={`gl-verdict-chip ${dense ? 'gl-label-small' : 'gl-label-large'}`}
      style={{ background: style.container, color: style.onContainer }}
    >
      <Icon name={style.icon} />
      {style.label}
    </span>
  );
}
