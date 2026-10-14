// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, createClients } from './api';
import { readConfig } from './config';
import { clearSession, readSession, saveSession } from './session';

beforeEach(() => { sessionStorage.clear(); vi.restoreAllMocks(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('configuración y sesión', () => {
  it('separa las dos APIs y rechaza configuración incompleta', () => {
    const config = readConfig({ VITE_API_BASE_URL: 'https://alb.example/api/v1/', VITE_UPLOAD_BASE_URL: 'https://gateway.example/v1/', VITE_USE_MOCKS: 'false' });
    expect(config.apiBaseUrl).toBe('https://alb.example/api/v1');
    expect(config.uploadBaseUrl).toBe('https://gateway.example/v1');
    expect(() => readConfig({ VITE_USE_MOCKS: 'false' })).toThrow('VITE_API_BASE_URL');
  });
  it('limpia la sesión y tolera datos corruptos', () => {
    saveSession({ accessToken: 'jwt', profileComplete: true });
    expect(readSession()?.accessToken).toBe('jwt');
    clearSession();
    expect(readSession()).toBeNull();
    sessionStorage.setItem('semisocial.session.v1', '{bad');
    expect(readSession()).toBeNull();
  });
});

describe('clientes HTTP', () => {
  const config = { apiBaseUrl: 'https://alb.example/api/v1', uploadBaseUrl: 'https://gateway.example/v1', useMocks: false };
  it('envía negocio al ALB y subidas al API Gateway', async () => {
    saveSession({ accessToken: 'jwt', profileComplete: true });
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ items: [] }), { status: 200 })).mockResolvedValueOnce(new Response(JSON.stringify({ imageKey: 'Fotos_Publicadas/1', imageUrl: 'https://example.test/1' }), { status: 201 }));
    vi.stubGlobal('fetch', fetchMock);
    const clients = createClients(config);
    await clients.business('/posts');
    await clients.upload(new File(['image'], 'foto.png', { type: 'image/png' }), { purpose: 'post' });
    expect(fetchMock.mock.calls[0][0]).toBe('https://alb.example/api/v1/posts');
    expect(fetchMock.mock.calls[1][0]).toBe('https://gateway.example/v1/uploads/images');
    expect(fetchMock.mock.calls[1][1].body.get('purpose')).toBe('post');
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe('Bearer jwt');
  });
  it('elimina sesión ante 401 y comunica errores', async () => {
    saveSession({ accessToken: 'jwt', profileComplete: true });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ message: 'Sesión vencida' }), { status: 401 })));
    await expect(createClients(config).business('/me')).rejects.toMatchObject({ status: 401, message: 'Sesión vencida' });
    expect(readSession()).toBeNull();
  });
  it('no envía archivos mayores a 5 MiB', async () => {
    const large = new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'grande.png', { type: 'image/png' });
    await expect(createClients(config).upload(large, { purpose: 'post' })).rejects.toBeInstanceOf(ApiError);
  });
});
