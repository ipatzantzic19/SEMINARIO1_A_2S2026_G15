import {
  Controller,
  Get,
  Post,
  Delete,
  Body,
  Param,
  UseGuards,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { JwtAuthGuard, UsuarioAutenticado } from '../common/guards/jwt-auth.guard';
import { UsuarioActual } from '../common/decorators/usuario-actual.decorator';
import { ArchivosService } from './archivos.service';
import { RegistrarArchivoDto } from './dto/registrar-archivo.dto';
import { CustomBusinessException } from '../common/filters/http-exception.filter';
import { CODIGOS_ERROR, MENSAJES_ERROR, DETALLES_ERROR } from '../config/acuerdos.constants';

@Controller('api/v1/files')
@UseGuards(JwtAuthGuard)
export class ArchivosController {
  constructor(private readonly archivosService: ArchivosService) {}

  private validarFileId(param: string): number {
    if (!/^[1-9][0-9]*$/.test(param)) {
      throw new CustomBusinessException(
        CODIGOS_ERROR.ERROR_VALIDACION,
        MENSAJES_ERROR.ERROR_VALIDACION,
        HttpStatus.BAD_REQUEST,
        [{ campo: 'fileId', mensaje: DETALLES_ERROR.ID_NO_ENTERO }],
      );
    }
    const id = parseInt(param, 10);
    if (isNaN(id) || id <= 0) {
      throw new CustomBusinessException(
        CODIGOS_ERROR.ERROR_VALIDACION,
        MENSAJES_ERROR.ERROR_VALIDACION,
        HttpStatus.BAD_REQUEST,
        [{ campo: 'fileId', mensaje: DETALLES_ERROR.ID_NO_ENTERO }],
      );
    }
    return id;
  }

  @Get()
  async listar(@UsuarioActual() usuario: UsuarioAutenticado) {
    const datos = await this.archivosService.listar(usuario.id);
    return {
      exito: true,
      datos,
    };
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  async registrar(
    @UsuarioActual() usuario: UsuarioAutenticado,
    @Body() dto: RegistrarArchivoDto,
  ) {
    const datos = await this.archivosService.registrar(usuario.id, dto);
    return {
      exito: true,
      datos,
    };
  }

  @Get(':fileId')
  async consultar(
    @UsuarioActual() usuario: UsuarioAutenticado,
    @Param('fileId') fileIdParam: string,
  ) {
    const fileId = this.validarFileId(fileIdParam);
    const datos = await this.archivosService.consultar(usuario.id, fileId);
    return {
      exito: true,
      datos,
    };
  }

  @Delete(':fileId')
  @HttpCode(HttpStatus.NO_CONTENT)
  async eliminar(
    @UsuarioActual() usuario: UsuarioAutenticado,
    @Param('fileId') fileIdParam: string,
  ) {
    const fileId = this.validarFileId(fileIdParam);
    await this.archivosService.eliminar(usuario.id, fileId);
  }
}
