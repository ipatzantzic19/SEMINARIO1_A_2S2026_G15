import { NestFactory } from '@nestjs/core';
import { ValidationPipe, BadRequestException, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { AppModule } from './app.module';

async function bootstrap() {
  const logger = new Logger('Bootstrap');
  const app = await NestFactory.create(AppModule);

  const configService = app.get(ConfigService);
  const port = configService.get<number>('port') || 3000;
  const basePath = configService.get<string>('apiBasePath') || '/api/v1';

  // Habilitar CORS
  app.enableCors({
    origin: '*',
    methods: 'GET,HEAD,PUT,PATCH,POST,DELETE,OPTIONS',
    credentials: true,
  });

  // Prefijo global /api/v1 excluyendo /health (para que el ALB consulte en la raíz)
  const cleanPrefix = basePath.startsWith('/') ? basePath.substring(1) : basePath;
  app.setGlobalPrefix(cleanPrefix, {
    exclude: ['health'],
  });

  // Tubería global de validación DTO
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

  // Configuración de documentación interactiva Swagger
  const swaggerConfig = new DocumentBuilder()
    .setTitle('Semi-Social API (Node.js - NestJS)')
    .setDescription('Implementación del contrato común OpenAPI 3.0 para Semi-Social (Seminario de Sistemas 1 - Grupo 15)')
    .setVersion('1.0.0')
    .addBearerAuth()
    .build();

  const document = SwaggerModule.createDocument(app, swaggerConfig);
  SwaggerModule.setup('api/docs', app, document);

  await app.listen(port);
  logger.log(`================================================================`);
  logger.log(` Semi-Social Backend Node.js corriendo en puerto: ${port}`);
  logger.log(` Health check disponible en: http://localhost:${port}/health`);
  logger.log(` Documentación Swagger en: http://localhost:${port}/api/docs`);
  logger.log(` API base path: http://localhost:${port}${basePath}`);
  logger.log(`================================================================`);
}

bootstrap();
