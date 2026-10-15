import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe, BadRequestException } from '@nestjs/common';
const request = require('supertest');
import { AppModule } from '../src/app.module';

describe('Semi-Social Backend Node.js (E2E Tests)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();

    // Replicar configuración de main.ts para pruebas
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

  describe('2. Manejo de Errores y Validación (400 VALIDATION_ERROR)', () => {
    it('POST /api/v1/auth/register sin body debe fallar con 400 y esquema Error', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({})
        .expect(400);

      expect(response.body).toHaveProperty('code', 'VALIDATION_ERROR');
      expect(response.body).toHaveProperty('message');
      expect(response.body).toHaveProperty('requestId');
      expect(response.body).toHaveProperty('details');
      expect(Array.isArray(response.body.details)).toBe(true);
    });

    it('POST /api/v1/translate con idioma no soportado debe retornar 400 VALIDATION_ERROR', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/translate')
        .set('Authorization', 'Bearer mock-test-token')
        .send({
          text: 'Hola',
          targetLang: 'it', // Solo se permiten es, en, fr, de
        })
        .expect(400);

      expect(response.body.code).toBe('VALIDATION_ERROR');
    });
  });

  describe('3. Guardia de Autenticación JWT Cognito (401 UNAUTHENTICATED)', () => {
    it('GET /api/v1/me sin header Authorization debe responder 401 UNAUTHENTICATED', async () => {
      const response = await request(app.getHttpServer()).get('/api/v1/me').expect(401);

      expect(response.body).toHaveProperty('code', 'UNAUTHENTICATED');
      expect(response.body).toHaveProperty('message');
      expect(response.body).toHaveProperty('requestId');
    });

    it('GET /api/v1/me con Bearer Token válido debe retornar perfil del usuario', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/me')
        .set('Authorization', 'Bearer mock-valid-token')
        .expect(200);

      expect(response.body).toHaveProperty('userId');
      expect(response.body).toHaveProperty('email');
      expect(response.body).toHaveProperty('cognitoSub');
      expect(response.body).toHaveProperty('profileComplete');
    });
  });

  describe('4. Flujo de Autenticación (Contrato OpenAPI)', () => {
    it('POST /api/v1/auth/register con datos válidos debe registrar usuario', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({
          fullName: 'Daniel Abraham Ortiz',
          email: 'daniel.test@ingenieria.usac.edu.gt',
          dpi: '1234567890101',
          password: 'Password123!',
        })
        .expect(201);

      expect(response.body).toHaveProperty('userId');
      expect(response.body.email).toBe('daniel.test@ingenieria.usac.edu.gt');
      expect(response.body.confirmationRequired).toBe(true);
      expect(response.body.profileComplete).toBe(false);
    });

    it('POST /api/v1/auth/login con credenciales válidas debe retornar tokens', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/login')
        .send({
          email: 'daniel.test@ingenieria.usac.edu.gt',
          password: 'Password123!',
        })
        .expect(200);

      expect(response.body).toHaveProperty('accessToken');
      expect(response.body).toHaveProperty('idToken');
      expect(response.body).toHaveProperty('refreshToken');
      expect(response.body.tokenType).toBe('Bearer');
    });
  });

  describe('5. Feed y Publicaciones', () => {
    it('GET /api/v1/posts debe retornar lista de posts ordenados', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/posts')
        .set('Authorization', 'Bearer mock-token')
        .expect(200);

      expect(response.body).toHaveProperty('posts');
      expect(Array.isArray(response.body.posts)).toBe(true);
    });

    it('GET /api/v1/labels debe retornar lista de etiquetas para filtros', async () => {
      const response = await request(app.getHttpServer())
        .get('/api/v1/labels')
        .set('Authorization', 'Bearer mock-token')
        .expect(200);

      expect(response.body).toHaveProperty('labels');
      expect(response.body.labels[0]).toHaveProperty('name', 'Todos');
    });
  });
});
