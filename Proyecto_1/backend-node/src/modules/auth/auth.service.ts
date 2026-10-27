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
  UnprocessableEntityException,
  Optional,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  CognitoIdentityProviderClient,
  SignUpCommand,
  AdminDeleteUserCommand,
  ConfirmSignUpCommand,
  ResendConfirmationCodeCommand,
  InitiateAuthCommand,
  RespondToAuthChallengeCommand,
  UpdateUserAttributesCommand,
  AdminUpdateUserAttributesCommand,
  GetUserCommand,
  AuthFlowType,
} from '@aws-sdk/client-cognito-identity-provider';
import { issueFaceUploadToken } from './face-upload-token';
import { v4 as uuidv4 } from 'uuid';
import { DatabaseService, DbUser } from '../../database/database.service';
import { FaceChallengeStore } from './face-challenge.store';
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
  private faceChallengeStore: FaceChallengeStore;

  constructor(
    private configService: ConfigService,
    private databaseService: DatabaseService,
    @Optional() faceChallengeStore?: FaceChallengeStore,
  ) {
    this.faceChallengeStore = faceChallengeStore || new FaceChallengeStore();
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
      this.logger.error(`Error en Cognito UpdateUserAttributes: ${err.name} - ${err.message}`);
      const errorName = err?.name;
      if (errorName === 'InvalidParameterException') {
        throw new BadRequestException({
          code: 'VALIDATION_ERROR',
          message: 'No fue posible actualizar el perfil con los datos enviados.',
          details: { reason: 'INVALID_PARAMETER' },
        });
      }
      if (errorName === 'AliasExistsException') {
        throw new ConflictException({
          code: 'CONFLICT',
          message: 'Ya existe una cuenta con ese correo.',
          details: { reason: 'EMAIL_TAKEN' },
        });
      }
      if (errorName === 'NotAuthorizedException' || errorName === 'UserNotFoundException') {
        throw new UnauthorizedException({
          code: 'UNAUTHENTICATED',
          message: 'La sesión no es válida.',
        });
      }
      if (
        errorName === 'LimitExceededException' ||
        errorName === 'TooManyRequestsException' ||
        errorName === 'TooManyFailedAttemptsException' ||
        errorName === 'ThrottlingException'
      ) {
        throw new HttpException(
          {
            code: 'RATE_LIMITED',
            message: 'Se excedió el límite de intentos. Intente más tarde.',
          },
          HttpStatus.TOO_MANY_REQUESTS,
        );
      }
      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'No fue posible actualizar los atributos en el servicio de identidad.',
      });
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
    const normalizedEmail = dto.email.toLowerCase().trim();
    this.logger.log(`Iniciando desafío facial para: ${normalizedEmail}`);

    if (this.mockMode) {
      const challengeId = uuidv4();
      const ttlSeconds = 120;
      const { uploadToken, expiresAt } = issueFaceUploadToken(
        this.configService.get<string>('faceUpload.privateKeyFile'),
        this.configService.get<string>('faceUpload.keyId'),
        challengeId, ttlSeconds,
      );
      this.faceChallengeStore.add({
        challengeId,
        username: normalizedEmail,
        session: `mock-session-${uuidv4()}`,
        uploadToken,
        expiresAt,
      });
      return {
        challengeId,
        expiresAt: new Date(expiresAt).toISOString(),
        uploadToken,
      };
    }

    try {
      const command = new InitiateAuthCommand({
        AuthFlow: AuthFlowType.CUSTOM_AUTH,
        ClientId: this.clientId,
        AuthParameters: {
          USERNAME: normalizedEmail,
        },
      });

      const response = await this.cognitoClient.send(command);
      const challengeId = response.ChallengeParameters?.challengeId;

      if (response.ChallengeName !== 'CUSTOM_CHALLENGE' || !challengeId || !response.Session) {
        return this.createDecoyChallenge();
      }

      const ttlParam = parseInt(response.ChallengeParameters?.expiresInSeconds || '120', 10);
      const ttlSeconds = Math.max(30, Math.min(300, isNaN(ttlParam) ? 120 : ttlParam));
      const username = response.ChallengeParameters?.USERNAME || normalizedEmail;
      const { uploadToken, expiresAt } = issueFaceUploadToken(
        this.configService.get<string>('faceUpload.privateKeyFile'),
        this.configService.get<string>('faceUpload.keyId'),
        challengeId, ttlSeconds,
      );

      this.faceChallengeStore.add({
        challengeId,
        username,
        session: response.Session,
        uploadToken,
        expiresAt,
      });

      return {
        challengeId,
        expiresAt: new Date(expiresAt).toISOString(),
        uploadToken,
      };
    } catch (err: any) {
      const errorName = err?.name;
      const errorMessage = err?.message || '';

      if (errorName === 'UserLambdaValidationException' && errorMessage.includes('MISSING_FACE_REFERENCE')) {
        throw new BadRequestException({
          code: 'VALIDATION_ERROR',
          message: 'La cuenta no tiene una referencia facial registrada.',
          details: { reason: 'FACE_REFERENCE_MISSING' },
        });
      }

      if (errorName === 'UserNotFoundException' || errorName === 'NotAuthorizedException') {
        // Anti-enumeración: responder 201 con reto señuelo que fallará en verify con 422
        return this.createDecoyChallenge();
      }

      if (errorName === 'UserNotConfirmedException') {
        throw new UnauthorizedException({
          code: 'UNAUTHENTICATED',
          message: 'La cuenta aún no está confirmada. Revise el código enviado a su correo.',
          details: { reason: 'USER_NOT_CONFIRMED' },
        });
      }

      if (errorName === 'PasswordResetRequiredException') {
        throw new UnauthorizedException({
          code: 'UNAUTHENTICATED',
          message: 'Debe restablecer su contraseña antes de iniciar sesión.',
          details: { reason: 'PASSWORD_RESET_REQUIRED' },
        });
      }

      if (
        errorName === 'LimitExceededException' ||
        errorName === 'TooManyRequestsException' ||
        errorName === 'TooManyFailedAttemptsException' ||
        errorName === 'ThrottlingException'
      ) {
        throw new HttpException(
          {
            code: 'RATE_LIMITED',
            message: 'Se excedió el límite de intentos. Intente más tarde.',
          },
          HttpStatus.TOO_MANY_REQUESTS,
        );
      }

      this.logger.error(`Error en Cognito InitiateAuth (CUSTOM_AUTH): ${errorName} - ${errorMessage}`);
      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'El servicio de autenticación facial no está disponible temporalmente.',
      });
    }
  }

  private createDecoyChallenge() {
    const challengeId = uuidv4();
    const ttlSeconds = 120;
    const { uploadToken, expiresAt } = issueFaceUploadToken(
      this.configService.get<string>('faceUpload.privateKeyFile'),
      this.configService.get<string>('faceUpload.keyId'),
      challengeId, ttlSeconds,
    );
    this.faceChallengeStore.add({
      challengeId,
      username: '',
      session: null,
      uploadToken,
      expiresAt,
    });
    return {
      challengeId,
      expiresAt: new Date(expiresAt).toISOString(),
      uploadToken,
    };
  }

  async verifyFaceChallenge(challengeId: string, dto: FaceVerifyRequestDto) {
    const prefix = `Fotos_Perfil/captures/${challengeId}/`;
    const captureFileRegex = /^[A-Za-z0-9._-]+$/;
    const captureKey = dto.captureKey || '';

    if (
      captureKey.length > 1024 ||
      captureKey.includes('..') ||
      !captureKey.startsWith(prefix) ||
      !captureFileRegex.test(captureKey.slice(prefix.length))
    ) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'La clave de la captura no es válida.',
        details: { reason: 'INVALID_CAPTURE_KEY' },
      });
    }

    const challenge = this.faceChallengeStore.take(challengeId);
    if (!challenge) {
      throw new NotFoundException({
        code: 'NOT_FOUND',
        message: 'El desafío facial no existe o venció.',
      });
    }

    if (challenge.session === null) {
      throw new UnprocessableEntityException({
        code: 'FACE_NOT_MATCHED',
        message: 'El rostro de la captura no coincide con la foto de perfil registrada.',
      });
    }

    if (this.mockMode) {
      const dbUser = await this.databaseService.findUserByEmail(challenge.username);
      return {
        accessToken: `mock-access-token-face-${uuidv4()}`,
        idToken: `mock-id-token-face-${uuidv4()}`,
        refreshToken: `mock-refresh-token-face-${uuidv4()}`,
        expiresIn: 3600,
        tokenType: 'Bearer',
        profileComplete: Boolean(dbUser?.profile_image_key),
      };
    }

    const answer = JSON.stringify({
      challengeId,
      purpose: 'faceCapture',
      captureKey,
    });

    try {
      const command = new RespondToAuthChallengeCommand({
        ClientId: this.clientId,
        ChallengeName: 'CUSTOM_CHALLENGE',
        Session: challenge.session,
        ChallengeResponses: {
          USERNAME: challenge.username,
          ANSWER: answer,
        },
      });

      const response = await this.cognitoClient.send(command);

      if (response.AuthenticationResult) {
        const result = response.AuthenticationResult;
        const accessToken = result.AccessToken;
        const idToken = result.IdToken;
        const refreshToken = result.RefreshToken;
        const expiresIn = result.ExpiresIn || 3600;

        if (!accessToken || !idToken || !refreshToken) {
          throw new ServiceUnavailableException({
            code: 'SERVICE_UNAVAILABLE',
            message: 'Tokens de autenticación incompletos recibidos de Cognito.',
          });
        }

        const dbUser = await this.getOrReconcileUser(challenge.username, accessToken);

        return {
          accessToken,
          idToken,
          refreshToken,
          expiresIn,
          tokenType: 'Bearer',
          profileComplete: Boolean(dbUser?.profile_image_key),
        };
      }

      if (response.ChallengeName === 'CUSTOM_CHALLENGE') {
        throw new UnprocessableEntityException({
          code: 'FACE_NOT_MATCHED',
          message: 'El rostro de la captura no coincide con la foto de perfil registrada.',
        });
      }

      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'Respuesta inesperada del servicio de autenticación facial.',
      });
    } catch (err: any) {
      if (err instanceof HttpException) {
        throw err;
      }

      const errorName = err?.name;
      this.logger.error(`Error en Cognito RespondToAuthChallenge: ${errorName} - ${err?.message}`);

      if (errorName === 'NotAuthorizedException' || errorName === 'UserNotFoundException') {
        throw new UnprocessableEntityException({
          code: 'FACE_NOT_MATCHED',
          message: 'El rostro de la captura no coincide con la foto de perfil registrada.',
        });
      }

      if (
        errorName === 'LimitExceededException' ||
        errorName === 'TooManyRequestsException' ||
        errorName === 'TooManyFailedAttemptsException' ||
        errorName === 'ThrottlingException'
      ) {
        this.faceChallengeStore.putBack(challenge);
        throw new HttpException(
          {
            code: 'RATE_LIMITED',
            message: 'Se excedió el límite de intentos. Intente más tarde.',
          },
          HttpStatus.TOO_MANY_REQUESTS,
        );
      }

      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'El servicio de autenticación facial no está disponible temporalmente.',
      });
    }
  }
}
