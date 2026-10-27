import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Client } from 'pg';
import { DatabaseService, ChatNotificationPayload } from '../../database/database.service';

export type ChatMessageNotificationHandler = (payload: ChatNotificationPayload) => void;

@Injectable()
export class ChatSubscriberService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger('ChatSubscriberService');
  private listenerClient: Client | null = null;
  private isDestroyed = false;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private readonly handlers = new Set<ChatMessageNotificationHandler>();

  constructor(
    private readonly configService: ConfigService,
    private readonly databaseService: DatabaseService,
  ) {}

  onNotification(handler: ChatMessageNotificationHandler): () => void {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  private dispatchNotification(payload: ChatNotificationPayload) {
    for (const handler of this.handlers) {
      try {
        handler(payload);
      } catch (err: any) {
        this.logger.error(`Error en handler de notificación de chat: ${err.message}`, err.stack);
      }
    }
  }

  async onModuleInit() {
    // 1. Escuchar eventos en memoria del DatabaseService (para mock mode o pruebas locales)
    this.databaseService.chatEvents.on('chat_messages', (payload: ChatNotificationPayload) => {
      this.dispatchNotification(payload);
    });

    // 2. Conectar a PostgreSQL para LISTEN / NOTIFY real si no es mockMode
    const mockMode = this.configService.get<boolean>('mockMode');
    if (!mockMode) {
      await this.initPostgresListener();
    } else {
      this.logger.log('ChatSubscriberService operando en Mock Mode (escucha vía EventEmitter local).');
    }
  }

  private async initPostgresListener() {
    if (this.isDestroyed) return;

    const rds = this.configService.get('rds') as any;
    if (!rds?.host) {
      this.logger.warn('Configuración RDS no encontrada. Usando suscriptor local en memoria.');
      return;
    }

    try {
      this.listenerClient = new Client({
        host: rds.host,
        port: rds.port,
        database: rds.database,
        user: rds.user,
        password: rds.password,
        ssl:
          rds.sslMode === 'require' || rds.sslMode === 'verify-full'
            ? { rejectUnauthorized: false }
            : undefined,
      });

      this.listenerClient.on('notification', (msg) => {
        if (msg.channel === 'chat_messages' && msg.payload) {
          try {
            const payload: ChatNotificationPayload = JSON.parse(msg.payload);
            this.dispatchNotification(payload);
          } catch (parseErr: any) {
            this.logger.error(`Error al parsear payload de notificación Postgres: ${parseErr.message}`);
          }
        }
      });

      this.listenerClient.on('error', (err) => {
        this.logger.warn(`Error en conexión LISTEN de PostgreSQL: ${err.message}`);
        this.scheduleReconnect();
      });

      this.listenerClient.on('end', () => {
        this.logger.warn('Conexión LISTEN de PostgreSQL finalizada.');
        this.scheduleReconnect();
      });

      await this.listenerClient.connect();
      await this.listenerClient.query('LISTEN chat_messages');
      this.logger.log('Suscrito exitosamente a canal de PostgreSQL: LISTEN chat_messages');
    } catch (err: any) {
      this.logger.warn(`No se pudo iniciar LISTEN chat_messages en PostgreSQL: ${err.message}`);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.isDestroyed || this.reconnectTimeout) return;
    this.reconnectTimeout = setTimeout(async () => {
      this.reconnectTimeout = null;
      if (this.listenerClient) {
        try {
          await this.listenerClient.end();
        } catch {
          // Ignorar error al cerrar
        }
        this.listenerClient = null;
      }
      await this.initPostgresListener();
    }, 5000);
  }

  async onModuleDestroy() {
    this.isDestroyed = true;
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.listenerClient) {
      try {
        await this.listenerClient.query('UNLISTEN chat_messages');
        await this.listenerClient.end();
      } catch {
        // Ignorar
      }
      this.listenerClient = null;
    }
    this.handlers.clear();
  }
}
