import {
  BadRequestException,
  Body,
  Controller,
  HttpCode,
  HttpStatus,
  Post,
  UploadedFile,
  UnsupportedMediaTypeException,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { AutenticacionService } from './autenticacion.service';
import { RegistroDto, InicioSesionDto } from './dto/autenticacion.dto';

@Controller('autenticacion')
export class AutenticacionController {
  constructor(private readonly autenticacionService: AutenticacionService) { }

  @Post('registro')
  @UseInterceptors(FileInterceptor('fotoPerfil'))
  async registrar(
    @Body() dto: RegistroDto,
    @UploadedFile() file: Express.Multer.File,
  ) {
    // Validar la confirmación de la contraseña
    if (dto.contrasena !== dto.confirmacionContrasena) {
      throw new BadRequestException(
        'confirmacionContrasena debe coincidir con contrasena',
      );
    }

    // Validar la presencia del archivo
    if (!file) {
      throw new BadRequestException('El archivo fotoPerfil es obligatorio.');
    }

    //  Validar el tipo de contenido del archivo
    const allowedMimeTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowedMimeTypes.includes(file.mimetype)) {
      throw new UnsupportedMediaTypeException(
        'El formato de la foto de perfil debe ser image/jpeg, image/png o image/webp.',
      );
    }

    // Procesar el registro
    const usuario = await this.autenticacionService.registrar(dto, file);

    return {
      exito: true,
      datos: {
        usuario,
      },
    };
  }

  @Post('inicio-sesion')
  @HttpCode(HttpStatus.OK)
  async iniciarSesion(@Body() dto: InicioSesionDto) {
    const datos = await this.autenticacionService.iniciarSesion(dto);

    return {
      exito: true,
      datos,
    };
  }
}
