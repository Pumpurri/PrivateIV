// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PausedDemo from './PausedDemo';

afterEach(cleanup);

it('explains the paused demo without collecting account information', () => {
  render(<MemoryRouter><PausedDemo /></MemoryRouter>);

  expect(screen.getByRole('heading', { name: 'La demo está en pausa' })).not.toBeNull();
  expect(screen.getByRole('link', { name: 'Ver vista previa' }).getAttribute('href')).toBe('/preview');
  expect(screen.queryByRole('textbox')).toBeNull();
  expect(screen.queryByRole('form')).toBeNull();
});
