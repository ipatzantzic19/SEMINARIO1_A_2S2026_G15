import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { Response } from 'express';
import { CODIGOS_ERROR, MENSAJES_ERROR } from '../../config/acuerdos.constants';

export class CustomBusinessException extends HttpException {
  constructor(
    public readonly codigo: string,
    mensaje: string,
    status: HttpStatus,
    public readonly detalles?: Array<{ campo?: string; mensaje: string }>,
  ) {
    super(mensaje, status);
  }
}

@Catch()
export class GlobalHttpExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(GlobalHttpExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();

    let status = HttpStatus.INTERNAL_SERVER_ERROR;
    let codigo: string = CODIGOS_ERROR.ERROR_INTERNO;
    let mensaje: string = MENSAJES_ERROR.ERROR_INTERNO;
    let detalles: Array<{ campo?: string; mensaje: string }> | undefined = undefined;

    if (exception instanceof CustomBusinessException) {
      status = exception.getStatus();
      codigo = exception.codigo;
      mensaje = exception.message;
      detalles = exception.detalles;
    } else if (exception instanceof HttpException) {
      status = exception.getStatus();
      const res: any = exception.getResponse();

      if (status === HttpStatus.BAD_REQUEST) {
        codigo = CODIGOS_ERROR.ERROR_VALIDACION;
        mensaje = MENSAJES_ERROR.ERROR_VALIDACION;
        if (typeof res === 'object' && res !== null && Array.isArray(res.message)) {
          detalles = res.message.map((msg: string) => ({
            mensaje: msg,
          }));
        } else if (typeof res === 'object' && res !== null && res.message) {
          detalles = [{ mensaje: res.message }];
        }
      } else if (status === HttpStatus.UNAUTHORIZED) {
        codigo = CODIGOS_ERROR.ERROR_AUTENTICACION;
        mensaje = res.message || MENSAJES_ERROR.ERROR_AUTENTICACION;
      } else if (status === HttpStatus.NOT_FOUND) {
        codigo = CODIGOS_ERROR.NO_ENCONTRADO;
        mensaje = res.message || MENSAJES_ERROR.NO_ENCONTRADO;
      } else if (status === HttpStatus.CONFLICT) {
        codigo = CODIGOS_ERROR.CONFLICTO;
        mensaje = res.message || MENSAJES_ERROR.CONFLICTO_USUARIO;
      } else if (status === HttpStatus.SERVICE_UNAVAILABLE) {
        codigo = CODIGOS_ERROR.BD_NO_DISPONIBLE;
        mensaje = res.message || MENSAJES_ERROR.BD_NO_DISPONIBLE;
      } else {
        mensaje = typeof res === 'string' ? res : res.message || mensaje;
      }
    } else {
      this.logger.error('Excepción no controlada:', exception);
    }

    const payloadError: any = {
      codigo,
      mensaje,
    };

    if (detalles && detalles.length > 0) {
      payloadError.detalles = detalles;
    }

    response.status(status).json({
      exito: false,
      error: payloadError,
    });
  }
}
