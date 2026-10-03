import { Controller, Post, Body, HttpCode, HttpStatus } from '@nestjs/common';
import { AutenticacionService } from './autenticacion.service';
import { RegistroDto } from './dto/registro.dto';
import { LoginDto } from './dto/login.dto';

@Controller('api/v1/auth')
export class AutenticacionController {
  constructor(private readonly authService: AutenticacionService) {}

  @Post('register')
  @HttpCode(HttpStatus.CREATED)
  async registrar(@Body() dto: RegistroDto) {
    const datos = await this.authService.registrar(dto);
    return {
      exito: true,
      datos,
    };
  }

  @Post('login')
  @HttpCode(HttpStatus.OK)
  async iniciarSesion(@Body() dto: LoginDto) {
    const datos = await this.authService.iniciarSesion(dto);
    return {
      exito: true,
      datos,
    };
  }
}
