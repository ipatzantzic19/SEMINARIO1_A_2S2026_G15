import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { Request, Response } from 'express';
import { v4 as uuidv4 } from 'uuid';
import { ErrorResponseDto } from '../dto/error-response.dto';

@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger('AllExceptionsFilter');

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request & { requestId?: string }>();

    const requestId = request.requestId || (request.headers['x-request-id'] as string) || uuidv4();

    let status = HttpStatus.INTERNAL_SERVER_ERROR;
    let code = 'INTERNAL_SERVER_ERROR';
    let message = 'Error interno del servidor.';
    let details: any = null;

    if (exception instanceof HttpException) {
      status = exception.getStatus();
      const res = exception.getResponse();

      if (typeof res === 'string') {
        message = res;
      } else if (typeof res === 'object' && res !== null) {
        const anyRes = res as any;
        message = anyRes.message || exception.message;
        code = anyRes.code || this.defaultCodeForStatus(status);
        details = anyRes.details || (Array.isArray(anyRes.message) ? anyRes.message : null);

        // Si validation pipe devolvió un array en 'message', ajustamos
        if (Array.isArray(anyRes.message)) {
          message = 'Error de validación en la solicitud.';
          code = 'VALIDATION_ERROR';
        }
      }
    } else if (exception instanceof Error) {
      this.logger.error(`[${requestId}] Error no manejado: ${exception.message}`, exception.stack);
      message = process.env.NODE_ENV === 'production' ? 'Error interno del servidor.' : exception.message;
    }

    // Mapear código por status si aún es genérico
    if (code === 'INTERNAL_SERVER_ERROR' && status !== HttpStatus.INTERNAL_SERVER_ERROR) {
      code = this.defaultCodeForStatus(status);
    }

    const errorBody: ErrorResponseDto = {
      code,
      message: Array.isArray(message) ? message.join('; ') : message,
      requestId,
      details: details || null,
    };

    response.status(status).json(errorBody);
  }

  private defaultCodeForStatus(status: number): string {
    switch (status) {
      case HttpStatus.BAD_REQUEST:
        return 'VALIDATION_ERROR';
      case HttpStatus.UNAUTHORIZED:
        return 'UNAUTHENTICATED';
      case HttpStatus.FORBIDDEN:
        return 'FORBIDDEN';
      case HttpStatus.NOT_FOUND:
        return 'NOT_FOUND';
      case HttpStatus.CONFLICT:
        return 'CONFLICT';
      case HttpStatus.PAYLOAD_TOO_LARGE:
        return 'FILE_TOO_LARGE';
      case HttpStatus.UNSUPPORTED_MEDIA_TYPE:
        return 'UNSUPPORTED_MEDIA_TYPE';
      case HttpStatus.UNPROCESSABLE_ENTITY:
        return 'FACE_NOT_MATCHED';
      case HttpStatus.TOO_MANY_REQUESTS:
        return 'RATE_LIMITED';
      case HttpStatus.SERVICE_UNAVAILABLE:
        return 'SERVICE_UNAVAILABLE';
      default:
        return 'INTERNAL_SERVER_ERROR';
    }
  }
}
