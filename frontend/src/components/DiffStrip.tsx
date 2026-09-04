import { Icon } from './Icon';
import type { Report } from '../types';

/**
 * Le bandeau de diff.
 *
 * Il porte la démonstration centrale du mode réécriture : sur une nouvelle
 * version, seules les entités que la réécriture a réellement touchées repartent
 * dans le pipeline. Le chiffre affiché est celui du run, pas une estimation.
 *
 * Les trois listes sont montrées telles quelles parce qu'elles se lisent
 * différemment. « Nouvelles » et « disparues » se déduisent d'un simple diff de
 * noms ; « redépeintes » ne se déduit de rien — l'entité porte le même nom, mais
 * la scène en fait désormais autre chose. C'est le cas qu'un cache naïf raterait,
 * donc celui qu'il faut montrer.
 */
export function DiffStrip({ diff }: { diff: NonNullable<Report['diff']> }) {
  return (
    <section className="gl-diff" aria-label="Comparaison avec la version précédente">
      <p className="gl-diff-head gl-title-medium">
        <Icon name="trending_up" size={20} />
        {diff.summary}
      </p>

      <div className="gl-diff-groups">
        <DiffGroup
          label="Nouvelles"
          hint="absentes de la version précédente"
          names={diff.added}
          tone="added"
        />
        <DiffGroup
          label="Redépeintes"
          hint="même nom, la scène en fait autre chose"
          names={diff.recontextualized}
          tone="changed"
        />
        <DiffGroup
          label="Disparues"
          hint="corrigées ou coupées par la réécriture"
          names={diff.removed}
          tone="removed"
        />
      </div>
    </section>
  );
}

function DiffGroup({
  label,
  hint,
  names,
  tone,
}: {
  label: string;
  hint: string;
  names: string[];
  tone: 'added' | 'changed' | 'removed';
}) {
  if (names.length === 0) return null;
  return (
    <div className={`gl-diff-group is-${tone}`}>
      <p className="gl-label-large gl-diff-label">
        {label} ({names.length})
      </p>
      <p className="gl-body-small gl-diff-hint">{hint}</p>
      <ul className="gl-diff-names">
        {names.map((name) => (
          <li key={name} className="gl-body-medium">
            {name}
          </li>
        ))}
      </ul>
    </div>
  );
}
