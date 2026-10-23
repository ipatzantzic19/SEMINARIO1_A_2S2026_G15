import {
  Injectable,
  OnModuleInit,
  OnModuleDestroy,
  Logger,
  BadRequestException,
  ConflictException,
  NotFoundException,
  ForbiddenException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool, QueryResult } from 'pg';
import { v4 as uuidv4 } from 'uuid';
import { EventEmitter } from 'events';

export interface DbMessage {
  id: string;
  sender_id: string;
  recipient_id: string;
  content: string;
  created_at: string;
  read_at: string | null;
}

export interface MessageDtoResponse {
  messageId: string;
  senderId: string;
  recipientId: string;
  body: string;
  createdAt: string;
  readAt: string | null;
}

export interface ChatNotificationPayload {
  messageId: string;
  clientMessageId?: string;
  senderId: string;
  recipientId: string;
  body: string;
  createdAt: string;
}

export interface DbUser {
  id: string;
  cognito_sub: string;
  email: string;
  full_name: string;
  dpi: string;
  profile_image_key: string | null;
  face_reference_key: string | null;
  created_at: string;
  updated_at: string;
}

export interface DbFriendRequest {
  id: string;
  requester_id: string;
  addressee_id: string;
  status: 'pending' | 'accepted' | 'rejected' | 'canceled';
  created_at: string;
  responded_at: string | null;
}

export interface DbFriendship {
  user_low_id: string;
  user_high_id: string;
  request_id: string | null;
  created_at: string;
}

export interface PublicUserInfo {
  userId: string;
  fullName: string;
  profileImageUrl: string;
}

export interface FriendRequestDtoResponse {
  requestId: string;
  requester: PublicUserInfo;
  addressee: PublicUserInfo;
  status: 'pending' | 'accepted' | 'rejected';
  createdAt: string;
}

export interface DbPost {
  id: string;
  author_id: string;
  description: string | null;
  image_key: string;
  created_at: string;
  updated_at: string;
}

export interface DbPostLabel {
  post_id: string;
  normalized_label: string;
  source_label: string;
  confidence: number;
  created_at?: string;
}

export interface DbComment {
  id: string;
  post_id: string;
  author_id: string;
  content: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface PostResponseDto {
  id: string;
  postId?: string;
  authorId?: string;
  author: PublicUserInfo;
  description: string | null;
  imageKey: string;
  imageUrl: string;
  labels: any[];
  labelDetails?: { name: string; confidence: number; sourceName: string }[];
  commentsCount: number;
  createdAt: string;
}

export interface CommentResponseDto {
  commentId: string;
  id: string;
  postId: string;
  author: PublicUserInfo;
  body: string;
  content: string;
  createdAt: string;
}

@Injectable()
export class DatabaseService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger('DatabaseService');
  private pool: Pool | null = null;
  private isConnected = false;

  // Almacenamiento en memoria para desarrollo local / mock mode
  private mockUsers = new Map<string, DbUser>();
  private mockSessions = new Map<string, { cognitoSub: string; email: string }>();
  private mockFriendRequests = new Map<string, DbFriendRequest>();
  private mockFriendships = new Map<string, DbFriendship>(); // key: `${lowId}:${highId}`
  private mockPosts = new Map<string, DbPost>();
  private mockPostLabels = new Map<string, DbPostLabel[]>(); // key: postId
  private mockComments = new Map<string, DbComment>();
  private mockMessages = new Map<string, DbMessage>(); // key: messageId
  public readonly chatEvents = new EventEmitter();

  constructor(private configService: ConfigService) {
    // Usuario mock por defecto para pruebas (Daniel)
    const defaultUser: DbUser = {
      id: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
      cognito_sub: 'c09a8123-1122-3344-5566-778899aabbcc',
      email: 'daniel.ortiz@ingenieria.usac.edu.gt',
      full_name: 'Daniel Abraham Ortiz',
      dpi: '1234567890101',
      profile_image_key: null,
      face_reference_key: null,
      created_at: new Date('2026-10-18T08:00:00Z').toISOString(),
      updated_at: new Date('2026-10-18T08:00:00Z').toISOString(),
    };
    this.mockUsers.set(defaultUser.id, defaultUser);
    this.mockUsers.set(defaultUser.cognito_sub, defaultUser);
    this.mockUsers.set(defaultUser.email.toLowerCase(), defaultUser);

    // Usuarios demo para pruebas en Postman y desarrollo local (con perfil completo)
    const anaUser: DbUser = {
      id: '11111111-1111-4111-8111-111111111111',
      cognito_sub: 'sub-ana-1111',
      email: 'ana@example.com',
      full_name: 'Ana López',
      dpi: '1000000000001',
      profile_image_key: 'Fotos_Perfil/public/sub-ana-1111/avatar.jpg',
      face_reference_key: 'Fotos_Perfil/references/sub-ana-1111/ref.jpg',
      created_at: new Date('2026-10-18T08:05:00Z').toISOString(),
      updated_at: new Date('2026-10-18T08:05:00Z').toISOString(),
    };
    this.saveMockUser(anaUser);
    this.saveMockSession('token-ana', { cognitoSub: anaUser.cognito_sub, email: anaUser.email });
    this.saveMockSession('token-ana-111', { cognitoSub: anaUser.cognito_sub, email: anaUser.email });

    const brunoUser: DbUser = {
      id: '22222222-2222-4222-8222-222222222222',
      cognito_sub: 'sub-bruno-2222',
      email: 'bruno@example.com',
      full_name: 'Bruno Díaz',
      dpi: '2000000000002',
      profile_image_key: 'Fotos_Perfil/public/sub-bruno-2222/avatar.jpg',
      face_reference_key: 'Fotos_Perfil/references/sub-bruno-2222/ref.jpg',
      created_at: new Date('2026-10-18T08:10:00Z').toISOString(),
      updated_at: new Date('2026-10-18T08:10:00Z').toISOString(),
    };
    this.saveMockUser(brunoUser);
    this.saveMockSession('token-bruno', { cognitoSub: brunoUser.cognito_sub, email: brunoUser.email });
    this.saveMockSession('token-bruno-222', { cognitoSub: brunoUser.cognito_sub, email: brunoUser.email });

    const carlaUser: DbUser = {
      id: '33333333-3333-4333-8333-333333333333',
      cognito_sub: 'sub-carla-3333',
      email: 'carla@example.com',
      full_name: 'Carla Ruiz',
      dpi: '3000000000003',
      profile_image_key: 'Fotos_Perfil/public/sub-carla-3333/avatar.jpg',
      face_reference_key: 'Fotos_Perfil/references/sub-carla-3333/ref.jpg',
      created_at: new Date('2026-10-18T08:20:00Z').toISOString(),
      updated_at: new Date('2026-10-18T08:20:00Z').toISOString(),
    };
    this.saveMockUser(carlaUser);
    this.saveMockSession('token-carla', { cognitoSub: carlaUser.cognito_sub, email: carlaUser.email });
    this.saveMockSession('token-carla-333', { cognitoSub: carlaUser.cognito_sub, email: carlaUser.email });

    const javierUser: DbUser = {
      id: '44444444-4444-4444-8444-444444444444',
      cognito_sub: 'sub-javier-4444',
      email: 'javier@example.com',
      full_name: 'Javier Velásquez',
      dpi: '4000000000004',
      profile_image_key: 'Fotos_Perfil/public/sub-javier-4444/avatar.jpg',
      face_reference_key: 'Fotos_Perfil/references/sub-javier-4444/ref.jpg',
      created_at: new Date('2026-10-18T08:30:00Z').toISOString(),
      updated_at: new Date('2026-10-18T08:30:00Z').toISOString(),
    };
    this.saveMockUser(javierUser);
    this.saveMockSession('token-javier', { cognitoSub: javierUser.cognito_sub, email: javierUser.email });

    // En modo desarrollo local fuera de Jest, sembramos amistad para probar de inmediato en Postman y chat-test.html
    if (process.env.NODE_ENV !== 'test') {
      this.mockFriendships.set(`${anaUser.id}:${brunoUser.id}`, {
        user_low_id: anaUser.id,
        user_high_id: brunoUser.id,
        request_id: null,
        created_at: new Date('2026-10-18T08:15:00Z').toISOString(),
      });
    }

    const initialMsg: DbMessage = {
      id: '9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d',
      sender_id: brunoUser.id,
      recipient_id: anaUser.id,
      content: '¡Hola Ana! ¿Pudiste revisar los tickets de la Fase 2?',
      created_at: new Date('2026-10-18T09:00:00Z').toISOString(),
      read_at: null,
    };
    this.mockMessages.set(initialMsg.id, initialMsg);
  }

  saveMockSession(token: string, session: { cognitoSub: string; email: string }) {
    this.mockSessions.set(token, session);
  }

  getMockSession(token: string): { cognitoSub: string; email: string } | undefined {
    return this.mockSessions.get(token);
  }

  getProfileImageUrl(profileImageKey: string | null): string {
    if (!profileImageKey) return '';
    const bucket = this.configService.get<string>('s3.imagesBucket') || 'semisocial-g15-images-581117996165';
    const region = this.configService.get<string>('aws.region') || 'us-east-1';
    return `https://${bucket}.s3.${region}.amazonaws.com/${profileImageKey}`;
  }

  async onModuleInit() {
    const mockMode = this.configService.get<boolean>('mockMode');
    if (mockMode) {
      this.logger.log('Base de datos operando en MOCK MODE (desarrollo/pruebas).');
      this.isConnected = true;
      return;
    }

    const rds = this.configService.get('rds') as any;
    try {
      this.pool = new Pool({
        host: rds.host,
        port: rds.port,
        database: rds.database,
        user: rds.user,
        password: rds.password,
        ssl: rds.sslMode === 'require' || rds.sslMode === 'verify-full' ? { rejectUnauthorized: false } : undefined,
        max: 20,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 5000,
      });

      this.pool.on('error', (err) => {
        this.logger.error('Error imprevisto en el cliente de PostgreSQL:', err);
      });

      // Prueba de conexión inicial
      const client = await this.pool.connect();
      await client.query('SELECT 1');
      client.release();
      this.isConnected = true;
      this.logger.log(`Conexión establecida con PostgreSQL en ${rds.host}:${rds.port}/${rds.database}`);
    } catch (err: any) {
      this.isConnected = false;
      this.logger.error(
        `No se pudo conectar a PostgreSQL en ${rds?.host}: ${err.message}. Las operaciones que requieren RDS no estarán disponibles.`,
      );
    }
  }

  async onModuleDestroy() {
    if (this.pool) {
      await this.pool.end();
      this.logger.log('Pool de PostgreSQL cerrado correctamente.');
    }
  }

  async ping(): Promise<boolean> {
    const mockMode = this.configService.get<boolean>('mockMode');
    if (mockMode) {
      return true;
    }

    if (!this.pool || !this.isConnected) {
      return false;
    }

    try {
      const res = await this.pool.query('SELECT 1');
      return res && res.rowCount ? res.rowCount > 0 : false;
    } catch {
      return false;
    }
  }

  async findUserByCognitoSub(cognitoSub: string): Promise<DbUser | null> {
    if (this.pool && this.isConnected) {
      try {
        const res = await this.pool.query('SELECT * FROM users WHERE cognito_sub = $1', [cognitoSub]);
        if (res.rows.length > 0) return res.rows[0];
      } catch (err: any) {
        this.logger.warn(`Error en DB query findUserByCognitoSub: ${err.message}`);
      }
    }
    return this.mockUsers.get(cognitoSub) || null;
  }

  async findUserByEmail(email: string): Promise<DbUser | null> {
    const normalized = email.toLowerCase().trim();
    if (this.pool && this.isConnected) {
      try {
        const res = await this.pool.query('SELECT * FROM users WHERE email = $1', [normalized]);
        if (res.rows.length > 0) return res.rows[0];
      } catch (err: any) {
        this.logger.warn(`Error en DB query findUserByEmail: ${err.message}`);
      }
    }
    return this.mockUsers.get(normalized) || null;
  }

  async assertUserIdentifiersAvailable(email: string, dpi: string): Promise<void> {
    if (this.configService.get<boolean>('mockMode')) {
      return;
    }

    if (!this.pool || !this.isConnected) {
      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'No se puede validar el registro porque la base de datos no está disponible.',
      });
    }

    try {
      const normalizedEmail = email.toLowerCase().trim();
      const normalizedDpi = dpi.trim();
      const result = await this.pool.query(
        'SELECT email, dpi FROM users WHERE email = $1 OR dpi = $2 LIMIT 1',
        [normalizedEmail, normalizedDpi],
      );
      const existingUser = result.rows[0];

      if (existingUser) {
        if (String(existingUser.email).toLowerCase() === normalizedEmail) {
          throw new ConflictException({
            code: 'CONFLICT',
            message: 'Ya existe una cuenta registrada con este correo electrónico.',
          });
        }

        throw new ConflictException({
          code: 'CONFLICT',
          message: 'Ya existe una cuenta registrada con este DPI.',
        });
      }
    } catch (err: any) {
      if (err instanceof ConflictException || err instanceof ServiceUnavailableException) {
        throw err;
      }

      this.logger.error(`Error en DB query assertUserIdentifiersAvailable: ${err.message}`);
      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'No se pudo validar el registro en la base de datos.',
      });
    }
  }

  async createUser(user: { id: string; cognitoSub: string; email: string; fullName: string; dpi: string }): Promise<DbUser> {
    const now = new Date().toISOString();
    const newUser: DbUser = {
      id: user.id,
      cognito_sub: user.cognitoSub,
      email: user.email.toLowerCase().trim(),
      full_name: user.fullName,
      dpi: user.dpi,
      profile_image_key: null,
      face_reference_key: null,
      created_at: now,
      updated_at: now,
    };

    if (this.configService.get<boolean>('mockMode')) {
      this.saveMockUser(newUser);
      return newUser;
    }

    if (!this.pool || !this.isConnected) {
      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'No se pudo guardar el usuario porque la base de datos no está disponible.',
      });
    }

    try {
      await this.pool.query(
        `INSERT INTO users (id, cognito_sub, email, full_name, dpi, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [newUser.id, newUser.cognito_sub, newUser.email, newUser.full_name, newUser.dpi, now, now],
      );
    } catch (err: any) {
      if (err?.code === '23505') {
        const constraint = String(err.constraint || '');
        const message = constraint.includes('dpi')
          ? 'Ya existe una cuenta registrada con este DPI.'
          : constraint.includes('email')
            ? 'Ya existe una cuenta registrada con este correo electrónico.'
            : 'Los datos del usuario ya están registrados.';

        throw new ConflictException({ code: 'CONFLICT', message });
      }

      this.logger.error(`Error en DB query createUser: ${err.message}`);
      throw new ServiceUnavailableException({
        code: 'SERVICE_UNAVAILABLE',
        message: 'No se pudo guardar el usuario en la base de datos.',
      });
    }

    return newUser;
  }

  saveMockUser(user: DbUser) {
    this.mockUsers.set(user.id, user);
    this.mockUsers.set(user.cognito_sub, user);
    this.mockUsers.set(user.email.toLowerCase(), user);
  }

  async completeProfile(cognitoSub: string, profileImageKey: string, faceReferenceKey?: string): Promise<DbUser | null> {
    const now = new Date().toISOString();
    const user = await this.findUserByCognitoSub(cognitoSub);
    if (!user) return null;

    user.profile_image_key = profileImageKey;
    const derivedRef = profileImageKey.startsWith('Fotos_Perfil/public/')
      ? profileImageKey.replace('Fotos_Perfil/public/', 'Fotos_Perfil/references/')
      : `Fotos_Perfil/references/${cognitoSub}/${profileImageKey.replace(/^Fotos_Perfil\//, '')}`;
    user.face_reference_key = faceReferenceKey || derivedRef;
    user.updated_at = now;

    if (this.pool && this.isConnected) {
      try {
        await this.pool.query(
          `UPDATE users SET profile_image_key = $1, face_reference_key = $2, updated_at = $3 WHERE cognito_sub = $4`,
          [user.profile_image_key, user.face_reference_key, now, cognitoSub],
        );
      } catch (err: any) {
        this.logger.warn(`Error en DB completeProfile: ${err.message}`);
      }
    }

    this.mockUsers.set(cognitoSub, user);
    this.mockUsers.set(user.email, user);
    this.mockUsers.set(user.id, user);
    return user;
  }

  async updateProfile(cognitoSub: string, updates: { fullName?: string; dpi?: string; profileImageKey?: string; faceReferenceKey?: string }): Promise<DbUser | null> {
    const now = new Date().toISOString();
    const user = await this.findUserByCognitoSub(cognitoSub);
    if (!user) return null;

    if (updates.fullName) user.full_name = updates.fullName;
    if (updates.dpi) user.dpi = updates.dpi;
    if (updates.profileImageKey) {
      user.profile_image_key = updates.profileImageKey;
      if (updates.faceReferenceKey) {
        user.face_reference_key = updates.faceReferenceKey;
      }
    }
    user.updated_at = now;

    if (this.pool && this.isConnected) {
      try {
        await this.pool.query(
          `UPDATE users SET full_name = $1, dpi = $2, profile_image_key = $3, face_reference_key = COALESCE($4, face_reference_key), updated_at = $5 WHERE cognito_sub = $6`,
          [user.full_name, user.dpi, user.profile_image_key, updates.faceReferenceKey || null, now, cognitoSub],
        );
      } catch (err: any) {
        this.logger.warn(`Error en DB updateProfile: ${err.message}`);
      }
    }

    this.mockUsers.set(cognitoSub, user);
    this.mockUsers.set(user.email, user);
    this.mockUsers.set(user.id, user);
    return user;
  }

  async findUserById(id: string): Promise<DbUser | null> {
    if (this.pool && this.isConnected) {
      try {
        const res = await this.pool.query('SELECT * FROM users WHERE id = $1', [id]);
        if (res.rows.length > 0) return res.rows[0];
      } catch (err: any) {
        this.logger.warn(`Error en DB query findUserById: ${err.message}`);
      }
    }
    return this.mockUsers.get(id) || null;
  }

  async listNonFriends(
    userId: string,
    cursor?: string,
    limit: number = 20,
  ): Promise<{ items: PublicUserInfo[]; nextCursor: string | null }> {
    const safeLimit = Math.min(Math.max(limit || 20, 1), 50);

    if (this.pool && this.isConnected) {
      try {
        let queryStr = `
          SELECT id, full_name, profile_image_key, created_at
          FROM users
          WHERE id <> $1
            AND profile_image_key IS NOT NULL
            AND id NOT IN (
              SELECT user_high_id FROM friendships WHERE user_low_id = $1
              UNION
              SELECT user_low_id FROM friendships WHERE user_high_id = $1
            )
        `;
        const params: any[] = [userId];

        if (cursor) {
          try {
            const decoded = Buffer.from(cursor, 'base64').toString('utf8');
            const [cursorCreatedAt, cursorId] = decoded.split('#');
            if (cursorCreatedAt && cursorId) {
              params.push(cursorCreatedAt, cursorId);
              queryStr += ` AND (created_at < $${params.length - 1} OR (created_at = $${params.length - 1} AND id < $${params.length}))`;
            }
          } catch {
            // Si el cursor es inválido, se ignora
          }
        }

        params.push(safeLimit + 1);
        queryStr += ` ORDER BY created_at DESC, id DESC LIMIT $${params.length}`;

        const res = await this.pool.query(queryStr, params);
        const rows = res.rows;
        const hasMore = rows.length > safeLimit;
        const resultRows = hasMore ? rows.slice(0, safeLimit) : rows;

        let nextCursor: string | null = null;
        if (hasMore && resultRows.length > 0) {
          const last = resultRows[resultRows.length - 1];
          nextCursor = Buffer.from(`${last.created_at}#${last.id}`).toString('base64');
        }

        return {
          items: resultRows.map((r) => ({
            userId: r.id,
            fullName: r.full_name,
            profileImageUrl: this.getProfileImageUrl(r.profile_image_key),
          })),
          nextCursor,
        };
      } catch (err: any) {
        this.logger.warn(`Error en DB listNonFriends: ${err.message}. Fallback a mock.`);
      }
    }

    // Mock Mode fallback
    const allUniqueUsers = Array.from(
      new Map(Array.from(this.mockUsers.values()).map((u) => [u.id, u])).values(),
    );

    let candidates = allUniqueUsers.filter((u) => {
      if (u.id === userId) return false;
      if (!u.profile_image_key) return false;

      const lowId = userId < u.id ? userId : u.id;
      const highId = userId < u.id ? u.id : userId;
      if (this.mockFriendships.has(`${lowId}:${highId}`)) return false;

      return true;
    });

    candidates.sort((a, b) => {
      const timeDiff = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      if (timeDiff !== 0) return timeDiff;
      return b.id.localeCompare(a.id);
    });

    if (cursor) {
      try {
        const decoded = Buffer.from(cursor, 'base64').toString('utf8');
        const [cursorCreatedAt, cursorId] = decoded.split('#');
        const cursorTime = new Date(cursorCreatedAt).getTime();
        candidates = candidates.filter((u) => {
          const uTime = new Date(u.created_at).getTime();
          if (uTime < cursorTime) return true;
          if (uTime === cursorTime && u.id < cursorId) return true;
          return false;
        });
      } catch {
        // Cursor inválido ignorado
      }
    }

    const hasMore = candidates.length > safeLimit;
    const items = hasMore ? candidates.slice(0, safeLimit) : candidates;

    let nextCursor: string | null = null;
    if (hasMore && items.length > 0) {
      const last = items[items.length - 1];
      nextCursor = Buffer.from(`${last.created_at}#${last.id}`).toString('base64');
    }

    return {
      items: items.map((u) => ({
        userId: u.id,
        fullName: u.full_name,
        profileImageUrl: this.getProfileImageUrl(u.profile_image_key),
      })),
      nextCursor,
    };
  }

  async createFriendRequest(requesterId: string, addresseeId: string): Promise<FriendRequestDtoResponse> {
    if (requesterId === addresseeId) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'No puedes enviarte una solicitud de amistad a ti mismo.',
      });
    }

    const requester = await this.findUserById(requesterId);
    if (!requester) {
      throw new NotFoundException({
        code: 'NOT_FOUND',
        message: 'Usuario solicitante no encontrado.',
      });
    }

    const addressee = await this.findUserById(addresseeId);
    if (!addressee) {
      throw new NotFoundException({
        code: 'NOT_FOUND',
        message: 'El usuario destinatario no existe.',
      });
    }

    if (!addressee.profile_image_key) {
      throw new BadRequestException({
        code: 'PROFILE_INCOMPLETE',
        message: 'El usuario destinatario no tiene su perfil completo.',
      });
    }

    const lowId = requesterId < addresseeId ? requesterId : addresseeId;
    const highId = requesterId < addresseeId ? addresseeId : requesterId;

    if (this.pool && this.isConnected) {
      try {
        // 1. Verificar si ya son amigos
        const friendRes = await this.pool.query(
          'SELECT 1 FROM friendships WHERE user_low_id = $1 AND user_high_id = $2',
          [lowId, highId],
        );
        if (friendRes.rows.length > 0) {
          throw new ConflictException({
            code: 'CONFLICT',
            message: 'Ya existe una relación de amistad entre ambos usuarios.',
          });
        }

        // 2. Verificar si ya hay solicitud pendiente en cualquier dirección
        const pendingRes = await this.pool.query(
          `SELECT 1 FROM friend_requests
           WHERE ((requester_id = $1 AND addressee_id = $2) OR (requester_id = $2 AND addressee_id = $1))
             AND status = 'pending'`,
          [requesterId, addresseeId],
        );
        if (pendingRes.rows.length > 0) {
          throw new ConflictException({
            code: 'CONFLICT',
            message: 'Ya existe una solicitud de amistad pendiente con este usuario.',
          });
        }

        const newId = uuidv4();
        const now = new Date().toISOString();
        const insertRes = await this.pool.query(
          `INSERT INTO friend_requests (id, requester_id, addressee_id, status, created_at)
           VALUES ($1, $2, $3, 'pending', $4)
           RETURNING *`,
          [newId, requesterId, addresseeId, now],
        );
        const reqRow = insertRes.rows[0];

        return {
          requestId: reqRow.id,
          requester: {
            userId: requester.id,
            fullName: requester.full_name,
            profileImageUrl: this.getProfileImageUrl(requester.profile_image_key),
          },
          addressee: {
            userId: addressee.id,
            fullName: addressee.full_name,
            profileImageUrl: this.getProfileImageUrl(addressee.profile_image_key),
          },
          status: 'pending',
          createdAt: reqRow.created_at,
        };
      } catch (err: any) {
        if (err instanceof ConflictException || err instanceof BadRequestException || err instanceof NotFoundException) {
          throw err;
        }
        if (err.code === '23505') {
          throw new ConflictException({
            code: 'CONFLICT',
            message: 'Ya existe una solicitud de amistad pendiente entre ambos usuarios.',
          });
        }
        if (err.code === '23514') {
          throw new BadRequestException({
            code: 'VALIDATION_ERROR',
            message: 'Violación de restricción en solicitud de amistad.',
          });
        }
        this.logger.warn(`Error en DB createFriendRequest: ${err.message}. Guardando en memoria.`);
      }
    }

    // Mock Mode fallback
    if (this.mockFriendships.has(`${lowId}:${highId}`)) {
      throw new ConflictException({
        code: 'CONFLICT',
        message: 'Ya existe una relación de amistad entre ambos usuarios.',
      });
    }

    const existingPending = Array.from(this.mockFriendRequests.values()).find(
      (r) =>
        r.status === 'pending' &&
        ((r.requester_id === requesterId && r.addressee_id === addresseeId) ||
          (r.requester_id === addresseeId && r.addressee_id === requesterId)),
    );

    if (existingPending) {
      throw new ConflictException({
        code: 'CONFLICT',
        message: 'Ya existe una solicitud de amistad pendiente con este usuario.',
      });
    }

    const newReq: DbFriendRequest = {
      id: uuidv4(),
      requester_id: requesterId,
      addressee_id: addresseeId,
      status: 'pending',
      created_at: new Date().toISOString(),
      responded_at: null,
    };
    this.mockFriendRequests.set(newReq.id, newReq);

    return {
      requestId: newReq.id,
      requester: {
        userId: requester.id,
        fullName: requester.full_name,
        profileImageUrl: this.getProfileImageUrl(requester.profile_image_key),
      },
      addressee: {
        userId: addressee.id,
        fullName: addressee.full_name,
        profileImageUrl: this.getProfileImageUrl(addressee.profile_image_key),
      },
      status: 'pending',
      createdAt: newReq.created_at,
    };
  }

  async listFriendRequests(userId: string): Promise<FriendRequestDtoResponse[]> {
    if (this.pool && this.isConnected) {
      try {
        const queryStr = `
          SELECT 
            fr.id as request_id, fr.status, fr.created_at,
            req.id as req_id, req.full_name as req_name, req.profile_image_key as req_img,
            addr.id as addr_id, addr.full_name as addr_name, addr.profile_image_key as addr_img
          FROM friend_requests fr
          JOIN users req ON req.id = fr.requester_id
          JOIN users addr ON addr.id = fr.addressee_id
          WHERE (fr.requester_id = $1 OR fr.addressee_id = $1)
            AND fr.status = 'pending'
          ORDER BY fr.created_at DESC
        `;
        const res = await this.pool.query(queryStr, [userId]);
        return res.rows.map((r) => ({
          requestId: r.request_id,
          requester: {
            userId: r.req_id,
            fullName: r.req_name,
            profileImageUrl: this.getProfileImageUrl(r.req_img),
          },
          addressee: {
            userId: r.addr_id,
            fullName: r.addr_name,
            profileImageUrl: this.getProfileImageUrl(r.addr_img),
          },
          status: r.status,
          createdAt: r.created_at,
        }));
      } catch (err: any) {
        this.logger.warn(`Error en DB listFriendRequests: ${err.message}. Fallback a mock.`);
      }
    }

    // Mock Mode fallback
    const requests = Array.from(this.mockFriendRequests.values())
      .filter(
        (r) =>
          r.status === 'pending' &&
          (r.requester_id === userId || r.addressee_id === userId),
      )
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const result: FriendRequestDtoResponse[] = [];
    for (const r of requests) {
      const requester = await this.findUserById(r.requester_id);
      const addressee = await this.findUserById(r.addressee_id);
      if (requester && addressee) {
        result.push({
          requestId: r.id,
          requester: {
            userId: requester.id,
            fullName: requester.full_name,
            profileImageUrl: this.getProfileImageUrl(requester.profile_image_key),
          },
          addressee: {
            userId: addressee.id,
            fullName: addressee.full_name,
            profileImageUrl: this.getProfileImageUrl(addressee.profile_image_key),
          },
          status: r.status as 'pending' | 'accepted' | 'rejected',
          createdAt: r.created_at,
        });
      }
    }

    return result;
  }

  async answerFriendRequest(
    requestId: string,
    userId: string,
    decision: 'accepted' | 'rejected',
  ): Promise<FriendRequestDtoResponse> {
    if (this.pool && this.isConnected) {
      try {
        const checkRes = await this.pool.query(
          `SELECT fr.*,
                  req.id as req_id, req.full_name as req_name, req.profile_image_key as req_img,
                  addr.id as addr_id, addr.full_name as addr_name, addr.profile_image_key as addr_img
           FROM friend_requests fr
           JOIN users req ON req.id = fr.requester_id
           JOIN users addr ON addr.id = fr.addressee_id
           WHERE fr.id = $1`,
          [requestId],
        );

        if (checkRes.rows.length === 0) {
          throw new NotFoundException({
            code: 'NOT_FOUND',
            message: 'Solicitud de amistad no encontrada.',
          });
        }

        const reqRow = checkRes.rows[0];

        // Solo el destinatario puede responder a la solicitud (criterio C no puede aceptar la de B)
        if (reqRow.addressee_id !== userId) {
          throw new ForbiddenException({
            code: 'FORBIDDEN',
            message: 'Solo el destinatario puede responder a esta solicitud de amistad.',
          });
        }

        if (reqRow.status !== 'pending') {
          throw new BadRequestException({
            code: 'VALIDATION_ERROR',
            message: 'La solicitud de amistad ya fue respondida previamente.',
          });
        }

        const now = new Date().toISOString();
        const client = await this.pool.connect();
        try {
          await client.query('BEGIN');
          await client.query(
            'UPDATE friend_requests SET status = $1, responded_at = $2 WHERE id = $3',
            [decision, now, requestId],
          );

          if (decision === 'accepted') {
            const lowId = reqRow.requester_id < reqRow.addressee_id ? reqRow.requester_id : reqRow.addressee_id;
            const highId = reqRow.requester_id < reqRow.addressee_id ? reqRow.addressee_id : reqRow.requester_id;
            await client.query(
              `INSERT INTO friendships (user_low_id, user_high_id, request_id, created_at)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (user_low_id, user_high_id) DO NOTHING`,
              [lowId, highId, requestId, now],
            );
          }
          await client.query('COMMIT');
        } catch (txErr) {
          await client.query('ROLLBACK');
          throw txErr;
        } finally {
          client.release();
        }

        return {
          requestId: reqRow.id,
          requester: {
            userId: reqRow.req_id,
            fullName: reqRow.req_name,
            profileImageUrl: this.getProfileImageUrl(reqRow.req_img),
          },
          addressee: {
            userId: reqRow.addr_id,
            fullName: reqRow.addr_name,
            profileImageUrl: this.getProfileImageUrl(reqRow.addr_img),
          },
          status: decision,
          createdAt: reqRow.created_at,
        };
      } catch (err: any) {
        if (err instanceof NotFoundException || err instanceof ForbiddenException || err instanceof BadRequestException) {
          throw err;
        }
        this.logger.warn(`Error en DB answerFriendRequest: ${err.message}. Fallback a mock.`);
      }
    }

    // Mock Mode fallback
    const req = this.mockFriendRequests.get(requestId);
    if (!req) {
      throw new NotFoundException({
        code: 'NOT_FOUND',
        message: 'Solicitud de amistad no encontrada.',
      });
    }

    if (req.addressee_id !== userId) {
      throw new ForbiddenException({
        code: 'FORBIDDEN',
        message: 'Solo el destinatario puede responder a esta solicitud de amistad.',
      });
    }

    if (req.status !== 'pending') {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'La solicitud de amistad ya fue respondida previamente.',
      });
    }

    const now = new Date().toISOString();
    req.status = decision;
    req.responded_at = now;
    this.mockFriendRequests.set(req.id, req);

    if (decision === 'accepted') {
      const lowId = req.requester_id < req.addressee_id ? req.requester_id : req.addressee_id;
      const highId = req.requester_id < req.addressee_id ? req.addressee_id : req.requester_id;
      this.mockFriendships.set(`${lowId}:${highId}`, {
        user_low_id: lowId,
        user_high_id: highId,
        request_id: req.id,
        created_at: now,
      });
    }

    const requester = await this.findUserById(req.requester_id);
    const addressee = await this.findUserById(req.addressee_id);

    return {
      requestId: req.id,
      requester: {
        userId: requester!.id,
        fullName: requester!.full_name,
        profileImageUrl: this.getProfileImageUrl(requester!.profile_image_key),
      },
      addressee: {
        userId: addressee!.id,
        fullName: addressee!.full_name,
        profileImageUrl: this.getProfileImageUrl(addressee!.profile_image_key),
      },
      status: decision,
      createdAt: req.created_at,
    };
  }

  async listFriends(userId: string): Promise<PublicUserInfo[]> {
    if (this.pool && this.isConnected) {
      try {
        const queryStr = `
          SELECT 
            u.id as user_id, 
            u.full_name, 
            u.profile_image_key
          FROM friendships f
          JOIN users u ON (u.id = CASE WHEN f.user_low_id = $1 THEN f.user_high_id ELSE f.user_low_id END)
          WHERE f.user_low_id = $1 OR f.user_high_id = $1
          ORDER BY u.full_name ASC
        `;
        const res = await this.pool.query(queryStr, [userId]);
        return res.rows.map((r) => ({
          userId: r.user_id,
          fullName: r.full_name,
          profileImageUrl: this.getProfileImageUrl(r.profile_image_key),
        }));
      } catch (err: any) {
        this.logger.warn(`Error en DB listFriends: ${err.message}. Fallback a mock.`);
      }
    }

    // Mock Mode fallback
    const friendUserIds: string[] = [];
    for (const friendship of this.mockFriendships.values()) {
      if (friendship.user_low_id === userId) {
        friendUserIds.push(friendship.user_high_id);
      } else if (friendship.user_high_id === userId) {
        friendUserIds.push(friendship.user_low_id);
      }
    }

    const friends: PublicUserInfo[] = [];
    for (const friendId of friendUserIds) {
      const user = await this.findUserById(friendId);
      if (user) {
        friends.push({
          userId: user.id,
          fullName: user.full_name,
          profileImageUrl: this.getProfileImageUrl(user.profile_image_key),
        });
      }
    }

    friends.sort((a, b) => a.fullName.localeCompare(b.fullName));
    return friends;
  }

  async areFriends(userId1: string, userId2: string): Promise<boolean> {
    if (userId1 === userId2) return false;
    const lowId = userId1 < userId2 ? userId1 : userId2;
    const highId = userId1 < userId2 ? userId2 : userId1;

    if (this.pool && this.isConnected) {
      try {
        const res = await this.pool.query(
          `SELECT 1 FROM friendships WHERE user_low_id = $1 AND user_high_id = $2`,
          [lowId, highId],
        );
        return res.rows.length > 0;
      } catch (err: any) {
        this.logger.warn(`Error en DB areFriends: ${err.message}. Fallback a mock.`);
      }
    }

    return this.mockFriendships.has(`${lowId}:${highId}`);
  }

  async createPost(
    authorId: string,
    imageKey: string,
    description: string | null,
    labels: { name: string; confidence: number; sourceName: string }[],
  ): Promise<PostResponseDto> {
    const author = await this.findUserById(authorId);
    if (!author) {
      throw new NotFoundException({
        code: 'NOT_FOUND',
        message: 'Autor no encontrado en la base de datos.',
      });
    }

    const postId = uuidv4();
    const now = new Date().toISOString();
    const cleanDesc = description && description.trim() !== '' ? description.trim() : null;

    if (this.pool && this.isConnected) {
      const client = await this.pool.connect();
      try {
        await client.query('BEGIN');
        await client.query(
          `INSERT INTO posts (id, author_id, description, image_key, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $5)`,
          [postId, authorId, cleanDesc, imageKey, now],
        );

        for (const label of labels) {
          await client.query(
            `INSERT INTO post_labels (post_id, normalized_label, confidence, source_label, created_at)
             VALUES ($1, $2, $3, $4, $5)
             ON CONFLICT (post_id, normalized_label) DO UPDATE
             SET confidence = EXCLUDED.confidence, source_label = EXCLUDED.source_label`,
            [postId, label.name, label.confidence, label.sourceName, now],
          );
        }

        await client.query('COMMIT');
      } catch (err: any) {
        await client.query('ROLLBACK');
        this.logger.error(`Error en DB createPost: ${err.message}`);
        throw new BadRequestException({
          code: 'VALIDATION_ERROR',
          message: `Error al persistir publicación: ${err.message}`,
        });
      } finally {
        client.release();
      }
    }

    // Mock Mode fallback
    const newPost: DbPost = {
      id: postId,
      author_id: authorId,
      description: cleanDesc,
      image_key: imageKey,
      created_at: now,
      updated_at: now,
    };
    this.mockPosts.set(postId, newPost);
    this.mockPostLabels.set(
      postId,
      labels.map((l) => ({
        post_id: postId,
        normalized_label: l.name,
        source_label: l.sourceName,
        confidence: l.confidence,
        created_at: now,
      })),
    );

    const labelNames = labels.map((l: any) => (typeof l === 'string' ? l : l.name));

    return {
      id: postId,
      postId,
      authorId: author.id,
      author: {
        userId: author.id,
        fullName: author.full_name,
        profileImageUrl: this.getProfileImageUrl(author.profile_image_key),
      },
      imageKey,
      imageUrl: this.getProfileImageUrl(imageKey),
      description: cleanDesc,
      labels: labelNames,
      labelDetails: labels,
      commentsCount: 0,
      createdAt: now,
    } as any;
  }

  async getFeed(
    userId: string,
    options: { limit?: number; cursor?: string; label?: string; q?: string },
  ): Promise<{ items: PostResponseDto[]; posts: PostResponseDto[]; nextCursor: string | null }> {
    const limit = Math.min(Math.max(Number(options.limit) || 10, 1), 50);
    const normalizedLabel = options.label ? options.label.trim().toLowerCase() : undefined;
    const searchFilter = options.q ? options.q.trim().toLowerCase() : undefined;

    if (this.pool && this.isConnected) {
      try {
        const queryParams: any[] = [userId];
        let paramIdx = 2;

        let queryStr = `
          SELECT 
            p.id, p.author_id, p.description, p.image_key, p.created_at,
            u.full_name as author_name, u.profile_image_key as author_image_key,
            (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id AND c.deleted_at IS NULL)::int as comments_count
          FROM posts p
          JOIN users u ON u.id = p.author_id
          WHERE (
            p.author_id = $1 
            OR p.author_id IN (
              SELECT CASE WHEN user_low_id = $1 THEN user_high_id ELSE user_low_id END
              FROM friendships
              WHERE user_low_id = $1 OR user_high_id = $1
            )
          )
        `;

        if (normalizedLabel && normalizedLabel !== 'todos') {
          queryStr += ` AND EXISTS (SELECT 1 FROM post_labels pl WHERE pl.post_id = p.id AND pl.normalized_label = $${paramIdx})`;
          queryParams.push(normalizedLabel);
          paramIdx++;
        }

        if (searchFilter) {
          queryStr += ` AND (p.description ILIKE $${paramIdx} OR EXISTS (SELECT 1 FROM post_labels pl WHERE pl.post_id = p.id AND pl.normalized_label ILIKE $${paramIdx}))`;
          queryParams.push(`%${searchFilter}%`);
          paramIdx++;
        }

        if (options.cursor) {
          queryStr += ` AND p.created_at < $${paramIdx}`;
          queryParams.push(options.cursor);
          paramIdx++;
        }

        queryStr += ` ORDER BY p.created_at DESC LIMIT $${paramIdx}`;
        queryParams.push(limit + 1);

        const res = await this.pool.query(queryStr, queryParams);
        const hasMore = res.rows.length > limit;
        const rows = hasMore ? res.rows.slice(0, limit) : res.rows;
        const nextCursor = hasMore ? rows[rows.length - 1].created_at : null;

        const items: PostResponseDto[] = [];
        for (const row of rows) {
          const labelsRes = await this.pool.query(
            `SELECT normalized_label as name, source_label as "sourceName", confidence FROM post_labels WHERE post_id = $1 ORDER BY confidence DESC`,
            [row.id],
          );

          const rawLabels = labelsRes.rows.map((l: any) => ({
            name: l.name,
            confidence: Number(l.confidence),
            sourceName: l.sourceName,
          }));
          const labelNames = rawLabels.map((l: any) => l.name);

          items.push({
            id: row.id,
            postId: row.id,
            authorId: row.author_id,
            author: {
              userId: row.author_id,
              fullName: row.author_name,
              profileImageUrl: this.getProfileImageUrl(row.author_image_key),
            },
            description: row.description,
            imageKey: row.image_key,
            imageUrl: this.getProfileImageUrl(row.image_key),
            labels: labelNames,
            labelDetails: rawLabels,
            commentsCount: row.comments_count,
            createdAt: row.created_at,
          } as any);
        }

        return { items, posts: items, nextCursor };
      } catch (err: any) {
        this.logger.warn(`Error en DB getFeed: ${err.message}. Fallback a mock.`);
      }
    }

    // Mock Mode fallback
    const visibleAuthorIds = new Set<string>([userId]);
    for (const friendship of this.mockFriendships.values()) {
      if (friendship.user_low_id === userId) {
        visibleAuthorIds.add(friendship.user_high_id);
      } else if (friendship.user_high_id === userId) {
        visibleAuthorIds.add(friendship.user_low_id);
      }
    }

    let candidatePosts: DbPost[] = [];
    for (const post of this.mockPosts.values()) {
      if (!visibleAuthorIds.has(post.author_id)) {
        continue;
      }

      const postLabels = this.mockPostLabels.get(post.id) || [];

      if (normalizedLabel && normalizedLabel !== 'todos') {
        const hasLabel = postLabels.some(
          (l) => l.normalized_label.toLowerCase() === normalizedLabel,
        );
        if (!hasLabel) continue;
      }

      if (searchFilter) {
        const matchesDesc = post.description
          ? post.description.toLowerCase().includes(searchFilter)
          : false;
        const matchesLabel = postLabels.some((l) =>
          l.normalized_label.toLowerCase().includes(searchFilter),
        );
        if (!matchesDesc && !matchesLabel) continue;
      }

      if (options.cursor) {
        if (new Date(post.created_at) >= new Date(options.cursor)) {
          continue;
        }
      }

      candidatePosts.push(post);
    }

    candidatePosts.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );

    const hasMore = candidatePosts.length > limit;
    const paged = hasMore ? candidatePosts.slice(0, limit) : candidatePosts;
    const nextCursor = hasMore && paged.length > 0 ? paged[paged.length - 1].created_at : null;

    const items: PostResponseDto[] = [];
    for (const p of paged) {
      const author = await this.findUserById(p.author_id);
      const postLabels = this.mockPostLabels.get(p.id) || [];
      const commentsCount = Array.from(this.mockComments.values()).filter(
        (c) => c.post_id === p.id && !c.deleted_at,
      ).length;

      const rawLabels = postLabels.map((l) => ({
        name: l.normalized_label,
        confidence: Number(l.confidence),
        sourceName: l.source_label,
      }));
      const labelNames = rawLabels.map((l) => l.name);

      items.push({
        id: p.id,
        postId: p.id,
        authorId: p.author_id,
        author: {
          userId: author?.id || p.author_id,
          fullName: author?.full_name || 'Usuario Semi-Social',
          profileImageUrl: this.getProfileImageUrl(author?.profile_image_key || null),
        },
        description: p.description,
        imageKey: p.image_key,
        imageUrl: this.getProfileImageUrl(p.image_key),
        labels: labelNames,
        labelDetails: rawLabels,
        commentsCount,
        createdAt: p.created_at,
      } as any);
    }

    return { items, posts: items, nextCursor };
  }

  async getLabels(q?: string): Promise<{ name: string; postCount: number; count: number }[]> {
    const search = q ? q.trim().toLowerCase() : undefined;

    if (this.pool && this.isConnected) {
      try {
        let queryStr = `
          SELECT normalized_label as name, COUNT(DISTINCT post_id)::int as post_count
          FROM post_labels
        `;
        const params: any[] = [];
        if (search) {
          queryStr += ` WHERE normalized_label ILIKE $1`;
          params.push(`%${search}%`);
        }
        queryStr += ` GROUP BY normalized_label ORDER BY post_count DESC, normalized_label ASC`;

        const res = await this.pool.query(queryStr, params);
        const countAll = await this.pool.query(`SELECT COUNT(*)::int as count FROM posts`);
        const totalPosts = countAll.rows[0]?.count || 0;

        const list = res.rows.map((r) => ({
          name: r.name,
          postCount: r.post_count,
          count: r.post_count,
        }));

        if (!search || 'todos'.includes(search)) {
          list.unshift({ name: 'Todos', postCount: totalPosts, count: totalPosts });
        }

        return list;
      } catch (err: any) {
        this.logger.warn(`Error en DB getLabels: ${err.message}. Fallback a mock.`);
      }
    }

    // Mock Mode fallback
    const counts = new Map<string, Set<string>>();
    for (const [postId, labels] of this.mockPostLabels.entries()) {
      for (const l of labels) {
        const norm = l.normalized_label.toLowerCase();
        if (search && !norm.includes(search)) continue;
        if (!counts.has(norm)) counts.set(norm, new Set());
        counts.get(norm)!.add(postId);
      }
    }

    const list: { name: string; postCount: number; count: number }[] = [];
    for (const [name, posts] of counts.entries()) {
      list.push({ name, postCount: posts.size, count: posts.size });
    }
    list.sort((a, b) => b.postCount - a.postCount || a.name.localeCompare(b.name));

    const totalPosts = this.mockPosts.size;
    if (!search || 'todos'.includes(search)) {
      list.unshift({ name: 'Todos', postCount: totalPosts, count: totalPosts });
    }

    return list;
  }

  async getPostById(postId: string): Promise<DbPost | null> {
    if (this.pool && this.isConnected) {
      try {
        const res = await this.pool.query(`SELECT * FROM posts WHERE id = $1`, [postId]);
        if (res.rows.length > 0) return res.rows[0];
      } catch (err: any) {
        this.logger.warn(`Error en DB getPostById: ${err.message}. Fallback a mock.`);
      }
    }
    return this.mockPosts.get(postId) || null;
  }

  async canUserAccessPost(userId: string, postId: string): Promise<boolean> {
    const post = await this.getPostById(postId);
    if (!post) {
      throw new NotFoundException({
        code: 'NOT_FOUND',
        message: 'Publicación no encontrada.',
      });
    }

    if (post.author_id === userId) return true;
    const areFriends = await this.areFriends(userId, post.author_id);
    if (!areFriends) {
      throw new ForbiddenException({
        code: 'FORBIDDEN',
        message: 'No tienes permiso para ver o interactuar con esta publicación (no son amigos).',
      });
    }

    return true;
  }

  async createComment(
    postId: string,
    authorId: string,
    content: string,
  ): Promise<CommentResponseDto> {
    await this.canUserAccessPost(authorId, postId);

    const author = await this.findUserById(authorId);
    if (!author) {
      throw new NotFoundException({
        code: 'NOT_FOUND',
        message: 'Autor del comentario no encontrado.',
      });
    }

    const cleanContent = (content || '').trim();
    if (!cleanContent) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'El contenido del comentario no puede estar vacío.',
      });
    }

    const commentId = uuidv4();
    const now = new Date().toISOString();

    if (this.pool && this.isConnected) {
      try {
        await this.pool.query(
          `INSERT INTO comments (id, post_id, author_id, content, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $5)`,
          [commentId, postId, authorId, cleanContent, now],
        );
      } catch (err: any) {
        this.logger.error(`Error en DB createComment: ${err.message}`);
        throw new BadRequestException({
          code: 'VALIDATION_ERROR',
          message: `Error al persistir comentario: ${err.message}`,
        });
      }
    }

    const comment: DbComment = {
      id: commentId,
      post_id: postId,
      author_id: authorId,
      content: cleanContent,
      created_at: now,
      updated_at: now,
      deleted_at: null,
    };
    this.mockComments.set(commentId, comment);

    return {
      commentId,
      id: commentId,
      postId,
      author: {
        userId: author.id,
        fullName: author.full_name,
        profileImageUrl: this.getProfileImageUrl(author.profile_image_key),
      },
      body: cleanContent,
      content: cleanContent,
      createdAt: now,
    };
  }

  async getComments(postId: string, userId: string): Promise<CommentResponseDto[]> {
    await this.canUserAccessPost(userId, postId);

    if (this.pool && this.isConnected) {
      try {
        const res = await this.pool.query(
          `SELECT c.id, c.post_id, c.author_id, c.content, c.created_at,
                  u.full_name as author_name, u.profile_image_key as author_image_key
           FROM comments c
           JOIN users u ON u.id = c.author_id
           WHERE c.post_id = $1 AND c.deleted_at IS NULL
           ORDER BY c.created_at ASC`,
          [postId],
        );

        return res.rows.map((r) => ({
          commentId: r.id,
          id: r.id,
          postId: r.post_id,
          author: {
            userId: r.author_id,
            fullName: r.author_name,
            profileImageUrl: this.getProfileImageUrl(r.author_image_key),
          },
          body: r.content,
          content: r.content,
          createdAt: r.created_at,
        }));
      } catch (err: any) {
        this.logger.warn(`Error en DB getComments: ${err.message}. Fallback a mock.`);
      }
    }

    // Mock Mode fallback
    const commentsList = Array.from(this.mockComments.values())
      .filter((c) => c.post_id === postId && !c.deleted_at)
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

    const result: CommentResponseDto[] = [];
    for (const c of commentsList) {
      const author = await this.findUserById(c.author_id);
      result.push({
        commentId: c.id,
        id: c.id,
        postId: c.post_id,
        author: {
          userId: author?.id || c.author_id,
          fullName: author?.full_name || 'Usuario Semi-Social',
          profileImageUrl: this.getProfileImageUrl(author?.profile_image_key || null),
        },
        body: c.content,
        content: c.content,
        createdAt: c.created_at,
      });
    }

    return result;
  }

  async query(text: string, params?: any[]): Promise<QueryResult<any>> {
    if (this.pool && this.isConnected) {
      return this.pool.query(text, params);
    }
    this.logger.debug(`[MOCK QUERY] ${text}`);
    return {
      rows: [],
      command: 'SELECT',
      rowCount: 0,
      oid: 0,
      fields: [],
    };
  }

  getPool(): Pool | null {
    return this.pool;
  }

  isDbConnected(): boolean {
    return this.isConnected;
  }

  async saveMessage(
    senderId: string,
    recipientId: string,
    content: string,
    clientMessageId?: string,
  ): Promise<MessageDtoResponse> {
    if (senderId === recipientId) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'No puedes enviarte un mensaje a ti mismo.',
      });
    }

    const trimmed = (content || '').trim();
    if (!trimmed || trimmed.length > 4000) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'El contenido del mensaje debe tener entre 1 y 4000 caracteres.',
      });
    }

    const areTheyFriends = await this.areFriends(senderId, recipientId);
    if (!areTheyFriends) {
      throw new ForbiddenException({
        code: 'FORBIDDEN',
        message: 'Solo amigos confirmados pueden enviarse mensajes.',
      });
    }

    const newId = uuidv4();
    const now = new Date().toISOString();

    const payload: ChatNotificationPayload = {
      messageId: newId,
      clientMessageId,
      senderId,
      recipientId,
      body: trimmed,
      createdAt: now,
    };

    if (this.pool && this.isConnected) {
      try {
        const res = await this.pool.query(
          `INSERT INTO messages (id, sender_id, recipient_id, content, created_at)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING id, sender_id, recipient_id, content, created_at, read_at`,
          [newId, senderId, recipientId, trimmed, now],
        );

        try {
          await this.pool.query(
            `SELECT pg_notify('chat_messages', $1)`,
            [JSON.stringify(payload)],
          );
        } catch (notifyErr: any) {
          this.logger.warn(`Error al emitir pg_notify: ${notifyErr.message}`);
        }

        const row = res.rows[0];
        return {
          messageId: row.id,
          senderId: row.sender_id,
          recipientId: row.recipient_id,
          body: row.content,
          createdAt: row.created_at,
          readAt: row.read_at,
        };
      } catch (err: any) {
        if (err instanceof BadRequestException || err instanceof ForbiddenException) {
          throw err;
        }
        this.logger.warn(`Error en DB saveMessage: ${err.message}. Fallback a mock.`);
      }
    }

    // Mock Mode fallback
    const msg: DbMessage = {
      id: newId,
      sender_id: senderId,
      recipient_id: recipientId,
      content: trimmed,
      created_at: now,
      read_at: null,
    };
    this.mockMessages.set(newId, msg);
    this.chatEvents.emit('chat_messages', payload);

    return {
      messageId: newId,
      senderId,
      recipientId,
      body: trimmed,
      createdAt: now,
      readAt: null,
    };
  }

  async getConversationMessages(
    userId: string,
    friendId: string,
    cursor?: string,
    limit: number = 50,
  ): Promise<{ items: MessageDtoResponse[]; nextCursor: string | null }> {
    const friend = await this.findUserById(friendId);
    if (!friend) {
      throw new NotFoundException({
        code: 'NOT_FOUND',
        message: 'El usuario destinatario no existe.',
      });
    }

    const areTheyFriends = await this.areFriends(userId, friendId);
    if (!areTheyFriends) {
      throw new ForbiddenException({
        code: 'FORBIDDEN',
        message: 'Solo amigos confirmados pueden consultar el historial de chat.',
      });
    }

    const safeLimit = Math.min(Math.max(Number(limit) || 50, 1), 50);

    if (this.pool && this.isConnected) {
      try {
        let queryStr = `
          SELECT id, sender_id, recipient_id, content, created_at, read_at
          FROM messages
          WHERE ((sender_id = $1 AND recipient_id = $2) OR (sender_id = $2 AND recipient_id = $1))
        `;
        const params: any[] = [userId, friendId];

        if (cursor) {
          params.push(cursor);
          queryStr += ` AND created_at < $${params.length}`;
        }

        queryStr += ` ORDER BY created_at DESC LIMIT $${params.length + 1}`;
        params.push(safeLimit + 1);

        const res = await this.pool.query(queryStr, params);
        const hasMore = res.rows.length > safeLimit;
        const rows = hasMore ? res.rows.slice(0, safeLimit) : res.rows;

        const items: MessageDtoResponse[] = rows.map((r) => ({
          messageId: r.id,
          senderId: r.sender_id,
          recipientId: r.recipient_id,
          body: r.content,
          createdAt: r.created_at,
          readAt: r.read_at,
        }));

        items.reverse();

        const nextCursor = hasMore && rows.length > 0 ? rows[rows.length - 1].created_at : null;

        return { items, nextCursor };
      } catch (err: any) {
        if (err instanceof ForbiddenException || err instanceof NotFoundException) {
          throw err;
        }
        this.logger.warn(`Error en DB getConversationMessages: ${err.message}. Fallback a mock.`);
      }
    }

    // Mock Mode fallback
    let messagesList = Array.from(this.mockMessages.values())
      .filter(
        (m) =>
          (m.sender_id === userId && m.recipient_id === friendId) ||
          (m.sender_id === friendId && m.recipient_id === userId),
      )
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    if (cursor) {
      const cursorTime = new Date(cursor).getTime();
      messagesList = messagesList.filter(
        (m) => new Date(m.created_at).getTime() < cursorTime,
      );
    }

    const hasMore = messagesList.length > safeLimit;
    const rows = hasMore ? messagesList.slice(0, safeLimit) : messagesList;

    const items: MessageDtoResponse[] = rows.map((m) => ({
      messageId: m.id,
      senderId: m.sender_id,
      recipientId: m.recipient_id,
      body: m.content,
      createdAt: m.created_at,
      readAt: m.read_at,
    }));

    items.reverse();

    const nextCursor = hasMore && rows.length > 0 ? rows[rows.length - 1].created_at : null;

    return { items, nextCursor };
  }
}
