import { Controller, Post, Body, HttpCode, HttpStatus, Param } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { AuthService } from './auth.service';
import { Public } from '../../common/decorators/public.decorator';
import {
  RegisterRequestDto,
  ConfirmRequestDto,
  ResendConfirmationCodeRequestDto,
  LoginRequestDto,
  FaceChallengeRequestDto,
  FaceVerifyRequestDto,
} from './dto/auth.dto';

@ApiTags('Autenticación')
@Controller('auth')
export class AuthController {
  constructor(private authService: AuthService) {}

  @Public()
  @Post('register')
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: 'Registrar un nuevo usuario en Amazon Cognito y RDS' })
  @ApiResponse({ status: 201, description: 'Usuario registrado exitosamente (cuenta pendiente de confirmación)' })
  @ApiResponse({ status: 400, description: 'Datos inválidos o contraseña débil' })
  @ApiResponse({ status: 409, description: 'El correo electrónico ya existe' })
  async register(@Body() dto: RegisterRequestDto) {
    return this.authService.register(dto);
  }

  @Public()
  @Post('confirm')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Confirmar registro mediante código de verificación enviado por correo' })
  @ApiResponse({ status: 204, description: 'Cuenta confirmada exitosamente' })
  @ApiResponse({ status: 400, description: 'Código incorrecto o expirado' })
  async confirm(@Body() dto: ConfirmRequestDto): Promise<void> {
    await this.authService.confirm(dto);
  }

  @Public()
  @Post('confirm/resend')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Solicitar un nuevo código de confirmación de correo por Cognito' })
  @ApiResponse({ status: 204, description: 'Solicitud aceptada; Cognito envió un nuevo código.' })
  @ApiResponse({ status: 400, description: 'Correo inválido o cuenta que no puede recibir otro código' })
  @ApiResponse({ status: 404, description: 'Cuenta no encontrada (según la configuración del User Pool)' })
  @ApiResponse({ status: 429, description: 'Cognito limitó temporalmente los reenvíos' })
  @ApiResponse({ status: 503, description: 'Cognito o la entrega de correo no están disponibles' })
  async resendConfirmationCode(@Body() dto: ResendConfirmationCodeRequestDto): Promise<void> {
    await this.authService.resendConfirmationCode(dto.email);
  }

  @Public()
  @Post('login')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Iniciar sesión con correo y contraseña en Cognito' })
  @ApiResponse({ status: 200, description: 'Tokens de Cognito emitidos exitosamente' })
  @ApiResponse({ status: 401, description: 'Credenciales inválidas o cuenta no confirmada' })
  async login(@Body() dto: LoginRequestDto) {
    return this.authService.login(dto);
  }

  @Public()
  @Post('face/challenges')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Iniciar desafío de reconocimiento facial (PRO-31)' })
  @ApiResponse({ status: 200, description: 'Desafío y token de subida efímero generado' })
  async createFaceChallenge(@Body() dto: FaceChallengeRequestDto) {
    return this.authService.createFaceChallenge(dto);
  }

  @Public()
  @Post('face/challenges/:challengeId/verify')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Verificar captura facial contra la referencia privada de Cognito/S3' })
  @ApiResponse({ status: 200, description: 'Verificación exitosa y emisión de tokens' })
  @ApiResponse({ status: 422, description: 'Rostro no coincide con la foto de perfil' })
  async verifyFaceChallenge(
    @Param('challengeId') challengeId: string,
    @Body() dto: FaceVerifyRequestDto,
  ) {
    return this.authService.verifyFaceChallenge(challengeId, dto);
  }
}
