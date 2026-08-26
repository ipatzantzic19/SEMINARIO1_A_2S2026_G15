import { Injectable } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { S3Service } from '../aws/s3.service';

@Injectable()
export class PeliculasService {
  constructor(
    private databaseService: DatabaseService,
    private s3Service: S3Service,
  ) {}

  async listarPeliculas() {
    let rawMovies: any[] = [];

    if (this.databaseService.isReachable) {
      const res = await this.databaseService.query(
        'SELECT id, titulo, director, anio_estreno, url_contenido, estado, clave_portada FROM peliculas ORDER BY id ASC',
      );
      rawMovies = res.rows;
    } else {
      rawMovies = this.databaseService.getMockMovies();
    }

    const peliculas = rawMovies.map((movie) => {
      const id = parseInt(movie.id, 10) || movie.id;
      const anioEstreno = parseInt(movie.anio_estreno, 10) || movie.anio_estreno;
      const urlPortada = this.s3Service.getPublicUrl(movie.clave_portada);

      return {
        id,
        titulo: movie.titulo,
        director: movie.director,
        anioEstreno,
        urlContenido: movie.url_contenido,
        estado: movie.estado,
        urlPortada,
      };
    });

    return {
      peliculas,
      total: peliculas.length,
    };
  }
}
