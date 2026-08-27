import {
  BadRequestException,
  ConflictException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { S3Service } from '../aws/s3.service';

@Injectable()
export class PlaylistService {
  private readonly logger = new Logger(PlaylistService.name);

  constructor(
    private databaseService: DatabaseService,
    private s3Service: S3Service,
  ) { }

  async consultarLista(usuarioId: number) {
    let rawList: any[] = [];

    if (this.databaseService.isReachable) {
      const res = await this.databaseService.query(
        `SELECT p.id, p.titulo, p.director, p.anio_estreno, p.url_contenido, p.estado, p.clave_portada, lr.agregado_en
         FROM lista_reproduccion lr
         INNER JOIN peliculas p ON lr.pelicula_id = p.id
         WHERE lr.usuario_id = $1
         ORDER BY lr.agregado_en DESC`,
        [usuarioId],
      );
      rawList = res.rows;
    } else {
      const playlist = this.databaseService.getMockPlaylist();
      const movies = this.databaseService.getMockMovies();

      // Filtra los elementos de la lista por usuario y cruza con las películas
      const userItems = playlist.filter((item) => item.usuarioId === usuarioId);
      rawList = userItems
        .map((item) => {
          const movie = movies.find((m) => m.id === item.peliculaId);
          if (!movie) return null;
          return {
            ...movie,
            agregado_en: item.agregadoEn,
          };
        })
        .filter((m) => m !== null);

      // Ordena por agregado_en descendente
      rawList.sort((a, b) => b.agregado_en.getTime() - a.agregado_en.getTime());
    }

    const peliculas = rawList.map((item) => {
      const id = parseInt(item.id, 10) || item.id;
      const anioEstreno = parseInt(item.anio_estreno, 10) || item.anio_estreno;
      const urlPortada = this.s3Service.getPublicUrl(item.clave_portada);
      const agregadoEn = new Date(item.agregado_en).toISOString();

      return {
        id,
        titulo: item.titulo,
        director: item.director,
        anioEstreno,
        urlContenido: item.url_contenido,
        estado: item.estado,
        urlPortada,
        agregadoEn,
      };
    });

    return {
      peliculas,
      total: peliculas.length,
    };
  }

  async agregarPeliculaALista(usuarioId: number, peliculaId: number) {
    let movieRecord: any = null;

    // Verifica que la película exista
    if (this.databaseService.isReachable) {
      const res = await this.databaseService.query(
        'SELECT id, titulo, director, anio_estreno, url_contenido, estado, clave_portada FROM peliculas WHERE id = $1',
        [peliculaId],
      );
      if (res.rowCount && res.rowCount > 0) {
        movieRecord = res.rows[0];
      }
    } else {
      movieRecord = this.databaseService
        .getMockMovies()
        .find((m) => m.id === peliculaId);
    }

    if (!movieRecord) {
      throw new NotFoundException('Película no encontrada.');
    }

    // Verifica que el estado sea DISPONIBLE (rechaza PROXIMO_ESTRENO)
    if (movieRecord.estado !== 'DISPONIBLE') {
      throw new BadRequestException(
        'No se puede agregar a la lista una película que no esté disponible.',
      );
    }

    // Verifica duplicados
    let alreadyExists = false;
    if (this.databaseService.isReachable) {
      const checkRes = await this.databaseService.query(
        'SELECT 1 FROM lista_reproduccion WHERE usuario_id = $1 AND pelicula_id = $2',
        [usuarioId, peliculaId],
      );
      alreadyExists = checkRes.rowCount !== null && checkRes.rowCount > 0;
    } else {
      alreadyExists = this.databaseService
        .getMockPlaylist()
        .some((item) => item.usuarioId === usuarioId && item.peliculaId === peliculaId);
    }

    if (alreadyExists) {
      throw new ConflictException(
        'La película ya se encuentra en tu lista de reproducción.',
      );
    }

    // Inserta la conexión
    let agregadoEnDate = new Date();

    if (this.databaseService.isReachable) {
      const insertRes = await this.databaseService.query(
        `INSERT INTO lista_reproduccion (usuario_id, pelicula_id)
         VALUES ($1, $2)
         RETURNING agregado_en`,
        [usuarioId, peliculaId],
      );
      agregadoEnDate = new Date(insertRes.rows[0].agregado_en);
    } else {
      this.databaseService.addMockPlaylistItem({
        usuarioId,
        peliculaId,
        agregadoEn: agregadoEnDate,
      });
    }

    const id = parseInt(movieRecord.id, 10) || movieRecord.id;
    const anioEstreno = parseInt(movieRecord.anio_estreno, 10) || movieRecord.anio_estreno;
    const urlPortada = this.s3Service.getPublicUrl(movieRecord.clave_portada);

    return {
      id,
      titulo: movieRecord.titulo,
      director: movieRecord.director,
      anioEstreno,
      urlContenido: movieRecord.url_contenido,
      estado: movieRecord.estado,
      urlPortada,
      agregadoEn: agregadoEnDate.toISOString(),
    };
  }

  async eliminarPeliculaDeLista(usuarioId: number, peliculaId: number) {
    let exists = false;

    if (this.databaseService.isReachable) {
      const res = await this.databaseService.query(
        'SELECT 1 FROM lista_reproduccion WHERE usuario_id = $1 AND pelicula_id = $2',
        [usuarioId, peliculaId],
      );
      exists = res.rowCount !== null && res.rowCount > 0;
    } else {
      exists = this.databaseService
        .getMockPlaylist()
        .some((item) => item.usuarioId === usuarioId && item.peliculaId === peliculaId);
    }

    if (!exists) {
      throw new NotFoundException(
        'La película no se encuentra en tu lista de reproducción.',
      );
    }

    if (this.databaseService.isReachable) {
      await this.databaseService.query(
        'DELETE FROM lista_reproduccion WHERE usuario_id = $1 AND pelicula_id = $2',
        [usuarioId, peliculaId],
      );
    } else {
      this.databaseService.deleteMockPlaylistItem(usuarioId, peliculaId);
    }

    return {
      peliculaId,
      eliminado: true,
    };
  }
}
