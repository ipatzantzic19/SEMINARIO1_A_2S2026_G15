import {
  Controller,
  Get,
  Post,
  Put,
  Patch,
  Delete,
  Body,
  Param,
  UseGuards,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { JwtAuthGuard, UsuarioAutenticado } from '../common/guards/jwt-auth.guard';
import { UsuarioActual } from '../common/decorators/usuario-actual.decorator';
import { TareasService } from './tareas.service';
import { CrearTareaDto } from './dto/crear-tarea.dto';
import { ActualizarTareaDto } from './dto/actualizar-tarea.dto';
import { CambiarEstadoTareaDto } from './dto/cambiar-estado-tarea.dto';
import { CustomBusinessException } from '../common/filters/http-exception.filter';
import { CODIGOS_ERROR, MENSAJES_ERROR, DETALLES_ERROR } from '../config/acuerdos.constants';

@Controller('api/v1/tasks')
@UseGuards(JwtAuthGuard)
export class TareasController {
  constructor(private readonly tareasService: TareasService) {}

  private validarTaskId(param: string): number {
    if (!/^[1-9][0-9]*$/.test(param)) {
      throw new CustomBusinessException(
        CODIGOS_ERROR.ERROR_VALIDACION,
        MENSAJES_ERROR.ERROR_VALIDACION,
        HttpStatus.BAD_REQUEST,
        [{ campo: 'taskId', mensaje: DETALLES_ERROR.ID_NO_ENTERO }],
      );
    }
    const id = parseInt(param, 10);
    if (isNaN(id) || id <= 0) {
      throw new CustomBusinessException(
        CODIGOS_ERROR.ERROR_VALIDACION,
        MENSAJES_ERROR.ERROR_VALIDACION,
        HttpStatus.BAD_REQUEST,
        [{ campo: 'taskId', mensaje: DETALLES_ERROR.ID_NO_ENTERO }],
      );
    }
    return id;
  }

  @Get()
  async listar(@UsuarioActual() usuario: UsuarioAutenticado) {
    const datos = await this.tareasService.listar(usuario.id);
    return {
      exito: true,
      datos,
    };
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  async crear(
    @UsuarioActual() usuario: UsuarioAutenticado,
    @Body() dto: CrearTareaDto,
  ) {
    const datos = await this.tareasService.crear(usuario.id, dto);
    return {
      exito: true,
      datos,
    };
  }

  @Get(':taskId')
  async consultar(
    @UsuarioActual() usuario: UsuarioAutenticado,
    @Param('taskId') taskIdParam: string,
  ) {
    const taskId = this.validarTaskId(taskIdParam);
    const datos = await this.tareasService.consultar(usuario.id, taskId);
    return {
      exito: true,
      datos,
    };
  }

  @Put(':taskId')
  async actualizar(
    @UsuarioActual() usuario: UsuarioAutenticado,
    @Param('taskId') taskIdParam: string,
    @Body() dto: ActualizarTareaDto,
  ) {
    const taskId = this.validarTaskId(taskIdParam);
    const datos = await this.tareasService.actualizar(usuario.id, taskId, dto);
    return {
      exito: true,
      datos,
    };
  }

  @Patch(':taskId')
  async cambiarEstado(
    @UsuarioActual() usuario: UsuarioAutenticado,
    @Param('taskId') taskIdParam: string,
    @Body() dto: CambiarEstadoTareaDto,
  ) {
    const taskId = this.validarTaskId(taskIdParam);
    const datos = await this.tareasService.cambiarEstado(usuario.id, taskId, dto);
    return {
      exito: true,
      datos,
    };
  }

  @Delete(':taskId')
  @HttpCode(HttpStatus.NO_CONTENT)
  async eliminar(
    @UsuarioActual() usuario: UsuarioAutenticado,
    @Param('taskId') taskIdParam: string,
  ) {
    const taskId = this.validarTaskId(taskIdParam);
    await this.tareasService.eliminar(usuario.id, taskId);
  }
}
