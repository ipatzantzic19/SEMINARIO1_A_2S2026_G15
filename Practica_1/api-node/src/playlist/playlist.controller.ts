import {
  Controller,
  Delete,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Req,
  UseGuards,
} from '@nestjs/common';
import { PlaylistService } from './playlist.service';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';

@Controller('lista-reproduccion')
@UseGuards(JwtAuthGuard)
export class PlaylistController {
  constructor(private readonly playlistService: PlaylistService) {}

  @Get()
  async consultarLista(@Req() req: any) {
    const usuarioId = req.user.sub;
    const data = await this.playlistService.consultarLista(usuarioId);

    return {
      exito: true,
      datos: data,
    };
  }

  @Post(':peliculaId')
  async agregarPelicula(
    @Req() req: any,
    @Param('peliculaId', ParseIntPipe) peliculaId: number,
  ) {
    const usuarioId = req.user.sub;
    const pelicula = await this.playlistService.agregarPeliculaALista(
      usuarioId,
      peliculaId,
    );

    return {
      exito: true,
      datos: {
        pelicula,
      },
    };
  }

  @Delete(':peliculaId')
  async eliminarPelicula(
    @Req() req: any,
    @Param('peliculaId', ParseIntPipe) peliculaId: number,
  ) {
    const usuarioId = req.user.sub;
    const data = await this.playlistService.eliminarPeliculaDeLista(
      usuarioId,
      peliculaId,
    );

    return {
      exito: true,
      datos: data,
    };
  }
}
