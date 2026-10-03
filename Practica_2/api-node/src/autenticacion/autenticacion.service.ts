import { Injectable, HttpStatus } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as bcrypt from 'bcryptjs';
import * as jwt from 'jsonwebtoken';
import { DatabaseService } from '../database/database.service';
import { RegistroDto } from './dto/registro.dto';
import { LoginDto } from './dto/login.dto';
import { CustomBusinessException } from '../common/filters/http-exception.filter';
import {
  CODIGOS_ERROR,
  MENSAJES_ERROR,
  DETALLES_ERROR,
  BCRYPT_COSTO,
} from '../config/acuerdos.constants';

@Injectable()
export class AutenticacionService {
  constructor(
    private readonly dbService: DatabaseService,
    private readonly configService: ConfigService,
  ) {}

  async registrar(dto: RegistroDto) {
    const nombreUsuario = dto.nombreUsuario.trim().toLowerCase();
    const correoElectronico = dto.correoElectronico.trim().toLowerCase();
    const contrasena = dto.contrasena;
    const confirmacion = dto.confirmacionContrasena;
    const urlImagenPerfil = dto.urlImagenPerfil || null;

    if (contrasena !== confirmacion) {
      throw new CustomBusinessException(
        CODIGOS_ERROR.ERROR_VALIDACION,
        MENSAJES_ERROR.ERROR_VALIDACION,
        HttpStatus.BAD_REQUEST,
        [
          {
            campo: 'confirmacionContrasena',
            mensaje: DETALLES_ERROR.CONTRASENAS_NO_COINCIDEN,
          },
        ],
      );
    }

    // Verificar duplicados
    const resExistente = await this.dbService.query(
      `SELECT nombre_usuario, correo_electronico 
       FROM usuarios 
       WHERE nombre_usuario = $1 OR correo_electronico = $2`,
      [nombreUsuario, correoElectronico],
    );

    if (resExistente.rows.length > 0) {
      const existeNombre = resExistente.rows.some((r) => r.nombre_usuario === nombreUsuario);
      const existeCorreo = resExistente.rows.some((r) => r.correo_electronico === correoElectronico);

      const detalles: Array<{ campo: string; mensaje: string }> = [];
      if (existeNombre) {
        detalles.push({ campo: 'nombreUsuario', mensaje: DETALLES_ERROR.NOMBRE_USUARIO_EXISTE });
      }
      if (existeCorreo) {
        detalles.push({ campo: 'correoElectronico', mensaje: DETALLES_ERROR.CORREO_EXISTE });
      }

      throw new CustomBusinessException(
        CODIGOS_ERROR.CONFLICTO,
        MENSAJES_ERROR.CONFLICTO_USUARIO,
        HttpStatus.CONFLICT,
        detalles,
      );
    }

    // Hash de la contraseña
    const contrasenaHash = await bcrypt.hash(contrasena, BCRYPT_COSTO);

    // Insertar en BD
    const resInsert = await this.dbService.query(
      `INSERT INTO usuarios (nombre_usuario, correo_electronico, contrasena_hash, url_imagen_perfil)
       VALUES ($1, $2, $3, $4)
       RETURNING id, nombre_usuario, correo_electronico, url_imagen_perfil`,
      [nombreUsuario, correoElectronico, contrasenaHash, urlImagenPerfil],
    );

    const row = resInsert.rows[0];
    return {
      usuario: {
        id: parseInt(row.id, 10),
        nombreUsuario: row.nombre_usuario,
        correoElectronico: row.correo_electronico,
        urlImagenPerfil: row.url_imagen_perfil,
      },
    };
  }

  async iniciarSesion(dto: LoginDto) {
    const nombreUsuario = dto.nombreUsuario.trim().toLowerCase();
    const contrasena = dto.contrasena;

    const resUser = await this.dbService.query(
      `SELECT id, nombre_usuario, correo_electronico, contrasena_hash, url_imagen_perfil
       FROM usuarios
       WHERE nombre_usuario = $1`,
      [nombreUsuario],
    );

    if (resUser.rows.length === 0) {
      throw new CustomBusinessException(
        CODIGOS_ERROR.ERROR_AUTENTICACION,
        MENSAJES_ERROR.CREDENCIALES_INVALIDAS,
        HttpStatus.UNAUTHORIZED,
      );
    }

    const userRow = resUser.rows[0];
    const passwordMatch = await bcrypt.compare(contrasena, userRow.contrasena_hash);

    if (!passwordMatch) {
      throw new CustomBusinessException(
        CODIGOS_ERROR.ERROR_AUTENTICACION,
        MENSAJES_ERROR.CREDENCIALES_INVALIDAS,
        HttpStatus.UNAUTHORIZED,
      );
    }

    const userId = parseInt(userRow.id, 10);
    const jwtSecret = this.configService.get<string>('jwt.secret') || 'secret-key-change-me';
    const expiresIn = this.configService.get<number>('jwt.expiresIn') || 3600;

    const payload = {
      sub: String(userId),
      nombreUsuario: userRow.nombre_usuario,
    };

    const token = jwt.sign(payload, jwtSecret, {
      algorithm: 'HS256',
      expiresIn: expiresIn,
    });

    return {
      token,
      tipoToken: 'Bearer',
      expiraEn: expiresIn,
      usuario: {
        id: userId,
        nombreUsuario: userRow.nombre_usuario,
        correoElectronico: userRow.correo_electronico,
        urlImagenPerfil: userRow.url_imagen_perfil,
      },
    };
  }
}
