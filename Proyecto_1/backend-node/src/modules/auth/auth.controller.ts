import { Controller, Post, Body, HttpCode, HttpStatus } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { AuthService } from './auth.service';
import { Public } from '../../common/decorators/public.decorator';
import { RegisterRequestDto, ConfirmRequestDto, LoginRequestDto, FaceLoginInitDto, FaceLoginVerifyDto } from './dto/auth.dto';

@ApiTags('Autenticación')
@Controller('auth')
export class AuthController {
  constructor(private authService: AuthService) {}

  @Public()
  @Post('register')
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: 'Registrar un nuevo usuario en Semi-Social' })
  @ApiResponse({ status: 201, description: 'Usuario registrado pendiente de confirmación' })
  async register(@Body() dto: RegisterRequestDto) {
    return this.authService.register(dto);
  }

  @Public()
  @Post('confirm')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Confirmar registro mediante código de verificación enviado por correo' })
  @ApiResponse({ status: 200, description: 'Cuenta confirmada exitosamente' })
  async confirm(@Body() dto: ConfirmRequestDto) {
    return this.authService.confirm(dto);
  }

  @Public()
  @Post('login')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Iniciar sesión con correo y contraseña' })
  @ApiResponse({ status: 200, description: 'Autenticación exitosa y emisión de tokens Cognito' })
  async login(@Body() dto: LoginRequestDto) {
    return this.authService.login(dto);
  }

  @Public()
  @Post('face-login/init')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Iniciar desafío de reconocimiento facial' })
  async initFaceLogin(@Body() dto: FaceLoginInitDto) {
    return this.authService.initFaceLogin(dto);
  }

  @Public()
  @Post('face-login/verify')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Verificar captura facial y completar login' })
  async verifyFaceLogin(@Body() dto: FaceLoginVerifyDto) {
    return this.authService.verifyFaceLogin(dto);
  }
}
