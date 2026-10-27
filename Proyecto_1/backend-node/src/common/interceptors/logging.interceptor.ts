import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
  Logger,
} from '@nestjs/common';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';

@Injectable()
export class LoggingInterceptor implements NestInterceptor {
  private readonly logger = new Logger('HTTP');

  intercept(context: ExecutionContext, next: CallHandler): Observable<any> {
    const request = context.switchToHttp().getRequest();
    const { method, originalUrl } = request;
    const requestId = request.requestId || 'no-request-id';
    const now = Date.now();

    // Sanitización de datos sensibles para evitar fugas en logs
    const sanitizedBody = this.sanitize(request.body);

    this.logger.log(
      `[REQ] [${requestId}] ${method} ${originalUrl} - Payload: ${JSON.stringify(
        sanitizedBody,
      )}`,
    );

    return next.handle().pipe(
      tap(() => {
        const response = context.switchToHttp().getResponse();
        const statusCode = response.statusCode;
        const duration = Date.now() - now;
        this.logger.log(
          `[RES] [${requestId}] ${method} ${originalUrl} ${statusCode} - ${duration}ms`,
        );
      }),
    );
  }

  private sanitize(data: any): any {
    if (!data || typeof data !== 'object') return data;
    const sensitiveKeys = [
      'password',
      'repeatPassword',
      'currentPassword',
      'newPassword',
      'token',
      'accessToken',
      'idToken',
      'refreshToken',
      'secret',
      'base64',
      'faceCapture',
      'faceReference',
    ];

    if (Array.isArray(data)) {
      return data.map((item) => this.sanitize(item));
    }

    const copy = { ...data };
    for (const key of Object.keys(copy)) {
      if (sensitiveKeys.some((s) => key.toLowerCase().includes(s.toLowerCase()))) {
        copy[key] = '[REDACTED]';
      } else if (typeof copy[key] === 'object') {
        copy[key] = this.sanitize(copy[key]);
      }
    }
    return copy;
  }
}
