import { Controller, Get } from '@nestjs/common';

@Controller('salud')
export class SaludController {
  @Get()
  consultarSalud() {
    return {
      exito: true,
      datos: {
        estado: 'ok',
        servicio: 'cloudcinema-api',
        implementacion: 'node',
      },
    };
  }
}
