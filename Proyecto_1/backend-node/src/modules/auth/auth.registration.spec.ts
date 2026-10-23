import { ConfigService } from '@nestjs/config';
import { ConflictException, HttpException, ServiceUnavailableException } from '@nestjs/common';
import {
  AdminDeleteUserCommand,
  CognitoIdentityProviderClient,
  SignUpCommand,
} from '@aws-sdk/client-cognito-identity-provider';
import { DatabaseService } from '../../database/database.service';
import { RegisterRequestDto } from './dto/auth.dto';
import { AuthService } from './auth.service';

describe('AuthService registration persistence', () => {
  const dto: RegisterRequestDto = {
    fullName: 'Test User',
    email: ' User@Example.com ',
    dpi: '1234567890123',
    password: 'StrongPassword2026!#',
  };
  const configValues: Record<string, string | boolean> = {
    awsRegion: 'us-east-1',
    'cognito.userPoolId': 'test-pool',
    'cognito.appClientId': 'test-client',
    mockMode: false,
  };

  function createService(databaseService: Partial<DatabaseService>) {
    const configService = {
      get: (key: string) => configValues[key],
    } as unknown as ConfigService;
    const service = new AuthService(configService, databaseService as DatabaseService);
    const cognitoClient = (service as unknown as { cognitoClient: CognitoIdentityProviderClient }).cognitoClient;

    return { service, cognitoClient };
  }

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('does not create a Cognito account when RDS reports an existing DPI', async () => {
    const conflict = new ConflictException({ code: 'CONFLICT', message: 'DPI duplicado' });
    const databaseService = {
      assertUserIdentifiersAvailable: jest.fn().mockRejectedValue(conflict),
      createUser: jest.fn(),
    };
    const { service, cognitoClient } = createService(databaseService);
    const send = jest.spyOn(cognitoClient, 'send');

    await expect(service.register(dto)).rejects.toBe(conflict);

    expect(send).not.toHaveBeenCalled();
    expect(databaseService.createUser).not.toHaveBeenCalled();
  });

  it('deletes the Cognito account when the RDS insert fails with a unique conflict', async () => {
    const conflict = new ConflictException({ code: 'CONFLICT', message: 'DPI duplicado' });
    const databaseService = {
      assertUserIdentifiersAvailable: jest.fn().mockResolvedValue(undefined),
      createUser: jest.fn().mockRejectedValue(conflict),
    };
    const { service, cognitoClient } = createService(databaseService);
    const send = jest.spyOn(cognitoClient, 'send').mockImplementation(() =>
      Promise.resolve({ UserSub: 'cognito-user-sub' } as never),
    );

    try {
      await service.register(dto);
      throw new Error('Expected registration conflict');
    } catch (error) {
      expect(error).toBeInstanceOf(ConflictException);
      expect((error as HttpException).getStatus()).toBe(409);
    }

    expect(databaseService.assertUserIdentifiersAvailable).toHaveBeenCalledWith('user@example.com', '1234567890123');
    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[0][0]).toBeInstanceOf(SignUpCommand);
    expect(send.mock.calls[1][0]).toBeInstanceOf(AdminDeleteUserCommand);
    expect(send.mock.calls[1][0].input).toMatchObject({
      UserPoolId: 'test-pool',
      Username: 'user@example.com',
    });
  });

  it('reports manual reconciliation if Cognito rollback fails after RDS failure', async () => {
    const databaseService = {
      assertUserIdentifiersAvailable: jest.fn().mockResolvedValue(undefined),
      createUser: jest.fn().mockRejectedValue(new Error('database unavailable')),
    };
    const { service, cognitoClient } = createService(databaseService);
    jest
      .spyOn(cognitoClient, 'send')
      .mockImplementationOnce(() => Promise.resolve({ UserSub: 'cognito-user-sub' } as never))
      .mockImplementationOnce(() => Promise.reject(new Error('access denied')));

    await expect(service.register(dto)).rejects.toBeInstanceOf(ServiceUnavailableException);
  });
});
