import { ConflictException, ServiceUnavailableException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool } from 'pg';
import { DatabaseService } from './database.service';

function createDatabaseService(query: jest.Mock) {
  const configService = {
    get: (key: string) => (key === 'mockMode' ? false : undefined),
  } as unknown as ConfigService;
  const service = new DatabaseService(configService);

  Object.assign(service, {
    pool: { query } as unknown as Pool,
    isConnected: true,
  });

  return service;
}

describe('DatabaseService user registration persistence', () => {
  it('maps the DPI unique constraint to 409 without saving the user in memory', async () => {
    const databaseError = Object.assign(new Error('duplicate key'), {
      code: '23505',
      constraint: 'users_dpi_key',
    });
    const query = jest.fn().mockRejectedValue(databaseError);
    const service = createDatabaseService(query);

    await expect(
      service.createUser({
        id: 'user-id',
        cognitoSub: 'cognito-sub',
        email: 'user@example.com',
        fullName: 'Test User',
        dpi: '1234567890123',
      }),
    ).rejects.toBeInstanceOf(ConflictException);

    const internalState = service as unknown as { mockUsers: Map<string, unknown> };
    expect(internalState.mockUsers.has('cognito-sub')).toBe(false);
  });

  it('maps the email unique constraint to 409', async () => {
    const databaseError = Object.assign(new Error('duplicate key'), {
      code: '23505',
      constraint: 'users_email_key',
    });
    const service = createDatabaseService(jest.fn().mockRejectedValue(databaseError));

    await expect(
      service.createUser({
        id: 'user-id',
        cognitoSub: 'cognito-sub',
        email: 'user@example.com',
        fullName: 'Test User',
        dpi: '1234567890123',
      }),
    ).rejects.toMatchObject({
      response: {
        code: 'CONFLICT',
        message: 'Ya existe una cuenta registrada con este correo electrónico.',
      },
    });
  });

  it('returns 503 for other RDS insert failures instead of falling back to memory', async () => {
    const query = jest.fn().mockRejectedValue(new Error('connection reset'));
    const service = createDatabaseService(query);

    await expect(
      service.createUser({
        id: 'user-id',
        cognitoSub: 'cognito-sub',
        email: 'user@example.com',
        fullName: 'Test User',
        dpi: '1234567890123',
      }),
    ).rejects.toBeInstanceOf(ServiceUnavailableException);

    const internalState = service as unknown as { mockUsers: Map<string, unknown> };
    expect(internalState.mockUsers.has('cognito-sub')).toBe(false);
  });

  it('rejects registration when RDS is disconnected', async () => {
    const configService = {
      get: (key: string) => (key === 'mockMode' ? false : undefined),
    } as unknown as ConfigService;
    const service = new DatabaseService(configService);

    await expect(
      service.createUser({
        id: 'user-id',
        cognitoSub: 'cognito-sub',
        email: 'user@example.com',
        fullName: 'Test User',
        dpi: '1234567890123',
      }),
    ).rejects.toBeInstanceOf(ServiceUnavailableException);

    await expect(service.ping()).resolves.toBe(false);
  });

  it('rejects a duplicate DPI before creating the Cognito account', async () => {
    const query = jest.fn().mockResolvedValue({
      rows: [{ email: 'other@example.com', dpi: '1234567890123' }],
    });
    const service = createDatabaseService(query);

    await expect(service.assertUserIdentifiersAvailable('user@example.com', '1234567890123')).rejects.toMatchObject({
      response: {
        code: 'CONFLICT',
        message: 'Ya existe una cuenta registrada con este DPI.',
      },
    });
  });
});
