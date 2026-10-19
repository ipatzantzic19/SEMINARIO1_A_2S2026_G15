import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe, BadRequestException } from '@nestjs/common';
const request = require('supertest');
import { AppModule } from '../src/app.module';
import { DatabaseService } from '../src/database/database.service';

describe('Semi-Social Backend Node.js (E2E Tests - PRO-7 Cognito & Contract)', () => {
  let app: INestApplication;
  let databaseService: DatabaseService;

  beforeAll(async () => {
    // Configurar para ejecución de tests
    process.env.MOCK_MODE = 'true';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    databaseService = app.get(DatabaseService);

    app.setGlobalPrefix('api/v1', {
      exclude: ['health'],
    });

    app.useGlobalPipes(
      new ValidationPipe({
        whitelist: true,
        forbidNonWhitelisted: true,
        transform: true,
        exceptionFactory: (errors) => {
          const details = errors.map((err) => ({
            field: err.property,
            errors: Object.values(err.constraints || {}),
          }));
          return new BadRequestException({
            code: 'VALIDATION_ERROR',
            message: 'Los parámetros o cuerpo de la solicitud no cumplen con el formato requerido.',
            details,
          });
        },
      }),
    );

    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  describe('1. Endpoint de Salud (ALB Target Group)', () => {
    it('GET /health debe responder 200 OK en la raíz con el formato exacto del contrato', async () => {
      const response = await request(app.getHttpServer()).get('/health').expect(200);

      expect(response.body).toEqual({
        status: 'ok',
        service: 'node',
        version: '1.0.0',
      });
    });
  });

  describe('2. Flujo de Autenticación con Cognito (PRO-7)', () => {
    it('POST /api/v1/auth/register con datos válidos debe registrar usuario (201 Created)', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({
          fullName: 'Daniel Abraham Ortiz',
          email: 'daniel.test@ingenieria.usac.edu.gt',
          dpi: '1234567890101',
          password: 'PasswordSeguro2026!#',
        })
        .expect(201);

      expect(response.body).toHaveProperty('userId');
      expect(response.body.email).toBe('daniel.test@ingenieria.usac.edu.gt');
      expect(response.body.confirmationRequired).toBe(true);
      expect(response.body.profileComplete).toBe(false);
    });

    it('POST /api/v1/auth/register con contraseña menor a 12 caracteres debe fallar con 400 VALIDATION_ERROR', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({
          fullName: 'Daniel Ortiz',
          email: 'daniel@example.com',
          dpi: '1234567890101',
          password: 'Corta8!',
        })
        .expect(400);

      expect(response.body.code).toBe('VALIDATION_ERROR');
    });

    it('POST /api/v1/auth/confirm debe responder 204 No Content', async () => {
      await request(app.getHttpServer())
        .post('/api/v1/auth/confirm')
        .send({
          email: 'daniel.test@ingenieria.usac.edu.gt',
          code: '123456',
        })
        .expect(204);
    });

    it('POST /api/v1/auth/login con credenciales válidas debe retornar tokens', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/login')
        .send({
          email: 'daniel.test@ingenieria.usac.edu.gt',
          password: 'PasswordSeguro2026!#',
        })
        .expect(200);

      expect(response.body).toHaveProperty('accessToken');
      expect(response.body).toHaveProperty('idToken');
      expect(response.body).toHaveProperty('refreshToken');
      expect(response.body.tokenType).toBe('Bearer');
    });

    it('POST /api/v1/auth/face/challenges debe iniciar desafío facial', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/face/challenges')
        .send({
          email: 'daniel.test@ingenieria.usac.edu.gt',
        })
        .expect(200);

      expect(response.body).toHaveProperty('challengeId');
      expect(response.body).toHaveProperty('uploadToken');
      expect(response.body).toHaveProperty('expiresAt');
    });
  });

  describe('3. Perfil y Edición con Contraseña (PRO-7)', () => {
    it('GET /api/v1/me sin header Authorization debe responder 401 UNAUTHENTICATED', async () => {
      const response = await request(app.getHttpServer()).get('/api/v1/me').expect(401);
      expect(response.body.code).toBe('UNAUTHENTICATED');
    });

    it('GET /api/v1/me con Bearer token debe retornar datos del perfil', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/me')
        .set('Authorization', 'Bearer mock-valid-token')
        .expect(200);

      expect(response.body).toHaveProperty('userId');
      expect(response.body).toHaveProperty('email');
      expect(response.body).toHaveProperty('fullName');
      expect(response.body).toHaveProperty('dpi');
    });

    it('GET /api/v1/posts con perfil incompleto debe responder 403 FORBIDDEN (PROFILE_INCOMPLETE)', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/posts')
        .set('Authorization', 'Bearer mock-valid-token')
        .expect(403);

      expect(response.body.code).toBe('FORBIDDEN');
      expect(response.body.details).toEqual({ reason: 'PROFILE_INCOMPLETE' });
    });

    it('POST /api/v1/me/complete-profile debe actualizar foto de perfil inicial y derivar referencia privada', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/me/complete-profile')
        .set('Authorization', 'Bearer mock-valid-token')
        .send({
          profileImageKey: 'Fotos_Perfil/public/c09a8123/avatar-nuevo.jpg',
        })
        .expect(200);

      expect(response.body.profileComplete).toBe(true);
      expect(response.body.profileImageKey).toBe('Fotos_Perfil/public/c09a8123/avatar-nuevo.jpg');

      const user = await databaseService.findUserByCognitoSub('c09a8123-1122-3344-5566-778899aabbcc');
      expect(user?.face_reference_key).toBe('Fotos_Perfil/references/c09a8123/avatar-nuevo.jpg');
    });

    it('GET /api/v1/posts con perfil completado debe responder 200 OK', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/posts')
        .set('Authorization', 'Bearer mock-valid-token')
        .expect(200);

      expect(response.body).toHaveProperty('items');
    });

    it('PATCH /api/v1/me con contraseña correcta debe actualizar datos', async () => {
      const response = await request(app.getHttpServer())
        .patch('/api/v1/me')
        .set('Authorization', 'Bearer mock-valid-token')
        .send({
          fullName: 'Daniel Ortiz Modificado',
          currentPassword: 'PasswordSeguro2026!#',
        })
        .expect(200);

      expect(response.body.fullName).toBe('Daniel Ortiz Modificado');
    });

    it('PATCH /api/v1/me con contraseña incorrecta debe responder 400 VALIDATION_ERROR e INVALID_CURRENT_PASSWORD', async () => {
      const response = await request(app.getHttpServer())
        .patch('/api/v1/me')
        .set('Authorization', 'Bearer mock-valid-token')
        .send({
          fullName: 'Nombre No Guardado',
          currentPassword: 'PasswordEquivocado!',
        })
        .expect(400);

      expect(response.body.code).toBe('VALIDATION_ERROR');
      const reason = response.body.reason || response.body.details?.reason;
      expect(reason).toBe('INVALID_CURRENT_PASSWORD');
    });
  });

  describe('4. Módulos Sociales e Integraciones', () => {
    it('GET /api/v1/friend-requests debe responder 200 OK con array de solicitudes', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/friend-requests')
        .set('Authorization', 'Bearer mock-valid-token')
        .expect(200);

      expect(Array.isArray(response.body)).toBe(true);
    });

    describe('Amazon Translate (PRO-42)', () => {
      it('POST /api/v1/translations debe traducir texto al idioma destino válido (en)', async () => {
        const response = await request(app.getHttpServer())
          .post('/api/v1/translations')
          .set('Authorization', 'Bearer mock-valid-token')
          .send({
            text: 'Bienvenidos a Semi-Social',
            targetLanguage: 'en',
          })
          .expect(200);

        expect(response.body).toHaveProperty('translatedText');
        expect(response.body.targetLanguage).toBe('en');
        expect(response.body).toHaveProperty('sourceLanguage');
      });

      it('POST /api/v1/translate (alias) debe ser compatible con frontend', async () => {
        const response = await request(app.getHttpServer())
          .post('/api/v1/translate')
          .set('Authorization', 'Bearer mock-valid-token')
          .send({
            text: 'Texto de prueba',
            targetLanguage: 'fr',
          })
          .expect(200);

        expect(response.body.targetLanguage).toBe('fr');
      });

      it('POST /api/v1/translations debe rechazar idioma no soportado con 400', async () => {
        const response = await request(app.getHttpServer())
          .post('/api/v1/translations')
          .set('Authorization', 'Bearer mock-valid-token')
          .send({
            text: 'Texto de prueba',
            targetLanguage: 'it', // No es es, en, fr, de
          })
          .expect(400);

        expect(response.body.code).toBe('VALIDATION_ERROR');
      });

      it('POST /api/v1/translations debe requerir autenticación (401)', async () => {
        const response = await request(app.getHttpServer())
          .post('/api/v1/translations')
          .send({
            text: 'Texto de prueba',
            targetLanguage: 'en',
          })
          .expect(401);

        expect(response.body.code).toBe('UNAUTHENTICATED');
      });
    });

    describe('Amazon Lex V2 (PRO-42)', () => {
      it('POST /api/v1/bot/messages debe responder con mensajes en array y el mismo sessionId', async () => {
        const sessionId = '3f2504e0-4f89-41d3-9a0c-0305e82c3301';
        const response = await request(app.getHttpServer())
          .post('/api/v1/bot/messages')
          .set('Authorization', 'Bearer mock-valid-token')
          .send({
            text: '¿Cuáles son los horarios de atención?',
            sessionId,
          })
          .expect(200);

        expect(Array.isArray(response.body.messages)).toBe(true);
        expect(response.body.messages.length).toBeGreaterThan(0);
        expect(response.body.sessionId).toBe(sessionId);
      });

      it('POST /api/v1/bot/messages debe rechazar payload sin sessionId con 400', async () => {
        const response = await request(app.getHttpServer())
          .post('/api/v1/bot/messages')
          .set('Authorization', 'Bearer mock-valid-token')
          .send({
            text: 'Horarios de atención',
          })
          .expect(400);

        expect(response.body.code).toBe('VALIDATION_ERROR');
      });

      it('POST /api/v1/bot/messages debe requerir autenticación (401)', async () => {
        const response = await request(app.getHttpServer())
          .post('/api/v1/bot/messages')
          .send({
            text: 'Horarios de atención',
            sessionId: 'sesion-test-123',
          })
          .expect(401);

        expect(response.body.code).toBe('UNAUTHENTICATED');
      });

      it('Fórmula de derivación lexSessionId debe cumplir exactamente con los vectores de prueba de docs/api/bot.md', () => {
        const { deriveLexSessionId } = require('../src/modules/bot/bot.service');

        // Vector 1 de bot.md
        const vec1 = deriveLexSessionId(
          '11111111-1111-4111-8111-111111111111',
          '3f2504e0-4f89-41d3-9a0c-0305e82c3301',
        );
        expect(vec1).toBe('u08f6e4a73d54e8994d037782bb85e5e5052166f55040c985ea3db65ed7fe7f85');

        // Vector 2 de bot.md con caracteres UTF-8
        const vec2 = deriveLexSessionId('11111111-1111-4111-8111-111111111111', 'sesión ñ #1');
        expect(vec2).toBe('u56baf61d953cd5e2c81a586de0acea13fd5bb5229270e6d5574dd5fe168ed112');
      });
    });
  });

  describe('5. Relaciones Sociales y Solicitudes de Amistad (PRO-8)', () => {
    const userA = {
      id: '11111111-1111-4111-8111-111111111111',
      cognito_sub: 'sub-ana-1111',
      email: 'ana@example.com',
      full_name: 'Ana López',
      dpi: '1000000000001',
      profile_image_key: 'Fotos_Perfil/public/sub-ana-1111/avatar.jpg',
      face_reference_key: 'Fotos_Perfil/references/sub-ana-1111/ref.jpg',
      created_at: new Date('2026-10-18T10:00:00Z').toISOString(),
      updated_at: new Date('2026-10-18T10:00:00Z').toISOString(),
    };
    const userB = {
      id: '22222222-2222-4222-8222-222222222222',
      cognito_sub: 'sub-bruno-2222',
      email: 'bruno@example.com',
      full_name: 'Bruno Díaz',
      dpi: '2000000000002',
      profile_image_key: 'Fotos_Perfil/public/sub-bruno-2222/avatar.jpg',
      face_reference_key: 'Fotos_Perfil/references/sub-bruno-2222/ref.jpg',
      created_at: new Date('2026-10-18T10:05:00Z').toISOString(),
      updated_at: new Date('2026-10-18T10:05:00Z').toISOString(),
    };
    const userC = {
      id: '33333333-3333-4333-8333-333333333333',
      cognito_sub: 'sub-carla-3333',
      email: 'carla@example.com',
      full_name: 'Carla Ruiz',
      dpi: '3000000000003',
      profile_image_key: 'Fotos_Perfil/public/sub-carla-3333/avatar.jpg',
      face_reference_key: 'Fotos_Perfil/references/sub-carla-3333/ref.jpg',
      created_at: new Date('2026-10-18T10:10:00Z').toISOString(),
      updated_at: new Date('2026-10-18T10:10:00Z').toISOString(),
    };

    const tokenA = 'token-ana-111';
    const tokenB = 'token-bruno-222';
    const tokenC = 'token-carla-333';

    let requestABId: string;

    beforeAll(() => {
      databaseService.saveMockUser(userA);
      databaseService.saveMockUser(userB);
      databaseService.saveMockUser(userC);

      databaseService.saveMockSession(tokenA, { cognitoSub: userA.cognito_sub, email: userA.email });
      databaseService.saveMockSession(tokenB, { cognitoSub: userB.cognito_sub, email: userB.email });
      databaseService.saveMockSession(tokenC, { cognitoSub: userC.cognito_sub, email: userC.email });
    });

    it('GET /api/v1/users (Ana): lista usuarios no amigos excluyendo a ella misma', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/users')
        .set('Authorization', `Bearer ${tokenA}`)
        .expect(200);

      expect(response.body).toHaveProperty('items');
      expect(Array.isArray(response.body.items)).toBe(true);

      const userIds = response.body.items.map((i: any) => i.userId);
      expect(userIds).toContain(userB.id);
      expect(userIds).toContain(userC.id);
      expect(userIds).not.toContain(userA.id);
    });

    it('POST /api/v1/friend-requests: auto-solicitud debe fallar con 400 VALIDATION_ERROR', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/friend-requests')
        .set('Authorization', `Bearer ${tokenA}`)
        .send({ addresseeId: userA.id })
        .expect(400);

      expect(response.body.code).toBe('VALIDATION_ERROR');
    });

    it('POST /api/v1/friend-requests: usuario destino inexistente debe fallar con 404 NOT_FOUND', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/friend-requests')
        .set('Authorization', `Bearer ${tokenA}`)
        .send({ addresseeId: '99999999-9999-4999-8999-999999999999' })
        .expect(404);

      expect(response.body.code).toBe('NOT_FOUND');
    });

    it('POST /api/v1/friend-requests: Ana envía solicitud a Bruno (201 Created)', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/friend-requests')
        .set('Authorization', `Bearer ${tokenA}`)
        .send({ addresseeId: userB.id })
        .expect(201);

      expect(response.body).toHaveProperty('requestId');
      expect(response.body.requester.userId).toBe(userA.id);
      expect(response.body.addressee.userId).toBe(userB.id);
      expect(response.body.status).toBe('pending');

      requestABId = response.body.requestId;
    });

    it('POST /api/v1/friend-requests: solicitud duplicada debe fallar con 409 CONFLICT', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/friend-requests')
        .set('Authorization', `Bearer ${tokenA}`)
        .send({ addresseeId: userB.id })
        .expect(409);

      expect(response.body.code).toBe('CONFLICT');
    });

    it('POST /api/v1/friend-requests: solicitud cruzada concurrente (Bruno a Ana) debe fallar con 409 CONFLICT', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/friend-requests')
        .set('Authorization', `Bearer ${tokenB}`)
        .send({ addresseeId: userA.id })
        .expect(409);

      expect(response.body.code).toBe('CONFLICT');
    });

    it('GET /api/v1/friend-requests: Bruno ve la solicitud recibida de Ana como pending', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/friend-requests')
        .set('Authorization', `Bearer ${tokenB}`)
        .expect(200);

      expect(Array.isArray(response.body)).toBe(true);
      const found = response.body.find((r: any) => r.requestId === requestABId);
      expect(found).toBeDefined();
      expect(found.requester.userId).toBe(userA.id);
      expect(found.status).toBe('pending');
    });

    it('PATCH /api/v1/friend-requests/:id: tercero C no puede responder la solicitud de B (403 FORBIDDEN)', async () => {
      const response = await request(app.getHttpServer())
        .patch(`/api/v1/friend-requests/${requestABId}`)
        .set('Authorization', `Bearer ${tokenC}`)
        .send({ decision: 'accepted' })
        .expect(403);

      expect(response.body.code).toBe('FORBIDDEN');
    });

    it('PATCH /api/v1/friend-requests/:id: decisión inválida debe fallar con 400 VALIDATION_ERROR', async () => {
      const response = await request(app.getHttpServer())
        .patch(`/api/v1/friend-requests/${requestABId}`)
        .set('Authorization', `Bearer ${tokenB}`)
        .send({ decision: 'maybe' })
        .expect(400);

      expect(response.body.code).toBe('VALIDATION_ERROR');
    });

    it('PATCH /api/v1/friend-requests/:id: Bruno acepta solicitud de Ana (200 OK)', async () => {
      const response = await request(app.getHttpServer())
        .patch(`/api/v1/friend-requests/${requestABId}`)
        .set('Authorization', `Bearer ${tokenB}`)
        .send({ decision: 'accepted' })
        .expect(200);

      expect(response.body.requestId).toBe(requestABId);
      expect(response.body.status).toBe('accepted');
    });

    it('PATCH /api/v1/friend-requests/:id: responder una solicitud ya resuelta debe fallar con 400', async () => {
      const response = await request(app.getHttpServer())
        .patch(`/api/v1/friend-requests/${requestABId}`)
        .set('Authorization', `Bearer ${tokenB}`)
        .send({ decision: 'accepted' })
        .expect(400);

      expect(response.body.code).toBe('VALIDATION_ERROR');
    });

    it('GET /api/v1/friends: Ana y Bruno aparecen mutuamente en lista de amigos', async () => {
      const resA = await request(app.getHttpServer())
        .get('/api/v1/friends')
        .set('Authorization', `Bearer ${tokenA}`)
        .expect(200);

      expect(Array.isArray(resA.body)).toBe(true);
      expect(resA.body.some((f: any) => f.userId === userB.id)).toBe(true);

      const resB = await request(app.getHttpServer())
        .get('/api/v1/friends')
        .set('Authorization', `Bearer ${tokenB}`)
        .expect(200);

      expect(Array.isArray(resB.body)).toBe(true);
      expect(resB.body.some((f: any) => f.userId === userA.id)).toBe(true);

      const resC = await request(app.getHttpServer())
        .get('/api/v1/friends')
        .set('Authorization', `Bearer ${tokenC}`)
        .expect(200);

      expect(Array.isArray(resC.body)).toBe(true);
      expect(resC.body.length).toBe(0);
    });

    it('GET /api/v1/users: Ana ya no ve a Bruno como no-amigo (ambos son amigos)', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/users')
        .set('Authorization', `Bearer ${tokenA}`)
        .expect(200);

      const userIds = response.body.items.map((i: any) => i.userId);
      expect(userIds).not.toContain(userB.id);
      expect(userIds).toContain(userC.id);
    });

    it('Flujo de Rechazo: Ana envía solicitud a Carla y Carla la rechaza (no crea amistad)', async () => {
      const sendRes = await request(app.getHttpServer())
        .post('/api/v1/friend-requests')
        .set('Authorization', `Bearer ${tokenA}`)
        .send({ addresseeId: userC.id })
        .expect(201);

      const reqACId = sendRes.body.requestId;

      const rejectRes = await request(app.getHttpServer())
        .patch(`/api/v1/friend-requests/${reqACId}`)
        .set('Authorization', `Bearer ${tokenC}`)
        .send({ decision: 'rejected' })
        .expect(200);

      expect(rejectRes.body.status).toBe('rejected');

      // Comprobar que no son amigos
      const friendsC = await request(app.getHttpServer())
        .get('/api/v1/friends')
        .set('Authorization', `Bearer ${tokenC}`)
        .expect(200);

      expect(friendsC.body.some((f: any) => f.userId === userA.id)).toBe(false);
    });
  });

  describe('6. Ciclo de Contenido, Rekognition, Feed de Amigos y Comentarios (PRO-32)', () => {
    const userA = {
      id: '11111111-1111-4111-8111-111111111111',
      cognito_sub: 'sub-ana-1111',
      email: 'ana@example.com',
    };
    const userB = {
      id: '22222222-2222-4222-8222-222222222222',
      cognito_sub: 'sub-bruno-2222',
      email: 'bruno@example.com',
    };
    const userC = {
      id: '33333333-3333-4333-8333-333333333333',
      cognito_sub: 'sub-carla-3333',
      email: 'carla@example.com',
    };

    const tokenA = 'token-ana-111';
    const tokenB = 'token-bruno-222';
    const tokenC = 'token-carla-333';

    let postAnaId: string;
    let postBrunoId: string;
    let commentId: string;

    it('POST /api/v1/posts: Ana crea una publicación con imagen válida y descripción', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/posts')
        .set('Authorization', `Bearer ${tokenA}`)
        .send({
          imageKey: `Fotos_Publicadas/${userA.cognito_sub}/campus-ana.jpg`,
          description: 'Hermosa mañana en el campus de la facultad',
        })
        .expect(201);

      expect(response.body).toHaveProperty('id');
      expect(response.body.author.userId).toBe(userA.id);
      expect(response.body.imageKey).toBe(`Fotos_Publicadas/${userA.cognito_sub}/campus-ana.jpg`);
      expect(response.body.imageUrl).toContain('campus-ana.jpg');
      expect(response.body.description).toBe('Hermosa mañana en el campus de la facultad');
      expect(Array.isArray(response.body.labels)).toBe(true);
      expect(response.body.labels.some((l: any) => (typeof l === 'string' ? l : l.name) === 'campus')).toBe(true);

      postAnaId = response.body.id;
    });

    it('POST /api/v1/posts: Bruno crea una publicación con imagen de perro', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/posts')
        .set('Authorization', `Bearer ${tokenB}`)
        .send({
          imageKey: `Fotos_Publicadas/${userB.cognito_sub}/perro-bruno.jpg`,
          description: 'Paseando a mi mascota',
        })
        .expect(201);

      expect(response.body.author.userId).toBe(userB.id);
      expect(response.body.labels.some((l: any) => (typeof l === 'string' ? l : l.name) === 'perro')).toBe(true);
      postBrunoId = response.body.id;
    });

    it('POST /api/v1/posts: descripción vacía u omitida es válida', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/posts')
        .set('Authorization', `Bearer ${tokenA}`)
        .send({
          imageKey: `Fotos_Publicadas/${userA.cognito_sub}/foto-sin-texto.jpg`,
        })
        .expect(201);

      expect(response.body.description).toBeNull();
    });

    it('POST /api/v1/posts: imagen ausente debe fallar con 400 VALIDATION_ERROR', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/posts')
        .set('Authorization', `Bearer ${tokenA}`)
        .send({
          description: 'Publicación sin imagen',
        })
        .expect(400);

      expect(response.body.code).toBe('VALIDATION_ERROR');
    });

    it('POST /api/v1/posts: clave de imagen ajena debe fallar con 403 FORBIDDEN', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/posts')
        .set('Authorization', `Bearer ${tokenA}`)
        .send({
          imageKey: `Fotos_Publicadas/${userB.cognito_sub}/foto-ajena.jpg`,
          description: 'Intentando usar foto ajena',
        })
        .expect(403);

      expect(response.body.code).toBe('FORBIDDEN');
    });

    it('GET /api/v1/posts: Bruno (amigo) ve el post de Ana y su propio post en el feed', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/posts')
        .set('Authorization', `Bearer ${tokenB}`)
        .expect(200);

      const postIds = response.body.items.map((p: any) => p.id);
      expect(postIds).toContain(postAnaId);
      expect(postIds).toContain(postBrunoId);
    });

    it('GET /api/v1/posts: Carla (no amiga) NO ve los posts de Ana ni los de Bruno', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/posts')
        .set('Authorization', `Bearer ${tokenC}`)
        .expect(200);

      const postIds = response.body.items.map((p: any) => p.id);
      expect(postIds).not.toContain(postAnaId);
      expect(postIds).not.toContain(postBrunoId);
    });

    it('GET /api/v1/posts?label=perro: filtrar por etiqueta solo devuelve posts correspondientes', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/posts?label=perro')
        .set('Authorization', `Bearer ${tokenB}`)
        .expect(200);

      expect(response.body.items.length).toBeGreaterThan(0);
      for (const post of response.body.items) {
        expect(post.labels.some((l: any) => (typeof l === 'string' ? l : l.name) === 'perro')).toBe(true);
      }
    });

    it('GET /api/v1/posts?q=campus: búsqueda textual responde al contrato', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/posts?q=campus')
        .set('Authorization', `Bearer ${tokenB}`)
        .expect(200);

      expect(response.body.items.length).toBeGreaterThan(0);
      expect(response.body.items.some((p: any) => p.id === postAnaId)).toBe(true);
    });

    it('GET /api/v1/labels: catálogo de etiquetas devuelve "Todos" y etiquetas detectadas', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/labels')
        .set('Authorization', `Bearer ${tokenA}`)
        .expect(200);

      const labelsList = Array.isArray(response.body) ? response.body : response.body.items;
      expect(Array.isArray(labelsList)).toBe(true);
      expect(labelsList.some((l: any) => l.name === 'Todos')).toBe(true);
      expect(labelsList.some((l: any) => l.name === 'campus')).toBe(true);
    });

    it('POST /api/v1/posts/:id/comments: Bruno (amigo) comenta exitosamente en el post de Ana', async () => {
      const response = await request(app.getHttpServer())
        .post(`/api/v1/posts/${postAnaId}/comments`)
        .set('Authorization', `Bearer ${tokenB}`)
        .send({
          content: '¡Qué buena foto del campus Ana!',
        })
        .expect(201);

      expect(response.body).toHaveProperty('id');
      expect(response.body.postId).toBe(postAnaId);
      expect(response.body.author.userId).toBe(userB.id);
      expect(response.body.content).toBe('¡Qué buena foto del campus Ana!');
      commentId = response.body.id;
    });

    it('POST /api/v1/posts/:id/comments: Carla (no amiga) intenta comentar y falla con 403 FORBIDDEN', async () => {
      const response = await request(app.getHttpServer())
        .post(`/api/v1/posts/${postAnaId}/comments`)
        .set('Authorization', `Bearer ${tokenC}`)
        .send({
          content: 'Comentario no autorizado',
        })
        .expect(403);

      expect(response.body.code).toBe('FORBIDDEN');
    });

    it('POST /api/v1/posts/:id/comments: comentario vacío falla con 400 VALIDATION_ERROR', async () => {
      const response = await request(app.getHttpServer())
        .post(`/api/v1/posts/${postAnaId}/comments`)
        .set('Authorization', `Bearer ${tokenB}`)
        .send({
          content: '   ',
        })
        .expect(400);

      expect(response.body.code).toBe('VALIDATION_ERROR');
    });

    it('GET /api/v1/posts/:id/comments: Ana y Bruno ven los comentarios de la publicación', async () => {
      const response = await request(app.getHttpServer())
        .get(`/api/v1/posts/${postAnaId}/comments`)
        .set('Authorization', `Bearer ${tokenA}`)
        .expect(200);

      const commentsList = Array.isArray(response.body) ? response.body : response.body.comments;
      expect(Array.isArray(commentsList)).toBe(true);
      expect(commentsList.some((c: any) => c.id === commentId || c.commentId === commentId)).toBe(true);
    });

    it('GET /api/v1/posts/:id/comments: Carla (no amiga) no puede leer los comentarios (403 FORBIDDEN)', async () => {
      const response = await request(app.getHttpServer())
        .get(`/api/v1/posts/${postAnaId}/comments`)
        .set('Authorization', `Bearer ${tokenC}`)
        .expect(403);

      expect(response.body.code).toBe('FORBIDDEN');
    });

    it('GET /api/v1/posts/:id/comments: post inexistente responde 404 NOT_FOUND', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/posts/00000000-0000-4000-8000-000000000000/comments')
        .set('Authorization', `Bearer ${tokenA}`)
        .expect(404);

      expect(response.body.code).toBe('NOT_FOUND');
    });
  });
});

