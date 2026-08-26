import { Module } from '@nestjs/common';
import { PeliculasController } from './peliculas.controller';
import { PeliculasService } from './peliculas.service';
import { AutenticacionModule } from '../autenticacion/autenticacion.module';

@Module({
  imports: [AutenticacionModule],
  controllers: [PeliculasController],
  providers: [PeliculasService],
  exports: [PeliculasService],
})
export class PeliculasModule {}
