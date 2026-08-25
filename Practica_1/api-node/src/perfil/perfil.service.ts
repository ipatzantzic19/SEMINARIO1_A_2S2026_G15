import {
  Injectable,
  Logger,
  NotFoundException,
  UnauthorizedException,
} from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { S3Service } from '../aws/s3.service';
import { ActualizarPerfilDto } from './dto/perfil.dto';
import * as crypto from 'crypto';

@Injectable()
export class PerfilService {
  private readonly logger = new Logger(PerfilService.name);

  constructor(
    private databaseService: DatabaseService,
    private s3Service: S3Service,
  ) { }

  private md5Hash(text: string): string {
    return crypto.createHash('md5').update(text).digest('hex');
  }

  async consultarPerfil(usuarioId: number) {
    let userRecord: any = null;

    if (this.databaseService.isReachable) {
      const res = await this.databaseService.query(
        'SELECT id, correo_electronico, nombre_completo, clave_foto_perfil FROM usuarios WHERE id = $1',
        [usuarioId],
      );
      if (res.rowCount && res.rowCount > 0) {
        userRecord = res.rows[0];
      }
    } else {
      userRecord = this.databaseService
        .getMockUsers()
        .find((u) => u.id === usuarioId);
    }

    if (!userRecord) {
      throw new NotFoundException('Usuario no encontrado.');
    }

    const urlFotoPerfil = this.s3Service.getPublicUrl(
      userRecord.clave_foto_perfil || userRecord.clave_foto_perfil,
    );

    return {
      id: usuarioId,
      correoElectronico: userRecord.correo_electronico || userRecord.correoElectronico,
      nombreCompleto: userRecord.nombre_completo || userRecord.nombreCompleto,
      urlFotoPerfil,
    };
  }

  async actualizarPerfil(
    usuarioId: number,
    dto: ActualizarPerfilDto,
    file?: Express.Multer.File,
  ) {
    const { contrasenaActual, nombreCompleto } = dto;
    const contrasenaMd5 = this.md5Hash(contrasenaActual);

    let userRecord: any = null;

    if (this.databaseService.isReachable) {
      const res = await this.databaseService.query(
        'SELECT id, correo_electronico, nombre_completo, contrasena_md5, clave_foto_perfil FROM usuarios WHERE id = $1',
        [usuarioId],
      );
      if (res.rowCount && res.rowCount > 0) {
        userRecord = res.rows[0];
      }
    } else {
      userRecord = this.databaseService
        .getMockUsers()
        .find((u) => u.id === usuarioId);
    }

    if (!userRecord) {
      throw new NotFoundException('Usuario no encontrado.');
    }

    // Validar contraseña
    if (userRecord.contrasena_md5 !== contrasenaMd5) {
      throw new UnauthorizedException('La contraseña actual es incorrecta.');
    }

    // Determinar valores finales
    let nuevoNombre = nombreCompleto || userRecord.nombre_completo || userRecord.nombreCompleto;
    let nuevaClaveFoto = userRecord.clave_foto_perfil;

    if (file) {
      try {
        nuevaClaveFoto = await this.s3Service.uploadImage(
          file.buffer,
          file.originalname,
          'Fotos_Perfil/',
          file.mimetype,
        );
      } catch (error) {
        this.logger.warn(
          `S3 Upload failed: ${error.message}. Falling back to default photo key for local dev.`,
        );
        nuevaClaveFoto = `Fotos_Perfil/dev-fallback-${Date.now()}.png`;
      }
    }

    if (this.databaseService.isReachable) {
      await this.databaseService.query(
        'UPDATE usuarios SET nombre_completo = $1, clave_foto_perfil = $2 WHERE id = $3',
        [nuevoNombre, nuevaClaveFoto, usuarioId],
      );
    } else {
      this.databaseService.updateMockUser(usuarioId, {
        nombre_completo: nuevoNombre,
        clave_foto_perfil: nuevaClaveFoto,
      });
    }

    const urlFotoPerfil = this.s3Service.getPublicUrl(nuevaClaveFoto);

    return {
      id: usuarioId,
      correoElectronico: userRecord.correo_electronico || userRecord.correoElectronico,
      nombreCompleto: nuevoNombre,
      urlFotoPerfil,
    };
  }
}
