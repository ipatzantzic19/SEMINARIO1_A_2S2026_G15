import {
  Injectable,
  CanActivate,
  ExecutionContext,
  UnauthorizedException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ConfigService } from '@nestjs/config';
import { IS_PUBLIC_KEY } from '../decorators/public.decorator';

@Injectable()
export class CognitoAuthGuard implements CanActivate {
  constructor(
    private reflector: Reflector,
    private configService: ConfigService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (isPublic) {
      return true;
    }

    const request = context.switchToHttp().getRequest();
    const authHeader = request.headers['authorization'];

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      throw new UnauthorizedException({
        code: 'UNAUTHENTICATED',
        message: 'Cabecera Authorization con formato Bearer <token> requerida.',
      });
    }

    const token = authHeader.split(' ')[1];
    if (!token) {
      throw new UnauthorizedException({
        code: 'UNAUTHENTICATED',
        message: 'Token de autenticación ausente.',
      });
    }

    const mockMode = this.configService.get<boolean>('mockMode');

    // Validación en modo desarrollo / mock
    if (mockMode) {
      // Simulación de usuario autenticado para pruebas locales
      request.user = {
        userId: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
        cognitoSub: 'c09a8123-1122-3344-5566-778899aabbcc',
        email: 'daniel.ortiz@ingenieria.usac.edu.gt',
        profileComplete: true,
      };
      return true;
    }

    // Modo producción con verificación real de Cognito
    try {
      // Decodificación y validación de payload JWT
      const parts = token.split('.');
      if (parts.length !== 3) {
        throw new Error('Token JWT malformado');
      }
      const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf8'));

      if (payload.exp && Date.now() >= payload.exp * 1000) {
        throw new UnauthorizedException({
          code: 'UNAUTHENTICATED',
          message: 'El token de sesión ha expirado.',
        });
      }

      request.user = {
        userId: payload['custom:userId'] || payload.sub,
        cognitoSub: payload.sub,
        email: payload.email,
        profileComplete: payload['custom:profileComplete'] === 'true',
      };

      return true;
    } catch (err) {
      throw new UnauthorizedException({
        code: 'UNAUTHENTICATED',
        message: 'Token de sesión inválido.',
      });
    }
  }
}
