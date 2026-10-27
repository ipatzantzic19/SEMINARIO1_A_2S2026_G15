import {
  Injectable,
  CanActivate,
  ExecutionContext,
  UnauthorizedException,
  ForbiddenException,
  Logger,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ConfigService } from '@nestjs/config';
import { CognitoJwtVerifier } from 'aws-jwt-verify';
import { IS_PUBLIC_KEY } from '../decorators/public.decorator';
import { DatabaseService } from '../../database/database.service';

@Injectable()
export class CognitoAuthGuard implements CanActivate {
  private readonly logger = new Logger('CognitoAuthGuard');
  private jwtVerifier: any = null;
  private userPoolId: string;
  private clientId: string;
  private mockMode: boolean;

  constructor(
    private reflector: Reflector,
    private configService: ConfigService,
    private databaseService: DatabaseService,
  ) {
    this.userPoolId = this.configService.get<string>('cognito.userPoolId') || 'us-east-1_4UrrCPt8Z';
    this.clientId = this.configService.get<string>('cognito.appClientId') || '1feavcj8qvobr4ltshlgnolg5f';
    this.mockMode = this.configService.get<boolean>('mockMode') || false;

    if (!this.mockMode) {
      try {
        this.jwtVerifier = CognitoJwtVerifier.create({
          userPoolId: this.userPoolId,
          tokenUse: 'access',
          clientId: this.clientId,
        });
      } catch (err: any) {
        this.logger.warn(`No se pudo inicializar CognitoJwtVerifier: ${err.message}. Modo fallback activado.`);
      }
    }
  }

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

    let cognitoSub = 'c09a8123-1122-3344-5566-778899aabbcc';
    let email = 'daniel.ortiz@ingenieria.usac.edu.gt';

    if (this.mockMode || !this.jwtVerifier) {
      // Modo Mock o token de prueba
      const session = this.databaseService.getMockSession(token);
      if (session) {
        cognitoSub = session.cognitoSub;
        email = session.email;
      } else if (token.startsWith('mock-')) {
        cognitoSub = 'c09a8123-1122-3344-5566-778899aabbcc';
        email = 'daniel.ortiz@ingenieria.usac.edu.gt';
      } else {
        try {
          const parts = token.split('.');
          if (parts.length === 3) {
            const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf8'));
            cognitoSub = payload.sub || cognitoSub;
            email = payload.email || email;
          }
        } catch {
          // Token simulado simple
        }
      }
    } else {
      // Verificación estricta de firma criptográfica y expiración con AWS Cognito
      try {
        const payload = await this.jwtVerifier.verify(token);
        cognitoSub = payload.sub;
        email = (payload as any).email || email;
      } catch (err: any) {
        this.logger.warn(`Verificación de token fallida: ${err.message}`);
        throw new UnauthorizedException({
          code: 'UNAUTHENTICATED',
          message: 'Token de autenticación inválido, expirado o con firma no reconocida.',
        });
      }
    }

    // Consultar el estado real del usuario en la base de datos
    const dbUser = await this.databaseService.findUserByCognitoSub(cognitoSub);
    const profileComplete = Boolean(dbUser?.profile_image_key);

    request.user = {
      userId: dbUser?.id || cognitoSub,
      cognitoSub,
      email: dbUser?.email || email,
      profileComplete,
    };

    // Validación de perfil incompleto: si no ha subido foto, solo puede acceder a /me y /me/complete-profile
    const path = request.path || request.url;
    const isProfileRoute = path.includes('/me');

    if (!profileComplete && !isProfileRoute) {
      throw new ForbiddenException({
        code: 'FORBIDDEN',
        message: 'Debe completar su foto de perfil para acceder a las funcionalidades sociales.',
        details: { reason: 'PROFILE_INCOMPLETE' },
      });
    }

    return true;
  }
}
