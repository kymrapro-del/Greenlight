/**
 * Le rapport de clearance, en texte brut.
 *
 * C'est ce que le bouton « copier » met dans le presse-papiers, et le format
 * compte : ce texte finit collé dans un mail à un producteur ou dans un ticket.
 * Il doit donc se lire sans mise en forme, et porter les mêmes informations que
 * l'écran — verdict, raison, sources, scènes — dans le même ordre.
 *
 * L'ordre vient du rapport, pas d'un tri local : l'écran et le presse-papiers
 * doivent dire la même chose, sinon la copie n'est plus une copie.
 */
import { TIER_LABELS, TYPE_LABELS, type Report } from './types';
import { VERDICT_STYLES, type Verdict } from './theme/verdicts';

export function reportToText(report: Report): string {
  const lines: string[] = [
    `GREENLIGHT — pré-clearance`,
    report.title,
    `${report.sceneCount} scènes · ${report.stats.entities} entités · ` +
      `${report.stats.flagged} à traiter avant le tournage`,
  ];

  if (report.stats.escalated > 0) {
    lines.push(
      `${report.stats.escalated} verdicts remontés parce que la scène met l'entité en cause.`,
    );
  }
  if (report.diff) {
    lines.push(
      `Réécriture : ${report.diff.reanalyzed} entités réanalysées, ` +
        `${report.diff.reused} verdicts repris de la version précédente.`,
    );
  }
  if (report.placeholder) {
    lines.push(`⚠ Ce rapport n'a pas été produit par un appel réel aux API.`);
  }

  lines.push('', '─'.repeat(64), '');

  for (const finding of report.findings) {
    const style = VERDICT_STYLES[finding.verdict as Verdict];
    const scenes =
      finding.scenes.length === 1
        ? `scène ${finding.scenes[0]}`
        : `scènes ${finding.scenes.join(', ')}`;

    lines.push(`[${style.label.toUpperCase()}] ${finding.name}`);
    lines.push(`  ${TYPE_LABELS[finding.type] ?? finding.type} · ${scenes}`);
    lines.push(`  → ${style.action}`);
    if (finding.rationale) lines.push(`  ${finding.rationale}`);

    if (finding.escalatedFrom) {
      lines.push(
        `  Verdict remonté depuis « ${VERDICT_STYLES[finding.escalatedFrom].label} » : ` +
          `les sources désignent une entité réelle précise, et la scène la met en cause.`,
      );
    }
    if (finding.resolvedByRule) {
      lines.push(`  Tranché par convention professionnelle, sans recherche facturée.`);
    }
    if (finding.suggestedReplacement) {
      const mark = finding.replacementVerified
        ? 're-vérifié, la recherche ne le rattache à rien de réel'
        : 'NON VÉRIFIÉ, à relire avant de l’appliquer';
      lines.push(`  Remplacement proposé : ${finding.suggestedReplacement} (${mark})`);
    }

    if (finding.citations.length === 0) {
      lines.push(`  Sources : aucune retenue.`);
    } else {
      lines.push(`  Sources :`);
      for (const citation of finding.citations) {
        lines.push(`    - ${citation.title || citation.url}`);
        lines.push(`      ${citation.url}`);
      }
    }

    for (const occurrence of finding.occurrences) {
      lines.push(
        `  Scène ${occurrence.sceneNumber} — ${TIER_LABELS[occurrence.contextTier]} : ` +
          `« ${occurrence.quote} »`,
      );
    }
    lines.push('');
  }

  lines.push('─'.repeat(64));
  lines.push(
    `GREENLIGHT ne remplace pas le rapport de clearance exigé par l'assureur E&O,`,
    `et ne constitue pas un avis juridique.`,
  );

  return lines.join('\n');
}
