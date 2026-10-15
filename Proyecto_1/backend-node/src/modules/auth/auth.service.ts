import {
  Injectable,
  Logger,
  BadRequestException,
  UnauthorizedException,
  ConflictException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  CognitoIdentityProviderClient,
  SignUpCommand,
  ConfirmSignUpCommand,
  InitiateAuthCommand,
  UpdateUserAttributesCommand,
  AuthFlowType,
} from '@aws-sdk/client-cognito-identity-provider';
import { v4 as uuidv4 } from 'uuid';
import { DatabaseService } from '../../database/database.service';
import {
  RegisterRequestDto,
  ConfirmRequestDto,
  LoginRequestDto,
  FaceChallengeRequestDto,
  FaceVerifyRequestDto,
} from './dto/auth.dto';

@Injectable()
export class AuthService {
  private readonly logger = new Logger('AuthService');
  private cognitoClient: CognitoIdentityProviderClient;
  private userPoolId: string;
  private clientId: string;
  private mockMode: boolean;

  constructor(
    private configService: ConfigService,
    private databaseService: DatabaseService,
  ) {
    const region = this.configService.get<string>('awsRegion') || 'us-east-1';
    this.userPoolId = this.configService.get<string>('cognito.userPoolId') || 'us-east-1_4UrrCPt8Z';
    this.clientId = this.configService.get<string>('cognito.appClientId') || '1feavcj8qvobr4ltshlgnolg5f';
    this.mockMode = this.configService.get<boolean>('mockMode') || false;

    this.cognitoClient = new CognitoIdentityProviderClient({ region });
  }

  async register(dto: RegisterRequestDto) {
    const normalizedEmail = dto.email.toLowerCase().trim();
    this.logger.log(`Registrando usuario: ${normalizedEmail}`);

    let cognitoSub = uuidv4();

    if (!this.mockMode) {
      try {
        const command = new SignUpCommand({
          ClientId: this.clientId,
          Username: normalizedEmail,
          Password: dto.password,
          UserAttributes: [
            { Name: 'email', Value: normalizedEmail },
            { Name: 'name', Value: dto.fullName.trim() },
            { Name: 'custom:dpi', Value: dto.dpi.trim() },
          ],
        });

        const response = await this.cognitoClient.send(command);
        if (response.UserSub) {
          cognitoSub = response.UserSub;
        }
        this.logger.log(`Usuario registrado en Cognito con sub: ${cognitoSub}`);
      } catch (err: any) {
        this.logger.error(`Error en Cognito SignUp: ${err.name} - ${err.message}`);
        if (err.name === 'UsernameExistsException') {
          throw new ConflictException({
            code: 'CONFLICT',
            message: 'Ya existe una cuenta registrada con este correo electrónico.',
          });
        }
        if (err.name === 'InvalidPasswordException') {
          throw new BadRequestException({
            code: 'VALIDATION_ERROR',
            message: 'La contraseña no cumple con la política de seguridad de Cognito.',
            details: { reason: err.message },
          });
        }
        throw new BadRequestException({
          code: 'VALIDATION_ERROR',
          message: err.message || 'Error al registrar usuario en el servicio de identidad.',
        });
      }
    }

    // Persistir o sincronizar en PostgreSQL RDS
    const userId = uuidv4();
    const dbUser = await this.databaseService.createUser({
      id: userId,
      cognitoSub,
      email: normalizedEmail,
      fullName: dto.fullName.trim(),
      dpi: dto.dpi.trim(),
    });

    return {
      userId: dbUser.id,
      email: dbUser.email,
      confirmationRequired: true,
      profileComplete: false,
    };
  }

  async confirm(dto: ConfirmRequestDto): Promise<void> {
    const normalizedEmail = dto.email.toLowerCase().trim();
    this.logger.log(`Confirmando registro para: ${normalizedEmail}`);

    if (!this.mockMode) {
      try {
        const command = new ConfirmSignUpCommand({
          ClientId: this.clientId,
          Username: normalizedEmail,
          ConfirmationCode: dto.code.trim(),
        });
        await this.cognitoClient.send(command);
        this.logger.log(`Cuenta confirmada en Cognito: ${normalizedEmail}`);
      } catch (err: any) {
        this.logger.error(`Error en Cognito ConfirmSignUp: ${err.name} - ${err.message}`);
        if (err.name === 'CodeMismatchException') {
          throw new BadRequestException({
            code: 'VALIDATION_ERROR',
            message: 'El código de confirmación ingresado es incorrecto.',
          });
        }
        if (err.name === 'ExpiredCodeException') {
          throw new BadRequestException({
            code: 'VALIDATION_ERROR',
            message: 'El código de confirmación ha expirado. Solicite uno nuevo.',
          });
        }
        throw new BadRequestException({
          code: 'VALIDATION_ERROR',
          message: err.message || 'No se pudo confirmar la cuenta.',
        });
      }
    }
  }

  async login(dto: LoginRequestDto) {
    const normalizedEmail = dto.email.toLowerCase().trim();
    this.logger.log(`Inicio de sesión para: ${normalizedEmail}`);

    let accessToken = `mock-access-token-${uuidv4()}`;
    let idToken = `mock-id-token-${uuidv4()}`;
    let refreshToken = `mock-refresh-token-${uuidv4()}`;
    let expiresIn = 3600;

    if (!this.mockMode) {
      try {
        const command = new InitiateAuthCommand({
          AuthFlow: AuthFlowType.USER_PASSWORD_AUTH,
          ClientId: this.clientId,
          AuthParameters: {
            USERNAME: normalizedEmail,
            PASSWORD: dto.password,
          },
        });

        const response = await this.cognitoClient.send(command);

        if (response.AuthenticationResult) {
          accessToken = response.AuthenticationResult.AccessToken || accessToken;
          idToken = response.AuthenticationResult.IdToken || idToken;
          refreshToken = response.AuthenticationResult.RefreshToken || refreshToken;
          expiresIn = response.AuthenticationResult.ExpiresIn || expiresIn;
        } else if (response.ChallengeName) {
          return {
            challenge: response.ChallengeName,
            session: response.Session,
            parameters: response.ChallengeParameters,
          };
        }
      } catch (err: any) {
        this.logger.error(`Error en Cognito InitiateAuth: ${err.name} - ${err.message}`);
        if (err.name === 'NotAuthorizedException' || err.name === 'UserNotFoundException') {
          throw new UnauthorizedException({
            code: 'UNAUTHENTICATED',
            message: 'Credenciales inválidas. Verifique su correo y contraseña.',
          });
        }
        if (err.name === 'UserNotConfirmedException') {
          throw new UnauthorizedException({
            code: 'UNAUTHENTICATED',
            message: 'La cuenta aún no ha sido confirmada con el código enviado por correo.',
          });
        }
        throw new BadRequestException({
          code: 'VALIDATION_ERROR',
          message: err.message || 'Error al autenticar con el servicio de identidad.',
        });
      }
    }

    // Verificar si el usuario ya completó su foto de perfil en la base de datos
    const dbUser = await this.databaseService.findUserByEmail(normalizedEmail);
    const profileComplete = Boolean(dbUser?.profile_image_key);
    const userSub = dbUser ? dbUser.cognito_sub : 'c09a8123-1122-3344-5566-778899aabbcc';

    if (this.mockMode) {
      this.databaseService.saveMockSession(accessToken, {
        cognitoSub: userSub,
        email: normalizedEmail,
      });
    }

    return {
      accessToken,
      idToken,
      refreshToken,
      expiresIn,
      tokenType: 'Bearer',
      profileComplete,
    };
  }

  async verifyCurrentPassword(email: string, password: string): Promise<boolean> {
    if (this.mockMode) {
      return true;
    }
    try {
      const command = new InitiateAuthCommand({
        AuthFlow: AuthFlowType.USER_PASSWORD_AUTH,
        ClientId: this.clientId,
        AuthParameters: {
          USERNAME: email.toLowerCase().trim(),
          PASSWORD: password,
        },
      });
      const response = await this.cognitoClient.send(command);
      return Boolean(response.AuthenticationResult?.AccessToken);
    } catch {
      return false;
    }
  }

  async updateCognitoProfile(accessToken: string, updates: { fullName?: string; dpi?: string }) {
    if (this.mockMode) return;

    const attributes: { Name: string; Value: string }[] = [];
    if (updates.fullName) {
      attributes.push({ Name: 'name', Value: updates.fullName });
    }
    if (updates.dpi) {
      attributes.push({ Name: 'custom:dpi', Value: updates.dpi });
    }

    if (attributes.length === 0) return;

    try {
      const command = new UpdateUserAttributesCommand({
        AccessToken: accessToken,
        UserAttributes: attributes,
      });
      await this.cognitoClient.send(command);
    } catch (err: any) {
      this.logger.warn(`Error al actualizar atributos en Cognito: ${err.message}`);
    }
  }

  async createFaceChallenge(dto: FaceChallengeRequestDto) {
    const challengeId = uuidv4();
    const expiresAt = new Date(Date.now() + 120000).toISOString();
    return {
      challengeId,
      uploadToken: `token-${uuidv4()}`,
      expiresAt,
    };
  }

  async verifyFaceChallenge(challengeId: string, dto: FaceVerifyRequestDto) {
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
