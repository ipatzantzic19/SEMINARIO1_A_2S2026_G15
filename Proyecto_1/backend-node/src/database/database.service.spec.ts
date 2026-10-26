import { ConflictException, ServiceUnavailableException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool } from 'pg';
import { DatabaseService } from './database.service';

function createDatabaseService(query: jest.Mock, mockMode = false) {
  const configService = {
    get: (key: string) => (key === 'mockMode' ? mockMode : undefined),
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

describe('DatabaseService RDS failure handling and mock isolation', () => {
  const userA = '11111111-1111-4111-8111-111111111111';
  const userB = '22222222-2222-4222-8222-222222222222';

  describe('areFriends', () => {
    it('throws 503 SERVICE_UNAVAILABLE when RDS query fails with mocks disabled', async () => {
      const query = jest.fn().mockRejectedValue(new Error('connection timeout'));
      const service = createDatabaseService(query, false);

      await expect(service.areFriends(userA, userB)).rejects.toBeInstanceOf(ServiceUnavailableException);
    });

    it('throws 503 SERVICE_UNAVAILABLE when RDS is disconnected with mocks disabled', async () => {
      const query = jest.fn();
      const service = createDatabaseService(query, false);
      Object.assign(service, { isConnected: false });

      await expect(service.areFriends(userA, userB)).rejects.toBeInstanceOf(ServiceUnavailableException);
    });

    it('uses in-memory friendships when mockMode is true', async () => {
      const query = jest.fn();
      const service = createDatabaseService(query, true);

      // By default not friends
      await expect(service.areFriends(userA, userB)).resolves.toBe(false);

      // Add mock friendship
      const internalState = service as unknown as { mockFriendships: Map<string, unknown> };
      const lowId = userA < userB ? userA : userB;
      const highId = userA < userB ? userB : userA;
      internalState.mockFriendships.set(`${lowId}:${highId}`, { user_low_id: lowId, user_high_id: highId });

      await expect(service.areFriends(userA, userB)).resolves.toBe(true);
      expect(query).not.toHaveBeenCalled();
    });
  });

  describe('getPostById', () => {
    it('throws 503 SERVICE_UNAVAILABLE when RDS query fails with mocks disabled', async () => {
      const query = jest.fn().mockRejectedValue(new Error('RDS query error'));
      const service = createDatabaseService(query, false);

      await expect(service.getPostById('post-uuid-1')).rejects.toBeInstanceOf(ServiceUnavailableException);
    });

    it('throws 503 SERVICE_UNAVAILABLE when RDS is disconnected with mocks disabled', async () => {
      const query = jest.fn();
      const service = createDatabaseService(query, false);
      Object.assign(service, { isConnected: false });

      await expect(service.getPostById('post-uuid-1')).rejects.toBeInstanceOf(ServiceUnavailableException);
    });

    it('returns null without falling back to mock when post is not found in RDS', async () => {
      const query = jest.fn().mockResolvedValue({ rows: [] });
      const service = createDatabaseService(query, false);

      // Even if post exists in mockPosts, with mockMode: false it must query RDS and return null
      const internalState = service as unknown as { mockPosts: Map<string, unknown> };
      internalState.mockPosts.set('post-uuid-1', { id: 'post-uuid-1', description: 'Mock post' });

      await expect(service.getPostById('post-uuid-1')).resolves.toBeNull();
    });

    it('returns post from memory when mockMode is true', async () => {
      const query = jest.fn();
      const service = createDatabaseService(query, true);
      const internalState = service as unknown as { mockPosts: Map<string, unknown> };
      internalState.mockPosts.set('post-uuid-1', { id: 'post-uuid-1', description: 'Mock post' });

      const post = await service.getPostById('post-uuid-1');
      expect(post).toEqual(expect.objectContaining({ id: 'post-uuid-1', description: 'Mock post' }));
      expect(query).not.toHaveBeenCalled();
    });
  });

  describe('saveMessage', () => {
    it('throws 503 SERVICE_UNAVAILABLE and does NOT save in memory when RDS query fails with mocks disabled', async () => {
      const query = jest.fn((sql: string) => {
        if (sql.includes('friendships')) {
          return Promise.resolve({ rows: [{ '?column?': 1 }] });
        }
        return Promise.reject(new Error('RDS insert error'));
      });
      const service = createDatabaseService(query, false);
      const internalState = service as unknown as { mockMessages: Map<string, any> };
      const initialCount = internalState.mockMessages.size;

      await expect(
        service.saveMessage(userA, userB, 'Mensaje de prueba'),
      ).rejects.toBeInstanceOf(ServiceUnavailableException);

      expect(internalState.mockMessages.size).toBe(initialCount);
      const hasContent = Array.from(internalState.mockMessages.values()).some(
        (m: any) => m.content === 'Mensaje de prueba',
      );
      expect(hasContent).toBe(false);
    });

    it('saves in memory and returns message DTO when mockMode is true', async () => {
      const query = jest.fn();
      const service = createDatabaseService(query, true);

      const internalState = service as unknown as {
        mockFriendships: Map<string, unknown>;
        mockMessages: Map<string, unknown>;
      };
      const lowId = userA < userB ? userA : userB;
      const highId = userA < userB ? userB : userA;
      internalState.mockFriendships.set(`${lowId}:${highId}`, { user_low_id: lowId, user_high_id: highId });

      const result = await service.saveMessage(userA, userB, 'Mensaje mock');
      expect(result.body).toBe('Mensaje mock');
      expect(result.senderId).toBe(userA);
      expect(result.recipientId).toBe(userB);
      expect(internalState.mockMessages.has(result.messageId)).toBe(true);
      expect(query).not.toHaveBeenCalled();
    });
  });

  describe('getConversationMessages', () => {
    it('throws 503 SERVICE_UNAVAILABLE and does NOT return mock history when RDS query fails with mocks disabled', async () => {
      const query = jest.fn((sql: string) => {
        if (sql.includes('users WHERE id = $1')) {
          return Promise.resolve({ rows: [{ id: userB, full_name: 'User B', profile_image_key: null }] });
        }
        if (sql.includes('friendships')) {
          return Promise.resolve({ rows: [{ '?column?': 1 }] });
        }
        return Promise.reject(new Error('RDS select error'));
      });
      const service = createDatabaseService(query, false);

      const internalState = service as unknown as { mockMessages: Map<string, unknown> };
      internalState.mockMessages.set('msg-1', {
        id: 'msg-1',
        sender_id: userA,
        recipient_id: userB,
        content: 'Mock message fallback test',
        created_at: new Date().toISOString(),
        read_at: null,
      });

      await expect(
        service.getConversationMessages(userA, userB),
      ).rejects.toBeInstanceOf(ServiceUnavailableException);
    });

    it('returns conversation history from memory when mockMode is true', async () => {
      const query = jest.fn();
      const service = createDatabaseService(query, true);

      const internalState = service as unknown as {
        mockFriendships: Map<string, unknown>;
        mockMessages: Map<string, unknown>;
      };
      const lowId = userA < userB ? userA : userB;
      const highId = userA < userB ? userB : userA;
      internalState.mockFriendships.set(`${lowId}:${highId}`, { user_low_id: lowId, user_high_id: highId });

      internalState.mockMessages.set('msg-1', {
        id: 'msg-1',
        sender_id: userA,
        recipient_id: userB,
        content: 'Historial en memoria',
        created_at: new Date('2026-10-26T10:00:00Z').toISOString(),
        read_at: null,
      });

      const result = await service.getConversationMessages(userA, userB);
      expect(result.items.length).toBeGreaterThanOrEqual(2);
      expect(result.items.some((item) => item.body === 'Historial en memoria')).toBe(true);
      expect(query).not.toHaveBeenCalled();
    });
  });
});
