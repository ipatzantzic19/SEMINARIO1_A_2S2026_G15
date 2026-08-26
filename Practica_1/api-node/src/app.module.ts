import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import configuration from './config/configuration';
import { DatabaseModule } from './database/database.module';
import { AwsModule } from './aws/aws.module';
import { SaludModule } from './salud/salud.module';
import { AutenticacionModule } from './autenticacion/autenticacion.module';
import { PerfilModule } from './perfil/perfil.module';
import { PeliculasModule } from './peliculas/peliculas.module';
import { PlaylistModule } from './playlist/playlist.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [configuration],
    }),
    DatabaseModule,
    AwsModule,
    SaludModule,
    AutenticacionModule,
    PerfilModule,
    PeliculasModule,
    PlaylistModule,
  ],
})
export class AppModule {}
