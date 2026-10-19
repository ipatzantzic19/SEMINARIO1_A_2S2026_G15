import {
  Injectable,
  OnModuleInit,
  OnModuleDestroy,
  Logger,
  BadRequestException,
  ConflictException,
  NotFoundException,
  ForbiddenException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool, QueryResult } from 'pg';
import { v4 as uuidv4 } from 'uuid';

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
      this.logger.warn(
        `No se pudo conectar a PostgreSQL en ${rds?.host}: ${err.message}. El servidor usará fallback en memoria para no bloquearse.`,
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
      return true; // En desarrollo no bloquea si usa fallback
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

    if (this.pool && this.isConnected) {
      try {
        await this.pool.query(
          `INSERT INTO users (id, cognito_sub, email, full_name, dpi, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7)`,
          [newUser.id, newUser.cognito_sub, newUser.email, newUser.full_name, newUser.dpi, now, now],
        );
      } catch (err: any) {
        this.logger.warn(`Error en DB query createUser: ${err.message}. Guardando en memoria.`);
      }
    }

    this.mockUsers.set(newUser.id, newUser);
    this.mockUsers.set(newUser.cognito_sub, newUser);
    this.mockUsers.set(newUser.email, newUser);
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
    user.face_reference_key = faceReferenceKey || `Fotos_Perfil/references/${cognitoSub}/reference.jpg`;
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

  async updateProfile(cognitoSub: string, updates: { fullName?: string; dpi?: string; profileImageKey?: string }): Promise<DbUser | null> {
    const now = new Date().toISOString();
    const user = await this.findUserByCognitoSub(cognitoSub);
    if (!user) return null;

    if (updates.fullName) user.full_name = updates.fullName;
    if (updates.dpi) user.dpi = updates.dpi;
    if (updates.profileImageKey) user.profile_image_key = updates.profileImageKey;
    user.updated_at = now;

    if (this.pool && this.isConnected) {
      try {
        await this.pool.query(
          `UPDATE users SET full_name = $1, dpi = $2, profile_image_key = $3, updated_at = $4 WHERE cognito_sub = $5`,
          [user.full_name, user.dpi, user.profile_image_key, now, cognitoSub],
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
}

