import { Injectable, Logger } from '@nestjs/common';
import { RegisterRequestDto, ConfirmRequestDto, LoginRequestDto, FaceLoginInitDto, FaceLoginVerifyDto } from './dto/auth.dto';
import { v4 as uuidv4 } from 'uuid';

@Injectable()
export class AuthService {
  private readonly logger = new Logger('AuthService');

  async register(dto: RegisterRequestDto) {
    this.logger.log(`Registrando nuevo usuario para: ${dto.email}`);
    return {
      userId: uuidv4(),
      email: dto.email,
      confirmationRequired: true,
      profileComplete: false,
    };
  }

  async confirm(dto: ConfirmRequestDto) {
    this.logger.log(`Confirmando código para: ${dto.email}`);
    return {
      confirmed: true,
      email: dto.email,
      message: 'Cuenta confirmada exitosamente. Proceda a iniciar sesión para completar su foto de perfil.',
    };
  }

  async login(dto: LoginRequestDto) {
    this.logger.log(`Inicio de sesión solicitado para: ${dto.email}`);
    return {
      accessToken: `mock-access-token-${uuidv4()}`,
      idToken: `mock-id-token-${uuidv4()}`,
      refreshToken: `mock-refresh-token-${uuidv4()}`,
      expiresIn: 3600,
      tokenType: 'Bearer',
      profileComplete: true,
    };
  }

  async initFaceLogin(dto: FaceLoginInitDto) {
    this.logger.log(`Desafío facial iniciado para: ${dto.email}`);
    return {
      challengeId: uuidv4(),
      uploadUrl: 'https://api-gateway-mock.us-east-1.amazonaws.com/uploads/images',
      purpose: 'faceCapture',
      expiresInSeconds: 120,
    };
  }

  async verifyFaceLogin(dto: FaceLoginVerifyDto) {
    this.logger.log(`Verificación de desafío facial: ${dto.challengeId}`);
    return {
      accessToken: `mock-access-token-face-${uuidv4()}`,
      idToken: `mock-id-token-face-${uuidv4()}`,
      refreshToken: `mock-refresh-token-face-${uuidv4()}`,
      expiresIn: 3600,
      tokenType: 'Bearer',
      profileComplete: true,
    };
  }
}
