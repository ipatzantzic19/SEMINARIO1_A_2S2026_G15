import { Module } from '@nestjs/common';
import { SaludController } from './salud.controller';
import { HealthController } from './health.controller';

@Module({
  controllers: [SaludController, HealthController],
})
export class SaludModule {}

