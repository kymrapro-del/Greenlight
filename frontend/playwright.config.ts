import { defineConfig, devices } from '@playwright/test';

/**
 * Le test de bout en bout : le vrai front compilé, contre le vrai serveur.
 *
 * Deux serveurs sont démarrés. L'API est `greenlight.api.server` tel quel, avec
 * les deux transports sortants scriptés depuis l'arbre de tests — le pipeline,
 * les huit phases et la sérialisation sont réels, seul le réseau ne l'est pas.
 * Le front est le bundle de production, pas le serveur de développement : c'est
 * ce bundle-là qui est déployé.
 *
 * Ce que ce test attrape et qu'aucun test unitaire ne voit : un flux SSE mal
 * découpé, un composant Material Web qui ne s'enregistre plus, une mise en page
 * qui déborde sur un téléphone.
 */
/**
 * Certains environnements fournissent déjà un Chromium, à une version qui n'est
 * pas celle que ce paquet télécharge. `PLAYWRIGHT_CHROMIUM_PATH` pointe dessus
 * plutôt que d'exiger un second téléchargement ; vide, Playwright utilise le
 * sien, ce que fait la CI.
 */
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH;
const launchOptions = executablePath ? { executablePath } : undefined;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',

  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    // Les polices Google sont injoignables dans plusieurs des environnements où
    // ce test tourne. Les captures doivent rester lisibles quand même.
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 }, launchOptions },
    },
    { name: 'phone', use: { ...devices['Pixel 7'], launchOptions } },
  ],

  webServer: [
    {
      command:
        'cd .. && PYTHONPATH=backend:. .venv/bin/python -m uvicorn tests.e2e_server:app --port 8001',
      url: 'http://127.0.0.1:8001/api/health',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: 'npm run build && npm run preview -- --port 4173',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: { VITE_API_BASE: 'http://127.0.0.1:8001' },
    },
  ],
});
