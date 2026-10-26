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
});
