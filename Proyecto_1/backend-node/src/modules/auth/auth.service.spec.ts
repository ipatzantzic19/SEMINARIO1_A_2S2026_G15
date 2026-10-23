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
});
