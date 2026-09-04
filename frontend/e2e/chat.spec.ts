import { expect, test } from '@playwright/test';

/**
 * Le parcours que fait un juge, dans l'ordre où il le fait.
 *
 * Chaque assertion porte sur une promesse que le produit tient à l'écran :
 * la progression se voit pendant qu'elle a lieu, le rapport arrive dans la
 * réponse, les entités se filtrent, et une question de suivi reçoit une réponse
 * ancrée dans ce rapport-là.
 */

test('une amorce lance une vraie passe, et le rapport arrive dans la réponse', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));

  await page.goto('/');
  await expect(page.getByRole('heading', { name: /commençons/i })).toBeVisible();

  await page.locator('.gl-suggestion').first().click();

  // La progression est visible PENDANT la passe : c'est la promesse du flux.
  await expect(page.locator('md-linear-progress')).toBeVisible();
  await expect(page.locator('.gl-run-phases li')).not.toHaveCount(0);

  await expect(page.locator('.gl-report')).toBeVisible({ timeout: 120_000 });

  // Les chiffres viennent du serveur : l'interface n'en calcule aucun.
  await expect(page.locator('.gl-stat').first()).toContainText('26');
  await expect(page.locator('.gl-finding')).toHaveCount(26);

  expect(errors).toEqual([]);
});

test('les composants Material Web sont réellement montés', async ({ page }) => {
  await page.goto('/');
  await page.locator('.gl-suggestion').first().click();
  await expect(page.locator('.gl-report')).toBeVisible({ timeout: 120_000 });

  // Un élément personnalisé non enregistré reste un HTMLElement inerte : il a
  // l'air correct dans le DOM et ne fait rien. C'est le mode de panne qu'on
  // veut voir échouer ici, et il ne casse aucun test unitaire.
  const registry = await page.evaluate(() =>
    [
      'md-ripple',
      'md-focus-ring',
      'md-chip-set',
      'md-filter-chip',
      'md-linear-progress',
      'md-outlined-text-field',
    ].filter((tag) => !customElements.get(tag)),
  );
  expect(registry).toEqual([]);

  // Et ceux qui sont montés à cet instant ont bien été promus. La barre de
  // progression n'en fait pas partie : la passe est finie, elle a disparu.
  const inert = await page.evaluate(() =>
    ['md-ripple', 'md-focus-ring', 'md-filter-chip', 'md-outlined-text-field'].filter((tag) => {
      const el = document.querySelector(tag);
      return !el || el.constructor.name === 'HTMLElement';
    }),
  );
  expect(inert).toEqual([]);
});

test('la recherche réduit le rapport sans le réordonner', async ({ page }) => {
  await page.goto('/');
  await page.locator('.gl-suggestion').first().click();
  await expect(page.locator('.gl-report')).toBeVisible({ timeout: 120_000 });

  const order = await page.locator('.gl-finding-name').allInnerTexts();

  await page.locator('.gl-report-search').click();
  await page.keyboard.type('chicago');
  const filtered = await page.locator('.gl-finding-name').allInnerTexts();

  expect(filtered.length).toBeGreaterThan(0);
  expect(filtered.length).toBeLessThan(order.length);
  // L'ordre appartient au backend : filtrer ne doit jamais le changer.
  expect(filtered).toEqual(order.filter((name) => filtered.includes(name)));

  // Une recherche sans résultat dit laquelle, plutôt que d'accuser les filtres.
  await page.keyboard.press('Control+A');
  await page.keyboard.type('zzzz');
  await expect(page.locator('.gl-empty')).toContainText('zzzz');
});

test('une question de suivi reçoit une réponse ancrée dans le rapport', async ({ page }) => {
  await page.goto('/');
  await page.locator('.gl-suggestion').first().click();
  await expect(page.locator('.gl-report')).toBeVisible({ timeout: 120_000 });

  // La saisie change de régime une fois qu'un rapport existe, et le dit.
  const field = page.locator('.gl-composer-input');
  await expect(field).toHaveAttribute('placeholder', /question sur ce rapport/i);

  await field.fill('Pourquoi le bar est-il en rouge ?');
  await page.locator('.gl-send').click();

  const answer = page.locator('.gl-turn.is-assistant').last();
  await expect(answer).toContainText(/verdict/i, { timeout: 60_000 });
});

test('le volet est modal sur téléphone et permanent au-delà', async ({ page }, testInfo) => {
  await page.goto('/');
  const drawer = page.locator('.gl-drawer');

  if (testInfo.project.name === 'phone') {
    await expect(drawer).toBeHidden();
    await page.locator('.gl-topbar .gl-icon-button').click();
    await expect(drawer).toBeVisible();
    // Le voile porte la fermeture : sans lui le volet piège l'utilisateur.
    await page.locator('.gl-scrim').click({ position: { x: 360, y: 700 } });
    await expect(drawer).toBeHidden();
  } else {
    await expect(drawer).toBeVisible();
    await expect(page.locator('.gl-topbar')).toBeHidden();
  }

  // Aucune mise en page ne doit déborder horizontalement, à aucune largeur.
  const overflows = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(overflows).toBe(false);
});
