import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool, PoolClient, QueryResult, QueryResultRow } from 'pg';
import * as fs from 'fs';

@Injectable()
export class DatabaseService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(DatabaseService.name);
  private pool: Pool;

  constructor(private configService: ConfigService) {}

  onModuleInit() {
    const dbConfig = this.configService.get('database');
    const sslMode = dbConfig.sslMode;

    let ssl: any = false;
    if (sslMode === 'require' || sslMode === 'verify-full' || sslMode === 'verify-ca') {
      ssl = {
        rejectUnauthorized: sslMode === 'verify-full',
      };
      if (dbConfig.sslRootCert && fs.existsSync(dbConfig.sslRootCert)) {
        ssl.ca = fs.readFileSync(dbConfig.sslRootCert).toString();
      }
    }

    this.pool = new Pool({
      host: dbConfig.host,
      port: dbConfig.port,
      database: dbConfig.name,
      user: dbConfig.user,
      password: dbConfig.password,
      ssl,
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });

    this.logger.log(`Conexión a PostgreSQL configurada (${dbConfig.host}:${dbConfig.port}/${dbConfig.name})`);
  }

  async onModuleDestroy() {
    if (this.pool) {
      await this.pool.end();
      this.logger.log('Pool de conexiones PostgreSQL cerrado.');
    }
  }

  async query<T extends QueryResultRow = any>(text: string, params?: any[]): Promise<QueryResult<T>> {
    return this.pool.query<T>(text, params);
  }

  async getClient(): Promise<PoolClient> {
    return this.pool.connect();
  }

  async verificarConexion(timeoutMs: number = 2000): Promise<boolean> {
    try {
      const clientPromise = this.pool.connect();
      const timeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('Timeout de conexión BD')), timeoutMs),
      );

      const client = await Promise.race([clientPromise, timeoutPromise]);
      try {
        await client.query('SELECT 1;');
        return true;
      } finally {
        client.release();
      }
    } catch (err) {
      this.logger.error(`Error verificando salud de base de datos: ${err.message}`);
      return false;
    }
  }
}
