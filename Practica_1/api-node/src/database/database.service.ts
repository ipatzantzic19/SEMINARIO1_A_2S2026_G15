import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool, PoolClient, QueryResult, QueryResultRow } from 'pg';
import * as fs from 'fs';

@Injectable()
export class DatabaseService implements OnModuleInit, OnModuleDestroy {
  private pool: Pool;
  private readonly logger = new Logger(DatabaseService.name);
  private isDbReachable = false;

  constructor(private configService: ConfigService) { }

  onModuleInit() {
    const host = this.configService.get<string>('database.host');
    const port = this.configService.get<number>('database.port');
    const database = this.configService.get<string>('database.name');
    const user = this.configService.get<string>('database.user');
    const password = this.configService.get<string>('database.password');
    const sslMode = this.configService.get<string>('database.sslMode');
    const caPath = this.configService.get<string>('database.caPath');

    let sslConfig: any = false;

    if (sslMode === 'verify-full' || sslMode === 'verify-ca' || sslMode === 'require') {
      sslConfig = {
        rejectUnauthorized: sslMode === 'verify-full',
      };

      if (caPath) {
        try {
          if (fs.existsSync(caPath)) {
            sslConfig.ca = fs.readFileSync(caPath).toString();
            this.logger.log(`SSL CA Certificate loaded successfully from: ${caPath}`);
          } else {
            this.logger.warn(
              `SSL CA Certificate not found at path: ${caPath}. Falling back to rejectUnauthorized: false for local connection stability.`,
            );
            sslConfig.rejectUnauthorized = false;
          }
        } catch (error) {
          this.logger.error(
            `Error reading SSL CA Certificate from ${caPath}: ${error.message}. Falling back to rejectUnauthorized: false.`,
          );
          sslConfig.rejectUnauthorized = false;
        }
      } else {
        this.logger.warn(`SSL mode is "${sslMode}" but BD_CERTIFICADO_CA is not specified. Connecting with rejectUnauthorized: false.`);
        sslConfig.rejectUnauthorized = false;
      }
    }

    this.logger.log(`Initializing database pool for host ${host}:${port}, database "${database}", user "${user}"`);

    this.pool = new Pool({
      host,
      port,
      database,
      user,
      password,
      ssl: sslConfig,
      max: 10, // número máximo de clientes en el grupo
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });

    // Probar conexión
    this.pool.query('SELECT NOW()', (err, res) => {
      if (err) {
        this.logger.error(`Database connection failed: ${err.message}`);
        this.isDbReachable = false;
      } else {
        this.logger.log(`Database connected successfully. Server time: ${res.rows[0].now}`);
        this.isDbReachable = true;
      }
    });
  }

  get isReachable(): boolean {
    return this.isDbReachable;
  }

  async onModuleDestroy() {
    if (this.pool) {
      this.logger.log('Closing database pool...');
      await this.pool.end();
    }
  }

  async query<T extends QueryResultRow = any>(text: string, params?: any[]): Promise<QueryResult<T>> {
    const start = Date.now();
    try {
      const res = await this.pool.query<T>(text, params);
      const duration = Date.now() - start;
      this.logger.verbose(`Executed query: ${text} | Duration: ${duration}ms | Rows: ${res.rowCount}`);
      return res;
    } catch (error) {
      this.logger.error(`Query failed: ${text} | Error: ${error.message}`);
      throw error;
    }
  }

  async getClient(): Promise<PoolClient> {
    return await this.pool.connect();
  }
}
