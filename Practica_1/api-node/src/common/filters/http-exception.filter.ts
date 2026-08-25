import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { Response } from 'express';

@Catch()
export class HttpExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(HttpExceptionFilter.name);

  catch(exception: any, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();

    let status = HttpStatus.INTERNAL_SERVER_ERROR;
    let codigo = 'ERROR_INTERNO';
    let mensaje = 'Error inesperado en el servidor.';
    let detalles: any[] | undefined = undefined;

    if (exception instanceof HttpException) {
      status = exception.getStatus();
      const resBody: any = exception.getResponse();

      // Comprueba si es un error de validación (de class-validator / ValidationPipe).
      if (status === HttpStatus.BAD_REQUEST && resBody && typeof resBody === 'object') {
        codigo = 'ERROR_VALIDACION';
        mensaje = 'Los datos enviados no son válidos.';

        // class-validator coloca los mensajes de validación en el campo 'message'.
        if (Array.isArray(resBody.message)) {
          detalles = resBody.message.map((msg: string) => {
            // Por lo general, los mensajes de validación tienen el formato: "el campo debe ser ..." o similar.
            // Intentemos extraer el nombre del campo si es posible.
            // Por ejemplo, class-validator proporciona: "correoElectronico debe ser una cadena"
            // Podemos buscar la primera palabra o manejarla con gracia.
            const firstSpaceIndex = msg.indexOf(' ');
            const campo = firstSpaceIndex !== -1 ? msg.substring(0, firstSpaceIndex) : undefined;
            return {
              campo,
              mensaje: msg,
            };
          });
        } else if (typeof resBody.message === 'string') {
          detalles = [
            {
              mensaje: resBody.message,
            },
          ];
        }
      } else {
        // Gestionar otros estados HTTP basándose en esquemas OpenAPI.
        switch (status) {
          case HttpStatus.UNAUTHORIZED:
            codigo = 'ERROR_AUTENTICACION';
            mensaje = resBody.message || 'Credenciales o token inválidos.';
            break;
          case HttpStatus.NOT_FOUND:
            codigo = 'NO_ENCONTRADO';
            mensaje = resBody.message || 'Recurso no encontrado.';
            break;
          case HttpStatus.CONFLICT:
            codigo = 'CONFLICTO';
            mensaje = resBody.message || 'Conflicto con el estado actual.';
            break;
          case HttpStatus.UNSUPPORTED_MEDIA_TYPE:
            codigo = 'TIPO_CONTENIDO_NO_SOPORTADO';
            mensaje = resBody.message || 'Tipo de imagen no permitido.';
            break;
          default:
            codigo = 'ERROR_SOLICITUD';
            mensaje = resBody.message || 'Error al procesar la solicitud.';
        }
      }
    } else {
      // Es una excepción no relacionada con HTTP (por ejemplo, un error de conexión a la base de datos o un error de sintaxis).
      this.logger.error(`Unhandled exception: ${exception.message || exception}`, exception.stack);
    }

    response.status(status).json({
      exito: false,
      error: {
        codigo,
        mensaje,
        ...(detalles ? { detalles } : {}),
      },
    });
  }
}
