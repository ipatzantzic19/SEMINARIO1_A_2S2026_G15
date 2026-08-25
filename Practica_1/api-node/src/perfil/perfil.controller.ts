import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Put,
  Req,
  UploadedFile,
  UnsupportedMediaTypeException,
  UseGuards,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { PerfilService } from './perfil.service';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { ActualizarPerfilDto } from './dto/perfil.dto';

@Controller('perfil')
@UseGuards(JwtAuthGuard)
export class PerfilController {
  constructor(private readonly perfilService: PerfilService) { }

  @Get()
  async consultarPerfil(@Req() req: any) {
    const usuarioId = req.user.sub;
    const usuario = await this.perfilService.consultarPerfil(usuarioId);

    return {
      exito: true,
      datos: {
        usuario,
      },
    };
  }

  @Put()
  @HttpCode(HttpStatus.OK)
  @UseInterceptors(FileInterceptor('fotoPerfil'))
  async actualizarPerfil(
    @Req() req: any,
    @Body() dto: ActualizarPerfilDto,
    @UploadedFile() file?: Express.Multer.File,
  ) {
    const usuarioId = req.user.sub;

    // Validar el tipo de contenido del archivo si se ha subido  
    if (file) {
      const allowedMimeTypes = ['image/jpeg', 'image/png', 'image/webp'];
      if (!allowedMimeTypes.includes(file.mimetype)) {
        throw new UnsupportedMediaTypeException(
          'El formato de la foto de perfil debe ser image/jpeg, image/png o image/webp.',
        );
      }
    }

    const usuario = await this.perfilService.actualizarPerfil(
      usuarioId,
      dto,
      file,
    );

    return {
      exito: true,
      datos: {
        usuario,
      },
    };
  }
}
