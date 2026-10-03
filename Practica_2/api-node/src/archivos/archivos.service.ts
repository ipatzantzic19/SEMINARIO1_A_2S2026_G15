import { Injectable, HttpStatus } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { RegistrarArchivoDto } from './dto/registrar-archivo.dto';
import { CustomBusinessException } from '../common/filters/http-exception.filter';
import { CODIGOS_ERROR, MENSAJES_ERROR } from '../config/acuerdos.constants';
import { formatearFechaISO } from '../common/utils/fecha.util';

@Injectable()
export class ArchivosService {
  constructor(private readonly dbService: DatabaseService) {}

  private mapearArchivo(row: any) {
    return {
      id: parseInt(row.id, 10),
      usuarioId: parseInt(row.usuario_id, 10),
      nombreOriginal: row.nombre_original,
      tipoMime: row.tipo_mime,
      tamanoBytes: parseInt(row.tamano_bytes, 10),
      proveedorAlmacenamiento: row.proveedor_almacenamiento,
      claveObjeto: row.clave_objeto,
      urlObjeto: row.url_objeto,
      creadoEn: formatearFechaISO(row.creado_en),
    };
  }

  async listar(usuarioId: number) {
    const res = await this.dbService.query(
      `SELECT id, usuario_id, nombre_original, tipo_mime, tamano_bytes, proveedor_almacenamiento, clave_objeto, url_objeto, creado_en
       FROM archivos
       WHERE usuario_id = $1
       ORDER BY creado_en DESC`,
      [usuarioId],
    );

    const archivos = res.rows.map((row) => this.mapearArchivo(row));
    return {
      archivos,
      total: archivos.length,
    };
  }

  async registrar(usuarioId: number, dto: RegistrarArchivoDto) {
    const res = await this.dbService.query(
      `INSERT INTO archivos (usuario_id, nombre_original, tipo_mime, tamano_bytes, proveedor_almacenamiento, clave_objeto, url_objeto)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       RETURNING id, usuario_id, nombre_original, tipo_mime, tamano_bytes, proveedor_almacenamiento, clave_objeto, url_objeto, creado_en`,
      [
        usuarioId,
        dto.nombreOriginal,
        dto.tipoMime,
        dto.tamanoBytes,
        dto.proveedorAlmacenamiento,
        dto.claveObjeto,
        dto.urlObjeto,
      ],
    );

    return {
      archivo: this.mapearArchivo(res.rows[0]),
    };
  }

  async consultar(usuarioId: number, fileId: number) {
    const res = await this.dbService.query(
      `SELECT id, usuario_id, nombre_original, tipo_mime, tamano_bytes, proveedor_almacenamiento, clave_objeto, url_objeto, creado_en
       FROM archivos
       WHERE id = $1 AND usuario_id = $2`,
      [fileId, usuarioId],
    );

    if (res.rows.length === 0) {
      throw new CustomBusinessException(
        CODIGOS_ERROR.NO_ENCONTRADO,
        MENSAJES_ERROR.NO_ENCONTRADO,
        HttpStatus.NOT_FOUND,
      );
    }

    return {
      archivo: this.mapearArchivo(res.rows[0]),
    };
  }

  async eliminar(usuarioId: number, fileId: number) {
    // Verificar propiedad
    await this.consultar(usuarioId, fileId);

    await this.dbService.query(
      `DELETE FROM archivos WHERE id = $1 AND usuario_id = $2`,
      [fileId, usuarioId],
    );
  }
}
