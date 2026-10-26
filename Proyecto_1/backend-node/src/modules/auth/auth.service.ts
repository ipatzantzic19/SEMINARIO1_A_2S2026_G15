import {
  Injectable,
  Logger,
  BadRequestException,
  UnauthorizedException,
  ConflictException,
  NotFoundException,
  HttpException,
  HttpStatus,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  CognitoIdentityProviderClient,
  SignUpCommand,
  AdminDeleteUserCommand,
  ConfirmSignUpCommand,
  ResendConfirmationCodeCommand,
  InitiateAuthCommand,
  UpdateUserAttributesCommand,
  AdminUpdateUserAttributesCommand,
  GetUserCommand,
  AuthFlowType,
} from '@aws-sdk/client-cognito-identity-provider';
import { v4 as uuidv4 } from 'uuid';
import { DatabaseService, DbUser } from '../../database/database.service';
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
    const normalizedDpi = dto.dpi.trim();
    this.logger.log(`Registrando usuario: ${normalizedEmail}`);

    await this.databaseService.assertUserIdentifiersAvailable(normalizedEmail, normalizedDpi);

    let cognitoSub = uuidv4();
    let cognitoUserCreated = false;

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
        cognitoUserCreated = true;
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
    let dbUser: DbUser;
    try {
      dbUser = await this.databaseService.createUser({
        id: userId,
        cognitoSub,
        email: normalizedEmail,
        fullName: dto.fullName.trim(),
        dpi: normalizedDpi,
      });
    } catch (dbError) {
      if (cognitoUserCreated) {
        try {
          await this.cognitoClient.send(
            new AdminDeleteUserCommand({
              UserPoolId: this.userPoolId,
              Username: normalizedEmail,
            }),
          );
          this.logger.warn(`Cuenta de Cognito revertida tras fallar la persistencia RDS: ${normalizedEmail}`);
        } catch (rollbackError: any) {
          this.logger.error(
            `No se pudo revertir la cuenta de Cognito ${normalizedEmail} tras fallar RDS: ${rollbackError.message}`,
          );

          if (dbError instanceof ConflictException) {
            throw new ConflictException({
              code: 'CONFLICT',
              message: 'Los datos ya están registrados y la cuenta de Cognito requiere conciliación manual.',
              details: { cognitoCleanupFailed: true },
            });
          }

          throw new ServiceUnavailableException({
            code: 'SERVICE_UNAVAILABLE',
            message: 'No se pudo guardar el usuario ni revertir su cuenta de Cognito; se requiere conciliación manual.',
            details: { cognitoCleanupFailed: true },
          });
        }
      }

      throw dbError;
    }

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

  async resendConfirmationCode(email: string): Promise<void> {
    const normalizedEmail = email.toLowerCase().trim();

    if (this.mockMode) {
      return;
    }

    try {
      await this.cognitoClient.send(
        new ResendConfirmationCodeCommand({
          ClientId: this.clientId,
          Username: normalizedEmail,
        }),
      );
    } catch (err: any) {
      const errorName = err?.name;
      this.logger.error(`Error en Cognito ResendConfirmationCode: ${errorName || 'UnknownError'}`);

      if (
        errorName === 'LimitExceededException' ||
        errorName === 'TooManyRequestsException' ||
        errorName === 'TooManyFailedAttemptsException' ||
        errorName === 'ThrottlingException'
      ) {
        throw new HttpException(
          {
            code: 'RATE_LIMITED',
            message: 'Se alcanzó el límite de reenvíos. Intente nuevamente más tarde.',
          },
          HttpStatus.TOO_MANY_REQUESTS,
        );
      }
      if (errorName === 'UserNotFoundException') {
        throw new NotFoundException({
          code: 'NOT_FOUND',
          message: 'No se encontró una cuenta pendiente de confirmación para ese correo.',
        });
      }
      if (errorName === 'NotAuthorizedException') {
        throw new BadRequestException({
          code: 'VALIDATION_ERROR',
          message: 'La cuenta no puede recibir otro código de confirmación.',
          details: { reason: 'RESEND_NOT_ALLOWED' },
        });
      }
      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'No fue posible solicitar el código de confirmación. Intente más tarde.',
      });
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

    let dbUser: DbUser | null = null;
    if (this.mockMode) {
      dbUser = await this.databaseService.findUserByEmail(normalizedEmail);
      const userSub = dbUser ? dbUser.cognito_sub : 'c09a8123-1122-3344-5566-778899aabbcc';
      this.databaseService.saveMockSession(accessToken, {
        cognitoSub: userSub,
        email: normalizedEmail,
      });
    } else {
      // Reconciliar con RDS igual que Python
      dbUser = await this.getOrReconcileUser('', accessToken, normalizedEmail);
    }

    return {
      accessToken,
      idToken,
      refreshToken,
      expiresIn,
      tokenType: 'Bearer',
      profileComplete: Boolean(dbUser?.profile_image_key),
    };
  }

  async getOrReconcileUser(cognitoSub?: string, accessToken?: string, fallbackEmail?: string): Promise<DbUser> {
    if (cognitoSub) {
      const existing = await this.databaseService.findUserByCognitoSub(cognitoSub);
      if (existing) {
        return existing;
      }
    }

    if (this.mockMode || !accessToken) {
      if (cognitoSub) {
        const mockUser = await this.databaseService.findUserByCognitoSub(cognitoSub);
        if (mockUser) return mockUser;
      }
      if (fallbackEmail) {
        const mockUser = await this.databaseService.findUserByEmail(fallbackEmail);
        if (mockUser) return mockUser;
      }
      throw new NotFoundException({
        code: 'NOT_FOUND',
        message: 'Usuario no encontrado en la base de datos.',
      });
    }

    let sub = cognitoSub || '';
    let email = (fallbackEmail || '').trim().toLowerCase();
    let fullName = '';
    let dpi = '';

    try {
      const command = new GetUserCommand({ AccessToken: accessToken });
      const userRes = await this.cognitoClient.send(command);
      const attrMap = new Map<string, string>();
      for (const attr of userRes.UserAttributes || []) {
        if (attr.Name && attr.Value) {
          attrMap.set(attr.Name, attr.Value);
        }
      }
      sub = attrMap.get('sub') || userRes.Username || sub;
      email = (attrMap.get('email') || email).trim().toLowerCase();
      fullName = (attrMap.get('name') || '').trim();
      dpi = (attrMap.get('custom:dpi') || '').trim();
    } catch (err: any) {
      this.logger.error(`Error al consultar atributos en Cognito para reconciliación: ${err.message}`);
      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'No fue posible validar los datos del usuario con el servicio de identidad.',
      });
    }

    if (sub) {
      const existing = await this.databaseService.findUserByCognitoSub(sub);
      if (existing) {
        return existing;
      }
    }

    if (!email || !fullName || !dpi) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'La cuenta de Cognito no tiene los atributos requeridos (nombre, email, DPI).',
      });
    }

    try {
      const newUser = await this.databaseService.createUser({
        id: uuidv4(),
        cognitoSub: sub,
        email,
        fullName,
        dpi,
      });
      this.logger.log(`Usuario reconciliado exitosamente en RDS: ${sub} (${email})`);
      return newUser;
    } catch (err: any) {
      if (err instanceof ConflictException) {
        const createdInParallel = await this.databaseService.findUserByCognitoSub(sub);
        if (createdInParallel) {
          return createdInParallel;
        }
        throw err;
      }
      throw err;
    }
  }

  async verifyCurrentPassword(email: string, password: string): Promise<boolean> {
    if (this.mockMode) {
      const lower = password.toLowerCase();
      if (lower.includes('equivocado') || lower.includes('wrong') || lower.includes('incorrect') || lower === 'invalid') {
        return false;
      }
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

  async updateFaceReferenceKey(cognitoSub: string, faceReferenceKey: string, accessToken?: string): Promise<void> {
    if (this.mockMode) {
      this.logger.log(`[MOCK] Actualizando custom:face_reference_key en Cognito para sub: ${cognitoSub} -> ${faceReferenceKey}`);
      return;
    }

    try {
      const adminCommand = new AdminUpdateUserAttributesCommand({
        UserPoolId: this.userPoolId,
        Username: cognitoSub,
        UserAttributes: [
          { Name: 'custom:face_reference_key', Value: faceReferenceKey },
        ],
      });
      await this.cognitoClient.send(adminCommand);
      this.logger.log(`custom:face_reference_key actualizado via AdminUpdateUserAttributes para sub: ${cognitoSub}`);
    } catch (adminErr: any) {
      this.logger.warn(`AdminUpdateUserAttributes falló (${adminErr.message}), intentando con UpdateUserAttributes...`);
      if (accessToken) {
        try {
          const userCommand = new UpdateUserAttributesCommand({
            AccessToken: accessToken,
            UserAttributes: [
              { Name: 'custom:face_reference_key', Value: faceReferenceKey },
            ],
          });
          await this.cognitoClient.send(userCommand);
          this.logger.log(`custom:face_reference_key actualizado via UpdateUserAttributes para sub: ${cognitoSub}`);
        } catch (userErr: any) {
          this.logger.error(`Error al actualizar custom:face_reference_key con UpdateUserAttributes: ${userErr.message}`);
        }
      }
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
