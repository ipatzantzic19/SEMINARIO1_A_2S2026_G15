import { Controller, Get, HttpStatus } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { CustomBusinessException } from '../common/filters/http-exception.filter';
import {
  CODIGOS_ERROR,
  MENSAJES_ERROR,
  SERVICIO,
  IMPLEMENTACION,
} from '../config/acuerdos.constants';

@Controller('health')
export class SaludController {
  constructor(private readonly dbService: DatabaseService) {}

  @Get()
  async consultarSalud() {
    const estaDisponible = await this.dbService.verificarConexion(2000);
    if (!estaDisponible) {
      throw new CustomBusinessException(
        CODIGOS_ERROR.BD_NO_DISPONIBLE,
        MENSAJES_ERROR.BD_NO_DISPONIBLE,
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }

    return {
      exito: true,
      datos: {
        estado: 'ok',
        servicio: SERVICIO,
        implementacion: IMPLEMENTACION,
      },
    };
  }
}
