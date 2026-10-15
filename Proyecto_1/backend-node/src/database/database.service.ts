import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool, QueryResult } from 'pg';

@Injectable()
export class DatabaseService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger('DatabaseService');
  private pool: Pool | null = null;
  private isConnected = false;

  constructor(private configService: ConfigService) {}

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
      this.logger.warn(`No se pudo conectar a PostgreSQL en ${rds?.host}: ${err.message}. El servidor iniciará, pero las consultas reales fallarán.`);
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

  async query(text: string, params?: any[]): Promise<QueryResult<any>> {
    const mockMode = this.configService.get<boolean>('mockMode');
    if (mockMode || !this.pool) {
      this.logger.debug(`[MOCK QUERY] ${text}`);
      return {
        rows: [],
        command: 'SELECT',
        rowCount: 0,
        oid: 0,
        fields: [],
      };
    }
    return this.pool.query(text, params);
  }
}
