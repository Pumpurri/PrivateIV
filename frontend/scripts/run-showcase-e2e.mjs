import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendDir = fileURLToPath(new URL('../', import.meta.url));
const repositoryDir = path.dirname(frontendDir);
const temporaryDir = await mkdtemp(path.join(tmpdir(), 'investment-portfolio-showcase-'));
const password = randomBytes(24).toString('base64url');
const python = process.env.PYTHON_BIN || 'python';
const captureImage = process.argv.includes('--capture-image');
const environment = {
  ...process.env,
  SECRET_KEY: 'disposable-local-browser-test-key',
  DEBUG: 'True',
  DATABASE_URL: `sqlite:///${path.join(temporaryDir, 'showcase.sqlite3')}`,
  ALLOWED_HOSTS: '127.0.0.1,localhost',
  CORS_ALLOWED_ORIGINS: 'http://127.0.0.1:5173',
  CSRF_TRUSTED_ORIGINS: 'http://127.0.0.1:5173,http://127.0.0.1:8000',
  VITE_API_URL: 'http://127.0.0.1:8000/api',
  SHOWCASE_PASSWORD: password,
  SHOWCASE_EMAIL: 'showcase@example.invalid',
  ...(captureImage ? { SHOWCASE_IMAGE_PATH: path.join(repositoryDir, 'docs/images/authenticated-portfolio.png') } : {}),
};

function start(command, args, cwd, stdio = 'inherit') {
  const child = spawn(command, args, { cwd, env: environment, stdio });
  child.on('error', (error) => console.error(`${command}: ${error.message}`));
  return child;
}

async function run(command, args, cwd) {
  const child = start(command, args, cwd);
  const code = await new Promise((resolve) => child.once('close', resolve));
  if (code !== 0) throw new Error(`${command} exited with status ${code}`);
}

async function waitFor(url) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The development server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

let backend;
let frontend;
try {
  await run(python, ['backend/manage.py', 'migrate', '--noinput'], repositoryDir);
  await run(python, ['backend/manage.py', 'create_showcase_portfolio', '--confirm-disposable'], repositoryDir);

  backend = start(python, ['backend/manage.py', 'runserver', '127.0.0.1:8000', '--noreload'], repositoryDir, 'ignore');
  frontend = start(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5173', '--strictPort'], frontendDir, 'ignore');
  await Promise.all([
    waitFor('http://127.0.0.1:8000/healthz/'),
    waitFor('http://127.0.0.1:5173/login'),
  ]);
  await run('npx', ['playwright', 'test', '--config', 'playwright.config.mjs'], frontendDir);
} finally {
  backend?.kill('SIGTERM');
  frontend?.kill('SIGTERM');
  await rm(temporaryDir, { recursive: true, force: true });
}
