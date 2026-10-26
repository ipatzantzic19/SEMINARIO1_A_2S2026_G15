import { ConfigService } from '@nestjs/config';
import { HttpException } from '@nestjs/common';
import { CognitoIdentityProviderClient, ResendConfirmationCodeCommand } from '@aws-sdk/client-cognito-identity-provider';
import { DatabaseService } from '../../database/database.service';
import { AuthService } from './auth.service';

describe('AuthService resend confirmation code', () => {
  const configValues: Record<string, string | boolean> = {
    awsRegion: 'us-east-1',
    'cognito.userPoolId': 'test-pool',
    'cognito.appClientId': 'test-client',
    mockMode: false,
  };
  const configService = {
    get: (key: string) => configValues[key],
  } as unknown as ConfigService;
  const authService = new AuthService(configService, {} as DatabaseService);
  const cognitoClient = Object.getOwnPropertyDescriptor(authService, 'cognitoClient')?.value as CognitoIdentityProviderClient;

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('sends ResendConfirmationCodeCommand with the normalized email', async () => {
    const send = jest.spyOn(cognitoClient, 'send').mockResolvedValue({} as never);

    await authService.resendConfirmationCode(' User@Example.com ');

    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toBeInstanceOf(ResendConfirmationCodeCommand);
    expect(send.mock.calls[0][0].input).toEqual({
      ClientId: 'test-client',
      Username: 'user@example.com',
    });
  });

  it('maps Cognito rate limits to 429 RATE_LIMITED', async () => {
    const cognitoError = new Error('rate limited');
    cognitoError.name = 'LimitExceededException';
    jest.spyOn(cognitoClient, 'send').mockImplementation(() => Promise.reject(cognitoError));

    try {
      await authService.resendConfirmationCode('user@example.com');
      throw new Error('Expected Cognito rate-limit error');
    } catch (error) {
      expect(error).toBeInstanceOf(HttpException);
      expect((error as HttpException).getStatus()).toBe(429);
      expect((error as HttpException).getResponse()).toMatchObject({ code: 'RATE_LIMITED' });
    }
  });

  describe('getOrReconcileUser and login conflict', () => {
    it('reconciles Cognito user to RDS if missing in database', async () => {
      const mockDb = {
        findUserByCognitoSub: jest.fn().mockResolvedValue(null),
        createUser: jest.fn().mockResolvedValue({
          id: 'user-id-123',
          cognito_sub: 'cognito-sub-123',
          email: 'test@example.com',
          full_name: 'Test User',
          dpi: '1234567890101',
        }),
      } as unknown as DatabaseService;

      const testAuthService = new AuthService(configService, mockDb);
      const testCognitoClient = Object.getOwnPropertyDescriptor(testAuthService, 'cognitoClient')?.value as CognitoIdentityProviderClient;

      jest.spyOn(testCognitoClient, 'send').mockResolvedValue({
        Username: 'cognito-sub-123',
        UserAttributes: [
          { Name: 'sub', Value: 'cognito-sub-123' },
          { Name: 'email', Value: 'test@example.com' },
          { Name: 'name', Value: 'Test User' },
          { Name: 'custom:dpi', Value: '1234567890101' },
        ],
      } as never);

      const result = await testAuthService.getOrReconcileUser('cognito-sub-123', 'access-token-xyz');
      expect(result.id).toBe('user-id-123');
      expect(mockDb.createUser).toHaveBeenCalledWith({
        id: expect.any(String),
        cognitoSub: 'cognito-sub-123',
        email: 'test@example.com',
        fullName: 'Test User',
        dpi: '1234567890101',
      });
    });

    it('propagates 409 DUPLICATE_DPI when reconciling a user whose DPI is already in RDS', async () => {
      const { ConflictException } = await import('@nestjs/common');
      const mockDb = {
        findUserByCognitoSub: jest.fn().mockResolvedValue(null),
        createUser: jest.fn().mockRejectedValue(
          new ConflictException({
            code: 'CONFLICT',
            message: 'Ya existe una cuenta registrada con este DPI.',
            details: { reason: 'DUPLICATE_DPI' },
          }),
        ),
      } as unknown as DatabaseService;

      const testAuthService = new AuthService(configService, mockDb);
      const testCognitoClient = Object.getOwnPropertyDescriptor(testAuthService, 'cognitoClient')?.value as CognitoIdentityProviderClient;

      jest.spyOn(testCognitoClient, 'send').mockResolvedValue({
        Username: 'cognito-sub-conflict',
        UserAttributes: [
          { Name: 'sub', Value: 'cognito-sub-conflict' },
          { Name: 'email', Value: 'newuser@example.com' },
          { Name: 'name', Value: 'New User' },
          { Name: 'custom:dpi', Value: '1234567891011' },
        ],
      } as never);

      await expect(
        testAuthService.getOrReconcileUser('cognito-sub-conflict', 'access-token-conflict'),
      ).rejects.toMatchObject({
        response: {
          code: 'CONFLICT',
          message: 'Ya existe una cuenta registrada con este DPI.',
          details: { reason: 'DUPLICATE_DPI' },
        },
      });
    });
  });

  describe('createFaceChallenge and verifyFaceChallenge (Cognito CUSTOM_AUTH)', () => {
    it('initiates CUSTOM_AUTH with Cognito and returns 201 with challengeId, uploadToken, and expiresAt', async () => {
      const mockDb = {} as DatabaseService;
      const testAuthService = new AuthService(configService, mockDb);
      const testCognitoClient = Object.getOwnPropertyDescriptor(testAuthService, 'cognitoClient')?.value as CognitoIdentityProviderClient;

      jest.spyOn(testCognitoClient, 'send').mockResolvedValue({
        ChallengeName: 'CUSTOM_CHALLENGE',
        Session: 'cognito-session-token-123',
        ChallengeParameters: {
          challengeId: 'd09a8123-1122-3344-5566-778899aabbcc',
          USERNAME: 'user@example.com',
          expiresInSeconds: '120',
        },
      } as never);

      const result = await testAuthService.createFaceChallenge({ email: 'user@example.com' });
      expect(result).toHaveProperty('challengeId', 'd09a8123-1122-3344-5566-778899aabbcc');
      expect(result).toHaveProperty('uploadToken');
      expect(result).toHaveProperty('expiresAt');
    });

    it('maps missing face reference Lambda exception to 400 FACE_REFERENCE_MISSING', async () => {
      const mockDb = {} as DatabaseService;
      const testAuthService = new AuthService(configService, mockDb);
      const testCognitoClient = Object.getOwnPropertyDescriptor(testAuthService, 'cognitoClient')?.value as CognitoIdentityProviderClient;

      const lambdaErr = new Error('UserLambdaValidationException: MISSING_FACE_REFERENCE');
      lambdaErr.name = 'UserLambdaValidationException';
      jest.spyOn(testCognitoClient, 'send').mockRejectedValue(lambdaErr as never);

      await expect(
        testAuthService.createFaceChallenge({ email: 'noreference@example.com' }),
      ).rejects.toMatchObject({
        response: {
          code: 'VALIDATION_ERROR',
          message: 'La cuenta no tiene una referencia facial registrada.',
          details: { reason: 'FACE_REFERENCE_MISSING' },
        },
      });
    });

    it('returns decoy challenge for non-existent user for anti-enumeration', async () => {
      const mockDb = {} as DatabaseService;
      const testAuthService = new AuthService(configService, mockDb);
      const testCognitoClient = Object.getOwnPropertyDescriptor(testAuthService, 'cognitoClient')?.value as CognitoIdentityProviderClient;

      const notFoundErr = new Error('UserNotFoundException');
      notFoundErr.name = 'UserNotFoundException';
      jest.spyOn(testCognitoClient, 'send').mockRejectedValue(notFoundErr as never);

      const result = await testAuthService.createFaceChallenge({ email: 'ghost@example.com' });
      expect(result).toHaveProperty('challengeId');
      expect(result).toHaveProperty('uploadToken');
      expect(result).toHaveProperty('expiresAt');

      // Verifying a decoy challenge fails with 422 FACE_NOT_MATCHED
      await expect(
        testAuthService.verifyFaceChallenge(result.challengeId, {
          captureKey: `Fotos_Perfil/captures/${result.challengeId}/capture.jpg`,
        }),
      ).rejects.toMatchObject({
        response: {
          code: 'FACE_NOT_MATCHED',
        },
      });
    });

    it('rejects captureKey with invalid path or traversal with 400 INVALID_CAPTURE_KEY without consuming challenge', async () => {
      const mockDb = {} as DatabaseService;
      const testAuthService = new AuthService(configService, mockDb);
      const testCognitoClient = Object.getOwnPropertyDescriptor(testAuthService, 'cognitoClient')?.value as CognitoIdentityProviderClient;

      jest.spyOn(testCognitoClient, 'send').mockResolvedValue({
        ChallengeName: 'CUSTOM_CHALLENGE',
        Session: 'cognito-session-token-valid',
        ChallengeParameters: {
          challengeId: 'e19a8123-1122-3344-5566-778899aabbcc',
          USERNAME: 'user@example.com',
          expiresInSeconds: '120',
        },
      } as never);

      const challenge = await testAuthService.createFaceChallenge({ email: 'user@example.com' });

      // Bad captureKey with traversal
      await expect(
        testAuthService.verifyFaceChallenge(challenge.challengeId, {
          captureKey: `Fotos_Perfil/captures/${challenge.challengeId}/../other.jpg`,
        }),
      ).rejects.toMatchObject({
        response: {
          code: 'VALIDATION_ERROR',
          details: { reason: 'INVALID_CAPTURE_KEY' },
        },
      });

      // Bad captureKey from different challenge
      await expect(
        testAuthService.verifyFaceChallenge(challenge.challengeId, {
          captureKey: `Fotos_Perfil/captures/different-challenge-id/photo.jpg`,
        }),
      ).rejects.toMatchObject({
        response: {
          code: 'VALIDATION_ERROR',
          details: { reason: 'INVALID_CAPTURE_KEY' },
        },
      });
    });

    it('verifies face capture via RespondToAuthChallenge and returns real Cognito tokens', async () => {
      const mockDb = {
        findUserByCognitoSub: jest.fn().mockResolvedValue({
          id: 'user-db-id',
          cognito_sub: 'sub-123',
          profile_image_key: 'Fotos_Perfil/public/sub-123/img.jpg',
        }),
      } as unknown as DatabaseService;

      const testAuthService = new AuthService(configService, mockDb);
      const testCognitoClient = Object.getOwnPropertyDescriptor(testAuthService, 'cognitoClient')?.value as CognitoIdentityProviderClient;

      // 1. Create challenge
      jest.spyOn(testCognitoClient, 'send').mockResolvedValueOnce({
        ChallengeName: 'CUSTOM_CHALLENGE',
        Session: 'cognito-session-abc',
        ChallengeParameters: {
          challengeId: 'f29a8123-1122-3344-5566-778899aabbcc',
          USERNAME: 'user@example.com',
          expiresInSeconds: '120',
        },
      } as never);

      const challenge = await testAuthService.createFaceChallenge({ email: 'user@example.com' });

      // 2. Respond to auth challenge with positive AuthenticationResult
      jest.spyOn(testCognitoClient, 'send').mockResolvedValueOnce({
        AuthenticationResult: {
          AccessToken: 'real-cognito-access-token',
          IdToken: 'real-cognito-id-token',
          RefreshToken: 'real-cognito-refresh-token',
          ExpiresIn: 3600,
        },
      } as never);

      // Mock GetUserCommand for reconciliation
      jest.spyOn(testCognitoClient, 'send').mockResolvedValueOnce({
        Username: 'sub-123',
        UserAttributes: [
          { Name: 'sub', Value: 'sub-123' },
          { Name: 'email', Value: 'user@example.com' },
          { Name: 'name', Value: 'Test User' },
          { Name: 'custom:dpi', Value: '1234567890101' },
        ],
      } as never);

      const tokenResult = await testAuthService.verifyFaceChallenge(challenge.challengeId, {
        captureKey: `Fotos_Perfil/captures/${challenge.challengeId}/photo-uuid.jpg`,
      });

      expect(tokenResult).toEqual({
        accessToken: 'real-cognito-access-token',
        idToken: 'real-cognito-id-token',
        refreshToken: 'real-cognito-refresh-token',
        expiresIn: 3600,
        tokenType: 'Bearer',
        profileComplete: true,
      });
    });

    it('returns 422 FACE_NOT_MATCHED when Cognito indicates face does not match', async () => {
      const mockDb = {} as DatabaseService;
      const testAuthService = new AuthService(configService, mockDb);
      const testCognitoClient = Object.getOwnPropertyDescriptor(testAuthService, 'cognitoClient')?.value as CognitoIdentityProviderClient;

      // 1. Create challenge
      jest.spyOn(testCognitoClient, 'send').mockResolvedValueOnce({
        ChallengeName: 'CUSTOM_CHALLENGE',
        Session: 'cognito-session-mismatch',
        ChallengeParameters: {
          challengeId: 'a39a8123-1122-3344-5566-778899aabbcc',
          USERNAME: 'user@example.com',
          expiresInSeconds: '120',
        },
      } as never);

      const challenge = await testAuthService.createFaceChallenge({ email: 'user@example.com' });

      // 2. Cognito returns another CUSTOM_CHALLENGE (face didn't match)
      jest.spyOn(testCognitoClient, 'send').mockResolvedValueOnce({
        ChallengeName: 'CUSTOM_CHALLENGE',
        Session: 'cognito-session-retry',
      } as never);

      await expect(
        testAuthService.verifyFaceChallenge(challenge.challengeId, {
          captureKey: `Fotos_Perfil/captures/${challenge.challengeId}/different-face.jpg`,
        }),
      ).rejects.toMatchObject({
        response: {
          code: 'FACE_NOT_MATCHED',
        },
      });
    });
  });
});
