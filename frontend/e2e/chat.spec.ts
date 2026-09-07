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

  // La progression est visible PENDANT la passe : c'est la promesse du flux.
  // L'observation démarre AVANT le clic — sinon le test court après une passe
  // qui peut se terminer plus vite que lui, et l'échec ne dit rien du produit.
  const progress = page.waitForSelector('md-linear-progress', { timeout: 30_000 });
  const phase = page.waitForSelector('.gl-run-phases li', { timeout: 30_000 });
  await page.locator('.gl-suggestion').first().click();
  await progress;
  await phase;

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

test('le bouton copier met le rapport dans le presse-papiers', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/');
  await page.locator('.gl-suggestion').first().click();
  await expect(page.locator('.gl-report')).toBeVisible({ timeout: 120_000 });

  await page.locator('.gl-response-actions button').first().click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());

  // Le presse-papiers doit dire la même chose que l'écran : le titre, le
  // compte, et chaque entité avec son verdict.
  expect(copied).toContain('GREENLIGHT');
  expect(copied).toContain('SEVENTEEN MINUTES');
  expect(copied).toContain('The Black Cat Tavern');
  expect(copied).toContain('À CHANGER');
  expect(copied).toContain("ne remplace pas le rapport de clearance");
});

test('le thème bascule et se souvient', async ({ page }, testInfo) => {
  await page.goto('/');
  const root = page.locator('html');
  const toggle = page.locator('.gl-account .gl-icon-button');

  // Sur téléphone le volet est modal : il faut l'ouvrir pour l'atteindre.
  const openDrawer = async () => {
    if (testInfo.project.name === 'phone') await page.locator('.gl-topbar .gl-icon-button').click();
  };
  await openDrawer();

  // Système au départ : aucun attribut imposé.
  await expect(root).not.toHaveAttribute('data-theme', /.*/);

  await toggle.click();
  await expect(root).toHaveAttribute('data-theme', 'light');
  await toggle.click();
  await expect(root).toHaveAttribute('data-theme', 'dark');

  // Le choix survit au rechargement — c'est une préférence, pas un état.
  await page.reload();
  await expect(root).toHaveAttribute('data-theme', 'dark');

  await openDrawer();
  await toggle.click();
  await expect(root).not.toHaveAttribute('data-theme', /.*/);
});

test('une URL de source au schéma dangereux ne devient jamais cliquable', async ({ page }) => {
  await page.goto('/');
  await page.locator('.gl-suggestion').first().click();
  await expect(page.locator('.gl-report')).toBeVisible({ timeout: 120_000 });
  await page.locator('.gl-finding.is-open').scrollIntoViewIfNeeded();

  // Le serveur de test rapporte délibérément une source en `javascript:`,
  // et le pipeline la laisse passer : il vérifie qu'une URL citée figure bien
  // dans les résultats, pas son schéma. Le filtre est côté interface, et sans
  // cette source hostile ce test ne prouverait rien.
  await expect(page.locator('.gl-citation-unsafe').first()).toBeVisible();
  await expect(page.locator('.gl-citation-unsafe').first()).toContainText('non ouvrable');

  // Et aucun lien du rapport ne porte autre chose que http(s).
  const schemes = await page.evaluate(() =>
    [...document.querySelectorAll('.gl-report a[href]')].map(
      (a) => new URL((a as HTMLAnchorElement).href).protocol,
    ),
  );
  expect(schemes.filter((p) => p !== 'http:' && p !== 'https:')).toEqual([]);
  expect(schemes.length).toBeGreaterThan(0); // il y a bien des liens légitimes
});
