import { Controller, Post, Body, HttpCode, HttpStatus, Param, ParseUUIDPipe, Res } from '@nestjs/common';
import { Response } from 'express';
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
  @ApiResponse({ status: 409, description: 'El correo electrónico o DPI ya existe' })
  @ApiResponse({ status: 503, description: 'RDS no está disponible o falló la persistencia del usuario' })
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
  @ApiResponse({ status: 202, description: 'Cognito exige un desafío adicional' })
  async login(
    @Body() dto: LoginRequestDto,
    @Res({ passthrough: true }) response: Response,
  ) {
    const result = await this.authService.login(dto);
    if ('challenge' in result) {
      response.status(HttpStatus.ACCEPTED);
    }
    return result;
  }

  @Public()
  @Post('face/challenges')
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: 'Iniciar desafío de reconocimiento facial (PRO-31)' })
  @ApiResponse({ status: 201, description: 'Desafío facial efímero generado' })
  @ApiResponse({ status: 401, description: 'Cuenta no habilitada para acceso facial' })
  @ApiResponse({ status: 429, description: 'Límite de Cognito excedido' })
  @ApiResponse({ status: 503, description: 'El servicio de autenticación facial no está disponible' })
  async createFaceChallenge(@Body() dto: FaceChallengeRequestDto) {
    return this.authService.createFaceChallenge(dto);
  }

  @Public()
  @Post('face/challenges/:challengeId/verify')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Verificar captura facial contra la referencia privada de Cognito/S3' })
  @ApiResponse({ status: 200, description: 'Verificación exitosa y emisión de tokens' })
  @ApiResponse({ status: 400, description: 'La captura no corresponde al desafío' })
  @ApiResponse({ status: 404, description: 'Desafío inexistente, expirado o ya utilizado' })
  @ApiResponse({ status: 422, description: 'Rostro no coincide con la foto de perfil' })
  @ApiResponse({ status: 429, description: 'Límite de Cognito excedido' })
  @ApiResponse({ status: 503, description: 'El servicio de autenticación facial no está disponible' })
  async verifyFaceChallenge(
    @Param('challengeId', new ParseUUIDPipe({ version: '4' })) challengeId: string,
    @Body() dto: FaceVerifyRequestDto,
  ) {
    return this.authService.verifyFaceChallenge(challengeId, dto);
  }
}
