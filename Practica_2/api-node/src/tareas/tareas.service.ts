import { Injectable, HttpStatus } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { CrearTareaDto } from './dto/crear-tarea.dto';
import { ActualizarTareaDto } from './dto/actualizar-tarea.dto';
import { CambiarEstadoTareaDto } from './dto/cambiar-estado-tarea.dto';
import { CustomBusinessException } from '../common/filters/http-exception.filter';
import { CODIGOS_ERROR, MENSAJES_ERROR } from '../config/acuerdos.constants';
import { formatearFechaISO } from '../common/utils/fecha.util';

@Injectable()
export class TareasService {
  constructor(private readonly dbService: DatabaseService) {}

  private mapearTarea(row: any) {
    return {
      id: parseInt(row.id, 10),
      usuarioId: parseInt(row.usuario_id, 10),
      titulo: row.titulo,
      descripcion: row.descripcion || '',
      fechaCreacion: formatearFechaISO(row.fecha_creacion),
      completada: row.completada,
      fechaCompletada: formatearFechaISO(row.fecha_completada),
      actualizadoEn: formatearFechaISO(row.actualizado_en),
    };
  }

  async listar(usuarioId: number) {
    const res = await this.dbService.query(
      `SELECT id, usuario_id, titulo, descripcion, fecha_creacion, completada, fecha_completada, actualizado_en
       FROM tareas
       WHERE usuario_id = $1
       ORDER BY fecha_creacion DESC`,
      [usuarioId],
    );

    const tareas = res.rows.map((row) => this.mapearTarea(row));
    return {
      tareas,
      total: tareas.length,
    };
  }

  async crear(usuarioId: number, dto: CrearTareaDto) {
    const titulo = dto.titulo;
    const descripcion = dto.descripcion !== undefined ? dto.descripcion : '';
    const fechaCreacion = dto.fechaCreacion || null;

    let res;
    if (fechaCreacion) {
      res = await this.dbService.query(
        `INSERT INTO tareas (usuario_id, titulo, descripcion, fecha_creacion)
         VALUES ($1, $2, $3, $4)
         RETURNING id, usuario_id, titulo, descripcion, fecha_creacion, completada, fecha_completada, actualizado_en`,
        [usuarioId, titulo, descripcion, fechaCreacion],
      );
    } else {
      res = await this.dbService.query(
        `INSERT INTO tareas (usuario_id, titulo, descripcion)
         VALUES ($1, $2, $3)
         RETURNING id, usuario_id, titulo, descripcion, fecha_creacion, completada, fecha_completada, actualizado_en`,
        [usuarioId, titulo, descripcion],
      );
    }

    return {
      tarea: this.mapearTarea(res.rows[0]),
    };
  }

  async consultar(usuarioId: number, taskId: number) {
    const res = await this.dbService.query(
      `SELECT id, usuario_id, titulo, descripcion, fecha_creacion, completada, fecha_completada, actualizado_en
       FROM tareas
       WHERE id = $1 AND usuario_id = $2`,
      [taskId, usuarioId],
    );

    if (res.rows.length === 0) {
      throw new CustomBusinessException(
        CODIGOS_ERROR.NO_ENCONTRADO,
        MENSAJES_ERROR.NO_ENCONTRADO,
        HttpStatus.NOT_FOUND,
      );
    }

    return {
      tarea: this.mapearTarea(res.rows[0]),
    };
  }

  async actualizar(usuarioId: number, taskId: number, dto: ActualizarTareaDto) {
    // Verificar existencia y propiedad
    await this.consultar(usuarioId, taskId);

    const titulo = dto.titulo;
    const descripcion = dto.descripcion !== undefined ? dto.descripcion : '';

    const res = await this.dbService.query(
      `UPDATE tareas
       SET titulo = $1, descripcion = $2
       WHERE id = $3 AND usuario_id = $4
       RETURNING id, usuario_id, titulo, descripcion, fecha_creacion, completada, fecha_completada, actualizado_en`,
      [titulo, descripcion, taskId, usuarioId],
    );

    return {
      tarea: this.mapearTarea(res.rows[0]),
    };
  }

  async cambiarEstado(usuarioId: number, taskId: number, dto: CambiarEstadoTareaDto) {
    const { tarea: actual } = await this.consultar(usuarioId, taskId);

    let res;
    if (dto.completada) {
      if (actual.completada) {
        // Idempotente: conserva la fechaCompletada original
        res = await this.dbService.query(
          `SELECT id, usuario_id, titulo, descripcion, fecha_creacion, completada, fecha_completada, actualizado_en
           FROM tareas WHERE id = $1 AND usuario_id = $2`,
          [taskId, usuarioId],
        );
      } else {
        // Marcar como completada
        res = await this.dbService.query(
          `UPDATE tareas
           SET completada = TRUE, fecha_completada = CURRENT_TIMESTAMP
           WHERE id = $1 AND usuario_id = $2
           RETURNING id, usuario_id, titulo, descripcion, fecha_creacion, completada, fecha_completada, actualizado_en`,
          [taskId, usuarioId],
        );
      }
    } else {
      // Marcar como pendiente
      res = await this.dbService.query(
        `UPDATE tareas
         SET completada = FALSE, fecha_completada = NULL
         WHERE id = $1 AND usuario_id = $2
         RETURNING id, usuario_id, titulo, descripcion, fecha_creacion, completada, fecha_completada, actualizado_en`,
        [taskId, usuarioId],
      );
    }

    return {
      tarea: this.mapearTarea(res.rows[0]),
    };
  }

  async eliminar(usuarioId: number, taskId: number) {
    // Verificar existencia y propiedad
    await this.consultar(usuarioId, taskId);

    await this.dbService.query(
      `DELETE FROM tareas WHERE id = $1 AND usuario_id = $2`,
      [taskId, usuarioId],
    );
  }
}
