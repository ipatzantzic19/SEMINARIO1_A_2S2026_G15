import { Controller, Get, UseGuards } from '@nestjs/common';
import { PeliculasService } from './peliculas.service';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';

@Controller('peliculas')
@UseGuards(JwtAuthGuard)
export class PeliculasController {
  constructor(private readonly peliculasService: PeliculasService) {}

  @Get()
  async listarPeliculas() {
    const data = await this.peliculasService.listarPeliculas();
    return {
      exito: true,
      datos: data,
    };
  }
}
