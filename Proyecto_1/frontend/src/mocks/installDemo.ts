import { AxiosHeaders, type AxiosAdapter, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { api, uploads } from '../lib/api/client'
import type { Comment, FriendRequest, Message, Post, Profile, PublicUser, TokenSet } from '../lib/api/types'

// Se carga únicamente con `pnpm dev:demo`. No debe importarse desde rutas de producción.
const maria: PublicUser = { userId: '22222222-2222-4222-8222-222222222222', fullName: 'María Pérez', profileImageUrl: '/campus.jpg' }
const javier: PublicUser = { userId: '33333333-3333-4333-8333-333333333333', fullName: 'Javier López', profileImageUrl: '/campus.jpg' }
const lucia: PublicUser = { userId: '44444444-4444-4444-8444-444444444444', fullName: 'Lucía Castillo', profileImageUrl: '/campus.jpg' }
const sofia: PublicUser = { userId: '77777777-7777-4777-8777-777777777777', fullName: 'Sofía Morales', profileImageUrl: '/campus.jpg' }
const demoPeople = [maria, javier, lucia, sofia]
const accounts = new Map<string, { password: string; profile: Profile; confirmed: boolean }>()
const faceChallenges = new Map<string, { email: string; uploadToken: string; expiresAt: number }>()
let currentEmail: string | null = null
const posts: Post[] = [{ postId: '55555555-5555-4555-8555-555555555555', author: maria, imageUrl: '/campus.jpg', description: 'Una tarde en el campus para recordar.', labels: ['campus', 'amistad'], commentsCount: 1, createdAt: '2026-10-14T18:30:00Z' }]
const comments: Record<string, Comment[]> = { [posts[0].postId]: [{ commentId: '66666666-6666-4666-8666-666666666666', author: javier, body: '¡Qué bonita foto!', createdAt: '2026-10-14T18:35:00Z' }] }
const requests: FriendRequest[] = []
const friendIds = new Set([maria.userId])
const incomingSeededFor = new Set<string>()
const uploadsByKey = new Map<string, string>()

function currentAccount() {
  const account = currentEmail ? accounts.get(currentEmail) : undefined
  if (!account) failure('Inicia sesión con una cuenta creada en el modo demo.')
  return account
}
function currentProfile(): Profile { return currentAccount().profile }
function toPublicUser(profile: Profile): PublicUser {
  return {
    userId: profile.userId,
    fullName: profile.fullName,
    profileImageUrl: profile.profileImageUrl || '/campus.jpg',
  }
}
function ensureIncomingRequest() {
  const profile = currentProfile()
  if (incomingSeededFor.has(profile.userId)) return
  requests.push({
    requestId: `demo-incoming-${profile.userId}`,
    requester: sofia,
    addressee: toPublicUser(profile),
    status: 'pending',
    createdAt: new Date().toISOString(),
  })
  incomingSeededFor.add(profile.userId)
}
function pendingPeerIds(profile: Profile) {
  return new Set(
    requests
      .filter((request) => request.status === 'pending' && (request.requester.userId === profile.userId || request.addressee.userId === profile.userId))
      .map((request) => request.requester.userId === profile.userId ? request.addressee.userId : request.requester.userId),
  )
}
function visiblePosts() {
  const profile = currentProfile()
  return posts
    .filter((post) => post.author.userId === profile.userId || friendIds.has(post.author.userId))
    .sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt))
}
function visiblePost(postId: string) {
  const post = visiblePosts().find((item) => item.postId === postId)
  if (!post) failure('Publicación no encontrada o no autorizada.')
  return post
}
function tokens(profileComplete: boolean): TokenSet { return { accessToken: 'demo-access-token', idToken: 'demo-id-token', refreshToken: 'demo-refresh-token', expiresIn: 3600, tokenType: 'Bearer', profileComplete } }
function body(config: AxiosRequestConfig): Record<string, any> { return typeof config.data === 'string' ? JSON.parse(config.data) : config.data || {} }
function response<T>(config: AxiosRequestConfig, data: T, status = 200): AxiosResponse<T> { return { data, status, statusText: status === 201 ? 'Created' : 'OK', headers: {}, config: config as AxiosResponse<T>['config'] } }
function failure(message: string): never { throw new Error(message) }

const businessAdapter: AxiosAdapter = async (config) => {
  const method = config.method?.toUpperCase()
  const path = config.url || ''
  const data = body(config)
  if (method === 'POST' && path === '/auth/login') {
    const email = String(data.email).trim().toLowerCase()
    const account = accounts.get(email)
    if (!account || account.password !== data.password || !account.confirmed) failure('Credenciales inválidas o correo sin confirmar (modo demo).')
    currentEmail = email
    return response(config, tokens(account.profile.profileComplete))
  }
  if (method === 'POST' && path === '/auth/register') {
    const email = String(data.email).trim().toLowerCase()
    if (accounts.has(email)) failure('Este correo ya está registrado (modo demo).')
    const userId = crypto.randomUUID()
    accounts.set(email, { password: data.password, confirmed: false, profile: { userId, fullName: data.fullName, email, dpi: data.dpi, profileImageUrl: null, profileComplete: false } })
    return response(config, { userId, email, confirmationRequired: true, profileComplete: false }, 201)
  }
  if (method === 'POST' && path === '/auth/confirm') {
    const account = accounts.get(String(data.email).trim().toLowerCase())
    if (!account || !String(data.code).match(/^\d{6,8}$/)) failure('Código de prueba inválido: usa entre 6 y 8 dígitos.')
    account.confirmed = true
    return response(config, undefined, 204)
  }
  if (method === 'POST' && path === '/auth/face/challenges') {
    const email = String(data.email).trim().toLowerCase()
    const account = accounts.get(email)
    if (!account?.confirmed) failure('Para probar el acceso facial, crea y confirma una cuenta en modo demo.')
    const challengeId = crypto.randomUUID()
    const uploadToken = `face-${crypto.randomUUID()}`
    const expiresAt = Date.now() + 60_000
    faceChallenges.set(challengeId, { email, uploadToken, expiresAt })
    return response(config, { challengeId, uploadToken, expiresAt: new Date(expiresAt).toISOString() }, 201)
  }
  const faceVerification = path.match(/^\/auth\/face\/challenges\/([^/]+)\/verify$/)
  if (method === 'POST' && faceVerification) {
    const challenge = faceChallenges.get(decodeURIComponent(faceVerification[1]))
    if (!challenge || challenge.expiresAt < Date.now()) failure('El desafío facial venció o no existe (modo demo).')
    const account = accounts.get(challenge.email)
    if (!account?.confirmed) failure('La cuenta demo no está confirmada.')
    currentEmail = challenge.email
    faceChallenges.delete(decodeURIComponent(faceVerification[1]))
    return response(config, tokens(account.profile.profileComplete))
  }
  if (method === 'GET' && path === '/me') return response(config, currentProfile())
  if (method === 'POST' && path === '/me/complete-profile') { const profile = currentProfile(); profile.profileImageUrl = uploadsByKey.get(data.profileImageKey) || null; profile.profileComplete = true; return response(config, profile) }
  if (method === 'PATCH' && path === '/me') { const account = currentAccount(); const profile = account.profile; if (!data.currentPassword || data.currentPassword !== account.password) failure('Contraseña actual incorrecta (modo demo).'); profile.fullName = data.fullName || profile.fullName; profile.dpi = data.dpi || profile.dpi; if (data.profileImageKey) profile.profileImageUrl = uploadsByKey.get(data.profileImageKey) || null; return response(config, profile) }
  if (method === 'GET' && path === '/users') { ensureIncomingRequest(); const pending = pendingPeerIds(currentProfile()); return response(config, { items: demoPeople.filter((user) => !friendIds.has(user.userId) && !pending.has(user.userId)), nextCursor: null }) }
  if (method === 'GET' && path === '/friend-requests') { ensureIncomingRequest(); return response(config, requests) }
  if (method === 'POST' && path === '/friend-requests') { ensureIncomingRequest(); const profile = currentProfile(); const addressee = demoPeople.find((user) => user.userId === data.addresseeId); if (!addressee || addressee.userId === profile.userId || friendIds.has(addressee.userId)) failure('Usuario no disponible para solicitud.'); if (pendingPeerIds(profile).has(addressee.userId)) failure('Ya hay una solicitud pendiente.'); const request: FriendRequest = { requestId: crypto.randomUUID(), requester: toPublicUser(profile), addressee, status: 'pending', createdAt: new Date().toISOString() }; requests.push(request); return response(config, request, 201) }
  if (method === 'PATCH' && path.startsWith('/friend-requests/')) { const profile = currentProfile(); const request = requests.find((item) => item.requestId === path.split('/').at(-1)); if (!request || request.addressee.userId !== profile.userId || request.status !== 'pending') failure('Solicitud no encontrada o no autorizada.'); request.status = data.decision; if (data.decision === 'accepted') friendIds.add(request.requester.userId); return response(config, request) }
  if (method === 'GET' && path === '/friends') return response(config, demoPeople.filter((user) => friendIds.has(user.userId)))
  if (method === 'GET' && path === '/posts') return response(config, { items: visiblePosts().filter((post) => !config.params?.label || post.labels.includes(config.params.label)), nextCursor: null })
  if (method === 'POST' && path === '/posts') { const imageUrl = uploadsByKey.get(data.imageKey); if (!imageUrl) failure('La imagen debe cargarse antes de crear la publicación.'); const post: Post = { postId: crypto.randomUUID(), author: toPublicUser(currentProfile()), imageUrl, description: data.description, labels: [], commentsCount: 0, createdAt: new Date().toISOString() }; posts.unshift(post); return response(config, post, 201) }
  const commentsPath = path.match(/^\/posts\/([^/]+)\/comments$/)
  if (commentsPath && method === 'GET') { visiblePost(commentsPath[1]); return response(config, comments[commentsPath[1]] || []) }
  if (commentsPath && method === 'POST') { const post = visiblePost(commentsPath[1]); const comment: Comment = { commentId: crypto.randomUUID(), author: toPublicUser(currentProfile()), body: data.body, createdAt: new Date().toISOString() }; (comments[commentsPath[1]] ||= []).push(comment); post.commentsCount++; return response(config, comment, 201) }
  if (method === 'GET' && path === '/labels') { const counts = new Map<string, number>(); visiblePosts().forEach((post) => post.labels.forEach((label) => counts.set(label, (counts.get(label) || 0) + 1))); const query = String(config.params?.q || '').trim().toLowerCase(); return response(config, [...counts].map(([name, postCount]) => ({ name, postCount })).filter((item) => item.name.toLowerCase().includes(query)).sort((left, right) => left.name.localeCompare(right.name))) }
  if (method === 'POST' && path === '/translations') return response(config, { translatedText: `[Traducción simulada: ${data.targetLanguage}] ${data.text}`, sourceLanguage: 'es', targetLanguage: data.targetLanguage })
  if (method === 'POST' && path === '/bot/messages') { const text = String(data.text).toLowerCase(); const message = text.includes('horario') ? 'El horario de atención de la Facultad es de lunes a viernes, de 8:00 a 16:00.' : text.includes('admision') ? 'Consulta los requisitos y fechas vigentes con Control Académico de la Facultad.' : text.includes('contact') ? 'Puedes comunicarte con la Facultad mediante sus canales institucionales.' : 'No encontré una respuesta específica. Intenta consultar sobre horarios, admisiones o contacto.'; return response(config, { messages: [message], sessionId: data.sessionId }) }
  if (method === 'GET' && /^\/conversations\/[^/]+\/messages$/.test(path)) { const friendId = path.split('/')[2]; if (!friendIds.has(friendId)) failure('Solo puedes ver mensajes de tus amigos.'); const profile = currentProfile(); const messages: Message[] = [{ messageId: '88888888-8888-4888-8888-888888888888', senderId: maria.userId, recipientId: profile.userId, body: '¿Viste la publicación del campus?', createdAt: '2026-10-14T18:40:00Z' }]; return response(config, { items: messages.filter((message) => message.senderId === friendId || message.recipientId === friendId), nextCursor: null }) }
  return failure(`Ruta no simulada: ${method} ${path}`)
}

const uploadAdapter: AxiosAdapter = async (config) => {
  if (config.method?.toUpperCase() !== 'POST' || config.url !== '/uploads/images') failure('Ruta de upload no simulada.')
  const form = config.data as FormData
  const file = form.get('file')
  if (!(file instanceof File)) failure('Selecciona una imagen válida.')
  const purpose = form.get('purpose')
  if (purpose === 'faceCapture') {
    const challengeId = String(form.get('challengeId') || '')
    const challenge = faceChallenges.get(challengeId)
    const uploadToken = AxiosHeaders.from(config.headers).get('X-Face-Upload-Token')
    if (!challenge || challenge.expiresAt < Date.now() || challenge.uploadToken !== uploadToken) failure('Credencial facial temporal inválida.')
  }
  const imageKey = `demo/${crypto.randomUUID()}`
  const imageUrl = purpose === 'faceCapture' ? null : URL.createObjectURL(file)
  if (imageUrl) uploadsByKey.set(imageKey, imageUrl)
  return response(config, { imageKey, imageUrl }, 201)
}

api.defaults.adapter = businessAdapter
uploads.defaults.adapter = uploadAdapter
