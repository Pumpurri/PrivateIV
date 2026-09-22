import { expect, test } from '@playwright/test';
import process from 'node:process';

test('signs in, inspects a generated portfolio, and places a paper trade', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Correo electrónico').fill(process.env.SHOWCASE_EMAIL);
  await page.getByLabel('Contraseña', { exact: true }).fill(process.env.SHOWCASE_PASSWORD);
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('heading', { name: 'BolsaSim demo' })).toBeVisible();
  await expect(page.getByText('TWR anual').locator('..')).toContainText('%');

  await page.getByRole('link', { name: 'Ver detalle' }).click();
  await expect(page.getByText('Valor de la cuenta')).toBeVisible();
  await expect(page.getByLabel('Evolución del balance del portafolio')).toBeVisible();
  const chartDateLabels = page.getByLabel('Evolución del balance del portafolio')
    .locator('svg text[text-anchor="middle"]');
  await expect(chartDateLabels.nth(1)).toBeVisible();
  const chartDates = await chartDateLabels.allTextContents();
  expect(chartDates.length).toBeGreaterThan(1);
  expect(new Set(chartDates).size).toBe(chartDates.length);

  if (process.env.SHOWCASE_IMAGE_PATH) {
    await page.screenshot({ path: process.env.SHOWCASE_IMAGE_PATH, fullPage: true });
  }

  await page.getByRole('button', { name: 'Operar' }).click();
  await page.getByPlaceholder('Ingresa símbolo').fill('AAPL');
  await page.getByRole('button', { name: /AAPL.*Apple/ }).click();
  await page.getByRole('button', { name: 'Revisar orden' }).click();
  await page.getByRole('button', { name: 'Confirmar orden' }).click();
  await expect(page.getByRole('heading', { name: 'Orden Recibida' })).toBeVisible();
  await expect(page.getByText('COMPRAR 1 acciones de AAPL')).toBeVisible();
});
