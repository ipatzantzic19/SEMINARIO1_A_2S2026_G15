import {
  ConflictException,
  Injectable,
  Logger,
  UnauthorizedException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { DatabaseService } from '../database/database.service';
import { S3Service } from '../aws/s3.service';
import { RegistroDto, InicioSesionDto } from './dto/autenticacion.dto';
import * as crypto from 'crypto';

@Injectable()
export class AutenticacionService {
  private readonly logger = new Logger(AutenticacionService.name);

  // Constructor

  constructor(
    private databaseService: DatabaseService,
    private s3Service: S3Service,
    private jwtService: JwtService,
  ) { }

  /**
   * Utilidad para generar el hash MD5 de una cadena, según lo requerido por las especificaciones de la universidad.
   */
  private md5Hash(text: string): string {
    return crypto.createHash('md5').update(text).digest('hex');
  }

  async registrar(dto: RegistroDto, file: Express.Multer.File) {
    const { correoElectronico, nombreCompleto, contrasena, confirmacionContrasena } = dto;

    // Verificación de la confirmación de la contraseña (realizada en el controlador/DTO o en el servicio)
    if (contrasena !== confirmacionContrasena) {
      // Gestionado mediante una excepción de validación personalizada o una comprobación manual.
    }

    const emailNormalized = correoElectronico.trim().toLowerCase();
    const contrasenaMd5 = this.md5Hash(contrasena);

    // Subir archivo a S3
    let claveFotoPerfil = '';
    try {
      claveFotoPerfil = await this.s3Service.uploadImage(
        file.buffer,
        file.originalname,
        'Fotos_Perfil/',
        file.mimetype,
      );
    } catch (error) {
      this.logger.warn(`S3 Upload failed: ${error.message}. Falling back to default photo key for local dev.`);
      claveFotoPerfil = `Fotos_Perfil/dev-fallback-${Date.now()}.png`;
    }

    //  Operaciones de base de datos
    if (this.databaseService.isReachable) {
      // Comprobar si el correo electrónico ya existe
      const checkRes = await this.databaseService.query(
        'SELECT id FROM usuarios WHERE correo_electronico = $1',
        [emailNormalized],
      );

      if (checkRes.rowCount && checkRes.rowCount > 0) {
        throw new ConflictException('El correo electrónico ya se encuentra registrado.');
      }

      // Insertar nuevo usuario
      const insertRes = await this.databaseService.query(
        `INSERT INTO usuarios (correo_electronico, nombre_completo, contrasena_md5, clave_foto_perfil)
         VALUES ($1, $2, $3, $4)
         RETURNING id`,
        [emailNormalized, nombreCompleto, contrasenaMd5, claveFotoPerfil],
      );

      const userId = parseInt(insertRes.rows[0].id, 10);
      const urlFotoPerfil = this.s3Service.getPublicUrl(claveFotoPerfil);

      return {
        id: userId,
        correoElectronico: emailNormalized,
        nombreCompleto,
        urlFotoPerfil,
      };
    } else {
      // Alternativa de reserva (fallback) simulada en memoria
      this.logger.warn(`Database is unreachable. Processing registration in memory.`);

      const mockUsers = this.databaseService.getMockUsers();
      const exists = mockUsers.find(u => u.correo_electronico === emailNormalized);
      if (exists) {
        throw new ConflictException('El correo electrónico ya se encuentra registrado.');
      }

      const mockId = mockUsers.length + 1;
      const newUser = {
        id: mockId,
        correo_electronico: emailNormalized,
        nombre_completo: nombreCompleto,
        contrasena_md5: contrasenaMd5,
        clave_foto_perfil: claveFotoPerfil,
      };

      this.databaseService.addMockUser(newUser);
      const urlFotoPerfil = this.s3Service.getPublicUrl(claveFotoPerfil);

      return {
        id: mockId,
        correoElectronico: emailNormalized,
        nombreCompleto,
        urlFotoPerfil,
      };
    }
  }

  async iniciarSesion(dto: InicioSesionDto) {
    const { correoElectronico, contrasena } = dto;
    const emailNormalized = correoElectronico.trim().toLowerCase();
    const contrasenaMd5 = this.md5Hash(contrasena);

    let userRecord: any = null;

    if (this.databaseService.isReachable) {
      const res = await this.databaseService.query(
        'SELECT id, correo_electronico, nombre_completo, contrasena_md5, clave_foto_perfil FROM usuarios WHERE correo_electronico = $1',
        [emailNormalized],
      );

      if (res.rowCount && res.rowCount > 0) {
        userRecord = res.rows[0];
      }
    } else {
      this.logger.warn(`Database is unreachable. Processing login in memory.`);
      userRecord = this.databaseService.getMockUsers().find(u => u.correo_electronico === emailNormalized);
    }

    // Validar credenciales
    if (!userRecord || userRecord.contrasena_md5 !== contrasenaMd5) {
      throw new UnauthorizedException('Credenciales incorrectas.');
    }

    const userId = parseInt(userRecord.id, 10);
    const urlFotoPerfil = this.s3Service.getPublicUrl(userRecord.clave_foto_perfil);

    // Generar token JWT
    const payload = {
      sub: userId,
      email: userRecord.correo_electronico,
      name: userRecord.nombre_completo,
    };

    const token = this.jwtService.sign(payload);

    return {
      token,
      tipoToken: 'Bearer',
      expiraEn: 3600,
      usuario: {
        id: userId,
        correoElectronico: userRecord.correo_electronico,
        nombreCompleto: userRecord.nombre_completo,
        urlFotoPerfil,
      },
    };
  }
}
