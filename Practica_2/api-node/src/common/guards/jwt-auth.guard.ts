import {
  CanActivate,
  ExecutionContext,
  Injectable,
  HttpStatus,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as jwt from 'jsonwebtoken';
import { CODIGOS_ERROR, MENSAJES_ERROR } from '../../config/acuerdos.constants';
import { CustomBusinessException } from '../filters/http-exception.filter';

export interface UsuarioAutenticado {
  id: number;
  nombreUsuario: string;
}

@Injectable()
export class JwtAuthGuard implements CanActivate {
  constructor(private configService: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest();
    const authHeader = request.headers.authorization;

    if (!authHeader || typeof authHeader !== 'string') {
      throw new CustomBusinessException(
        CODIGOS_ERROR.ERROR_AUTENTICACION,
        MENSAJES_ERROR.ERROR_AUTENTICACION,
        HttpStatus.UNAUTHORIZED,
      );
    }

    const partes = authHeader.split(' ');
    if (partes.length !== 2 || partes[0] !== 'Bearer') {
      throw new CustomBusinessException(
        CODIGOS_ERROR.ERROR_AUTENTICACION,
        MENSAJES_ERROR.ERROR_AUTENTICACION,
        HttpStatus.UNAUTHORIZED,
      );
    }

    const token = partes[1];
    const jwtSecret = this.configService.get<string>('jwt.secret') || 'secret-key-change-me';

    try {
      const decoded: any = jwt.verify(token, jwtSecret, { algorithms: ['HS256'] });

      if (!decoded || !decoded.sub) {
        throw new CustomBusinessException(
          CODIGOS_ERROR.ERROR_AUTENTICACION,
          MENSAJES_ERROR.ERROR_AUTENTICACION,
          HttpStatus.UNAUTHORIZED,
        );
      }

      const userId = parseInt(String(decoded.sub), 10);
      if (isNaN(userId) || userId <= 0) {
        throw new CustomBusinessException(
          CODIGOS_ERROR.ERROR_AUTENTICACION,
          MENSAJES_ERROR.ERROR_AUTENTICACION,
          HttpStatus.UNAUTHORIZED,
        );
      }

      request.user = {
        id: userId,
        nombreUsuario: decoded.nombreUsuario || '',
      } as UsuarioAutenticado;

      return true;
    } catch (err) {
      if (err instanceof CustomBusinessException) {
        throw err;
      }
      throw new CustomBusinessException(
        CODIGOS_ERROR.ERROR_AUTENTICACION,
        MENSAJES_ERROR.ERROR_AUTENTICACION,
        HttpStatus.UNAUTHORIZED,
      );
    }
  }
}
