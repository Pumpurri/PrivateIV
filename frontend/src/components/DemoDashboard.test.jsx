// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DemoDashboard from './DemoDashboard';

afterEach(cleanup);

it('labels the public dashboard preview as fictional and read-only', () => {
  render(<MemoryRouter><DemoDashboard /></MemoryRouter>);

  expect(screen.getByText('Datos ficticios · Solo lectura')).not.toBeNull();
  expect(screen.getByText('S/ 30,080.50')).not.toBeNull();
  expect(screen.getAllByRole('row')).toHaveLength(5);
  expect(screen.queryByRole('textbox')).toBeNull();
});
