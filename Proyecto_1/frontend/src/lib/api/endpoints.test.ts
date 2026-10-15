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
})
