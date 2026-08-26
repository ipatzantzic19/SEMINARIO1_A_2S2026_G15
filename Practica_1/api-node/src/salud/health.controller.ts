import { Controller, Get } from '@nestjs/common';

@Controller('health')
export class HealthController {
  @Get()
  checkHealth() {
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
