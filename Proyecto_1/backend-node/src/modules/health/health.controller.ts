import { Controller, Get, HttpStatus, ServiceUnavailableException } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { Public } from '../../common/decorators/public.decorator';
import { DatabaseService } from '../../database/database.service';
import { ConfigService } from '@nestjs/config';

export interface HealthResponse {
  status: 'ok';
  service: 'node';
  version: string;
}

@ApiTags('Salud')
@Controller('health')
export class HealthController {
  constructor(
    private databaseService: DatabaseService,
    private configService: ConfigService,
  ) {}

  @Public()
  @Get()
  @ApiOperation({ summary: 'Verifica la salud del backend Node.js (usado por el ALB)' })
  @ApiResponse({
    status: 200,
    description: 'Backend saludable y operativo',
    schema: {
      example: { status: 'ok', service: 'node', version: '1.0.0' },
    },
  })
  @ApiResponse({
    status: 503,
    description: 'Dependencia crítica no disponible',
  })
  async checkHealth(): Promise<HealthResponse> {
    const isDbAlive = await this.databaseService.ping();
    const mockMode = this.configService.get<boolean>('mockMode');

    if (!isDbAlive && !mockMode) {
      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'La base de datos relacional no responde.',
      });
    }

    return {
      status: 'ok',
      service: 'node',
      version: '1.0.0',
    };
  }
}
