import { afterEach, describe, expect, it } from 'vitest'
import { AxiosHeaders, type AxiosAdapter } from 'axios'
import { api, uploads } from './client'
import { endpoints } from './endpoints'
import { useSession } from '../../features/auth/session'

const originalApiAdapter = api.defaults.adapter
const originalUploadAdapter = uploads.defaults.adapter

afterEach(() => {
  api.defaults.adapter = originalApiAdapter
  uploads.defaults.adapter = originalUploadAdapter
  useSession.getState().clear()
})

describe('rutas del contrato HTTP', () => {
  it('registro envía solo los campos del contrato a /auth/register', async () => {
    let seenUrl = ''
    let seenBody = ''
    let seenBaseUrl: string | undefined
    api.defaults.adapter = (async (config) => {
      seenUrl = config.url || ''
      seenBody = config.data
      seenBaseUrl = config.baseURL
      return { data: { userId: 'id', email: 'ana@example.com', confirmationRequired: true, profileComplete: false }, status: 201, statusText: 'Created', headers: {}, config }
    }) satisfies AxiosAdapter

    await endpoints.register({ fullName: 'Ana García', email: 'ana@example.com', dpi: '1234567890101', password: 'claveSegura123' })
    expect(seenUrl).toBe('/auth/register')
    expect(seenBaseUrl).toBe(api.defaults.baseURL)
    expect(JSON.parse(seenBody)).toEqual({ fullName: 'Ana García', email: 'ana@example.com', dpi: '1234567890101', password: 'claveSegura123' })
  })

  it('captura facial usa el header efímero del contrato, no el bearer Cognito', async () => {
    let seenHeaders = new AxiosHeaders()
    let seenBaseUrl: string | undefined
    let seenData: unknown
    uploads.defaults.adapter = (async (config) => {
      seenHeaders = AxiosHeaders.from(config.headers)
      seenBaseUrl = config.baseURL
      seenData = config.data
      return { data: { imageKey: 'capture/key', imageUrl: '' }, status: 201, statusText: 'Created', headers: {}, config }
    }) satisfies AxiosAdapter

    useSession.getState().setTokens({ accessToken: 'cognito-access-token', idToken: 'id', refreshToken: 'refresh', expiresIn: 3600, tokenType: 'Bearer', profileComplete: true })
    await endpoints.upload('faceCapture', new File(['foto'], 'captura.jpg', { type: 'image/jpeg' }), { challengeId: 'challenge-id', uploadToken: 'efimero' })
    expect(seenHeaders.get('X-Face-Upload-Token')).toBe('efimero')
    expect(seenHeaders.get('Authorization')).toBeUndefined()
    expect(seenBaseUrl).toBe(uploads.defaults.baseURL)
    expect(uploads).not.toBe(api)
    expect(seenData).toBeInstanceOf(FormData)
    const form = seenData as FormData
    expect(form.get('purpose')).toBe('faceCapture')
    expect(form.get('challengeId')).toBe('challenge-id')
  })

  it('completa el flujo facial mediante los endpoints proxy sin llamar Cognito desde la SPA', async () => {
    const requests: Array<{ method?: string; url?: string; data?: string }> = []
    api.defaults.adapter = (async (config) => {
      requests.push({ method: config.method, url: config.url, data: config.data })
      const isChallenge = config.url === '/auth/face/challenges'
      return {
        data: isChallenge
          ? {
              challengeId: 'challenge-id',
              uploadToken: 'upload-token',
              expiresAt: '2026-10-19T22:00:00Z',
            }
          : {
              accessToken: 'access-token',
              idToken: 'id-token',
              refreshToken: 'refresh-token',
              expiresIn: 3600,
              tokenType: 'Bearer',
              profileComplete: true,
            },
        status: isChallenge ? 201 : 200,
        statusText: isChallenge ? 'Created' : 'OK',
        headers: {},
        config,
      }
    }) satisfies AxiosAdapter

    const challenge = await endpoints.createFaceChallenge('ana@example.com')
    await endpoints.verifyFaceChallenge(
      challenge.challengeId,
      'Fotos_Perfil/captures/challenge-id/capture.webp',
    )

    expect(requests).toEqual([
      {
        method: 'post',
        url: '/auth/face/challenges',
        data: JSON.stringify({ email: 'ana@example.com' }),
      },
      {
        method: 'post',
        url: '/auth/face/challenges/challenge-id/verify',
        data: JSON.stringify({
          captureKey: 'Fotos_Perfil/captures/challenge-id/capture.webp',
        }),
      },
    ])
  })

  it('envía imageKey y contraseña actual según el contrato de perfil', async () => {
    const requests: Array<{ method?: string; url?: string; data?: string }> = []
    api.defaults.adapter = (async (config) => {
      requests.push({ method: config.method, url: config.url, data: config.data })
      return {
        data: {
          userId: 'user-1',
          fullName: 'Ana García',
          email: 'ana@example.com',
          dpi: '1234567890101',
          profileImageUrl: 'https://example.com/profile.webp',
          profileComplete: true,
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }) satisfies AxiosAdapter

    await endpoints.completeProfile('Fotos_Perfil/public/user-1/profile.webp')
    await endpoints.updateMe({
      fullName: 'Ana García',
      dpi: '1234567890101',
      profileImageKey: 'Fotos_Perfil/public/user-1/profile-2.webp',
      currentPassword: 'claveSegura123',
    })

    expect(requests).toEqual([
      {
        method: 'post',
        url: '/me/complete-profile',
        data: JSON.stringify({
          profileImageKey: 'Fotos_Perfil/public/user-1/profile.webp',
        }),
      },
      {
        method: 'patch',
        url: '/me',
        data: JSON.stringify({
          fullName: 'Ana García',
          dpi: '1234567890101',
          profileImageKey: 'Fotos_Perfil/public/user-1/profile-2.webp',
          currentPassword: 'claveSegura123',
        }),
      },
    ])
  })

  it('traducción usa la ruta y el payload del contrato compartido', async () => {
    let seenUrl = ''
    let seenBody = ''
    api.defaults.adapter = (async (config) => {
      seenUrl = config.url || ''
      seenBody = config.data
      return {
        data: {
          translatedText: 'Hello community',
          sourceLanguage: 'es',
          targetLanguage: 'en',
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }) satisfies AxiosAdapter

    await endpoints.translate('Hola comunidad', 'en')

    expect(seenUrl).toBe('/translations')
    expect(JSON.parse(seenBody)).toEqual({
      text: 'Hola comunidad',
      targetLanguage: 'en',
    })
  })

  it('bot conserva el sessionId del cliente en la ruta acordada', async () => {
    let seenUrl = ''
    let seenBody = ''
    api.defaults.adapter = (async (config) => {
      seenUrl = config.url || ''
      seenBody = config.data
      return {
        data: { messages: ['Respuesta'], sessionId: 'session-1' },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }) satisfies AxiosAdapter

    await endpoints.bot('¿Cuál es el horario?', 'session-1')

    expect(seenUrl).toBe('/bot/messages')
    expect(JSON.parse(seenBody)).toEqual({
      text: '¿Cuál es el horario?',
      sessionId: 'session-1',
    })
  })

  it('amistades usa las cinco operaciones del contrato compartido', async () => {
    const requests: Array<{
      method?: string
      url?: string
      params?: unknown
      data?: string
    }> = []
    api.defaults.adapter = (async (config) => {
      requests.push({
        method: config.method,
        url: config.url,
        params: config.params,
        data: config.data,
      })
      return {
        data:
          config.url === '/users'
            ? { items: [], nextCursor: null }
            : config.url === '/friends' ||
                (config.url === '/friend-requests' && config.method === 'get')
              ? []
              : {},
        status: config.method === 'post' ? 201 : 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }) satisfies AxiosAdapter

    await endpoints.users('cursor-2')
    await endpoints.requests()
    await endpoints.requestFriend('user-b')
    await endpoints.answerRequest('request-1', 'accepted')
    await endpoints.friends()

    expect(requests).toEqual([
      {
        method: 'get',
        url: '/users',
        params: { cursor: 'cursor-2', limit: 20 },
        data: undefined,
      },
      {
        method: 'get',
        url: '/friend-requests',
        params: undefined,
        data: undefined,
      },
      {
        method: 'post',
        url: '/friend-requests',
        params: undefined,
        data: JSON.stringify({ addresseeId: 'user-b' }),
      },
      {
        method: 'patch',
        url: '/friend-requests/request-1',
        params: undefined,
        data: JSON.stringify({ decision: 'accepted' }),
      },
      {
        method: 'get',
        url: '/friends',
        params: undefined,
        data: undefined,
      },
    ])
  })
})
