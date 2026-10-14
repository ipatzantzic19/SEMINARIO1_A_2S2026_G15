// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from './main';
import { clearSession, saveSession } from './session';

beforeEach(() => { clearSession(); window.history.replaceState({}, '', '/feed'); });
afterEach(() => cleanup());

it('redirige a login sin sesión y bloquea la ruta privada', async () => {
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Qué bueno verte.' })).toBeTruthy();
  expect(window.location.pathname).toBe('/login');
});

it('navega con sesión y logout limpia el estado', async () => {
  saveSession({ accessToken: 'mock', profileComplete: true });
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Tu comunidad, en un lugar.' })).toBeTruthy();
  fireEvent.click(screen.getByRole('link', { name: 'Personas' }));
  expect(await screen.findByRole('heading', { name: 'Conoce a tu gente.' })).toBeTruthy();
  await waitFor(() => expect(screen.getByText('1 persona de ejemplo')).toBeTruthy());
  fireEvent.click(screen.getByRole('button', { name: 'Salir' }));
  expect(await screen.findByRole('heading', { name: 'Qué bueno verte.' })).toBeTruthy();
  expect(sessionStorage.getItem('semisocial.session.v1')).toBeNull();
});
