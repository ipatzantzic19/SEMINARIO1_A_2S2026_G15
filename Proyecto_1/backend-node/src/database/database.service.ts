import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool, QueryResult } from 'pg';

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

@Injectable()
export class DatabaseService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger('DatabaseService');
  private pool: Pool | null = null;
  private isConnected = false;

  // Almacenamiento en memoria para desarrollo local / mock mode
  private mockUsers = new Map<string, DbUser>();
  private mockSessions = new Map<string, { cognitoSub: string; email: string }>();

  constructor(private configService: ConfigService) {
    // Usuario mock por defecto para pruebas (inicia con perfil incompleto para validar flujo de foto obligatoria)
    const defaultUser: DbUser = {
      id: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
      cognito_sub: 'c09a8123-1122-3344-5566-778899aabbcc',
      email: 'daniel.ortiz@ingenieria.usac.edu.gt',
      full_name: 'Daniel Abraham Ortiz',
      dpi: '1234567890101',
      profile_image_key: null,
      face_reference_key: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    this.mockUsers.set(defaultUser.cognito_sub, defaultUser);
    this.mockUsers.set(defaultUser.email.toLowerCase(), defaultUser);
  }

  saveMockSession(token: string, session: { cognitoSub: string; email: string }) {
    this.mockSessions.set(token, session);
  }

  getMockSession(token: string): { cognitoSub: string; email: string } | undefined {
    return this.mockSessions.get(token);
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

    this.mockUsers.set(newUser.cognito_sub, newUser);
    this.mockUsers.set(newUser.email, newUser);
    return newUser;
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
    return user;
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
