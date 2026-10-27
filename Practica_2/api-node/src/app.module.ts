import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import configuration from './config/configuration';
import { DatabaseModule } from './database/database.module';
import { SaludModule } from './salud/salud.module';
import { AutenticacionModule } from './autenticacion/autenticacion.module';
import { TareasModule } from './tareas/tareas.module';
import { ArchivosModule } from './archivos/archivos.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [configuration],
    }),
    DatabaseModule,
    SaludModule,
    AutenticacionModule,
    TareasModule,
    ArchivosModule,
  ],
})
export class AppModule {}
