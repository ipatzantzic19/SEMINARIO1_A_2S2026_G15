import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe, BadRequestException } from '@nestjs/common';
const request = require('supertest');
import { AppModule } from '../src/app.module';

describe('Semi-Social Backend Node.js (E2E Tests - PRO-7 Cognito & Contract)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    // Configurar para ejecución de tests
    process.env.MOCK_MODE = 'true';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();

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

    it('POST /api/v1/me/complete-profile debe actualizar foto de perfil inicial', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/me/complete-profile')
        .set('Authorization', 'Bearer mock-valid-token')
        .send({
          profileImageKey: 'Fotos_Perfil/public/c09a8123/avatar-nuevo.jpg',
        })
        .expect(200);

      expect(response.body.profileComplete).toBe(true);
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
  });

  describe('4. Módulos Sociales e Integraciones', () => {
    it('GET /api/v1/friend-requests debe responder 200 OK', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/friend-requests')
        .set('Authorization', 'Bearer mock-valid-token')
        .expect(200);

      expect(response.body).toHaveProperty('incoming');
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
});
