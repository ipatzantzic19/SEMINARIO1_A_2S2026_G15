import {
  Injectable,
  OnModuleInit,
  OnModuleDestroy,
  Logger,
} from '@nestjs/common';
import { HttpAdapterHost } from '@nestjs/core';
import { ConfigService } from '@nestjs/config';
import { WebSocketServer, WebSocket } from 'ws';
import { CognitoJwtVerifier } from 'aws-jwt-verify';
import {
  DatabaseService,
  ChatNotificationPayload,
} from '../../database/database.service';
import { ChatSubscriberService } from './chat-subscriber.service';

interface ClientSession {
  socket: WebSocket;
  userId: string;
  friendId: string;
}

@Injectable()
export class ChatGateway implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger('ChatGateway');
  private wss: WebSocketServer | null = null;
  private jwtVerifier: any = null;
  private readonly sessions = new Map<string, Set<ClientSession>>(); // key: userId
  private pingInterval: NodeJS.Timeout | null = null;

  constructor(
    private readonly httpAdapterHost: HttpAdapterHost,
    private readonly configService: ConfigService,
    private readonly databaseService: DatabaseService,
    private readonly subscriberService: ChatSubscriberService,
  ) {
    const userPoolId =
      this.configService.get<string>('cognito.userPoolId') || 'us-east-1_4UrrCPt8Z';
    const clientId =
      this.configService.get<string>('cognito.appClientId') || '1feavcj8qvobr4ltshlgnolg5f';
    const mockMode = this.configService.get<boolean>('mockMode') || false;

    if (!mockMode) {
      try {
        this.jwtVerifier = CognitoJwtVerifier.create({
          userPoolId,
          tokenUse: 'access',
          clientId,
        });
      } catch (err: any) {
        this.logger.warn(
          `No se pudo inicializar CognitoJwtVerifier en ChatGateway: ${err.message}. Modo fallback activado.`,
        );
      }
    }
  }

  onModuleInit() {
    const server = this.httpAdapterHost.httpAdapter?.getHttpServer();
    if (!server) {
      this.logger.warn('Servidor HTTP no disponible para montar WebSockets.');
      return;
    }

    this.wss = new WebSocketServer({ noServer: true });

    server.on('upgrade', (request: any, socket: any, head: any) => {
      try {
        const urlObj = new URL(request.url || '', 'http://localhost');
        const pathname = urlObj.pathname;

        if (pathname === '/ws/chat' || pathname === '/api/v1/chat/ws') {
          this.wss!.handleUpgrade(request, socket, head, (ws) => {
            this.wss!.emit('connection', ws, request);
          });
        }
      } catch (err: any) {
        this.logger.error(`Error en upgrade de WebSocket: ${err.message}`);
        socket.destroy();
      }
    });

    this.wss.on('connection', (ws: WebSocket, req: any) => {
      this.handleConnection(ws, req);
    });

    // Suscribirse a la difusión de Postgres (LISTEN / NOTIFY o EventEmitter)
    this.subscriberService.onNotification((payload) => {
      this.handleNotification(payload);
    });

    // Heartbeat periódico a nivel servidor cada 30 segundos
    this.pingInterval = setInterval(() => {
      for (const userSessions of this.sessions.values()) {
        for (const session of userSessions) {
          if (session.socket.readyState === WebSocket.OPEN) {
            session.socket.ping();
          }
        }
      }
    }, 30000);

    this.logger.log('ChatGateway inicializado en rutas: /ws/chat y /api/v1/chat/ws');
  }

  private async authenticate(token: string): Promise<{
    userId: string;
    profileComplete: boolean;
  } | null> {
    const mockMode = this.configService.get<boolean>('mockMode');
    let cognitoSub = 'c09a8123-1122-3344-5566-778899aabbcc';

    if (mockMode || !this.jwtVerifier) {
      const session = this.databaseService.getMockSession(token);
      if (session) {
        cognitoSub = session.cognitoSub;
      } else if (token.startsWith('mock-') || token.startsWith('token-')) {
        const sub = token.replace('token-', 'sub-');
        const dbUser = await this.databaseService.findUserByCognitoSub(sub);
        if (dbUser) {
          cognitoSub = dbUser.cognito_sub;
        }
      } else {
        try {
          const parts = token.split('.');
          if (parts.length === 3) {
            const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf8'));
            cognitoSub = payload.sub || cognitoSub;
          }
        } catch {
          // Token no parseable
        }
      }
    } else {
      try {
        const payload = await this.jwtVerifier.verify(token);
        cognitoSub = payload.sub;
      } catch (err: any) {
        this.logger.warn(`Handshake WebSocket rechazada: Token Cognito inválido (${err.message})`);
        return null;
      }
    }

    const dbUser = await this.databaseService.findUserByCognitoSub(cognitoSub);
    if (!dbUser) {
      return null;
    }

    return {
      userId: dbUser.id,
      profileComplete: Boolean(dbUser.profile_image_key),
    };
  }

  private async handleConnection(ws: WebSocket, req: any) {
    try {
      const urlObj = new URL(req.url || '', 'http://localhost');
      const token = urlObj.searchParams.get('token');
      const friendId = urlObj.searchParams.get('friendId');

      if (!token) {
        ws.close(4401, 'Unauthorized: token is required');
        return;
      }

      if (!friendId) {
        ws.close(4400, 'Bad Request: friendId is required');
        return;
      }

      const auth = await this.authenticate(token);
      if (!auth) {
        ws.close(4401, 'Unauthorized: invalid token');
        return;
      }

      if (!auth.profileComplete) {
        ws.close(4403, 'Forbidden: PROFILE_INCOMPLETE');
        return;
      }

      // Validar si son amigos
      const areFriends = await this.databaseService.areFriends(auth.userId, friendId);
      if (!areFriends) {
        ws.close(4403, 'Forbidden: NOT_FRIENDS');
        return;
      }

      const session: ClientSession = {
        socket: ws,
        userId: auth.userId,
        friendId,
      };

      if (!this.sessions.has(auth.userId)) {
        this.sessions.set(auth.userId, new Set());
      }
      this.sessions.get(auth.userId)!.add(session);

      this.logger.log(`WebSocket conectado: Usuario ${auth.userId} conversando con ${friendId}`);

      // Enviar evento inicial de conexión
      this.send(ws, {
        event: 'connected',
        data: {
          userId: auth.userId,
          friendId,
        },
      });

      ws.on('message', async (raw: string | Buffer) => {
        await this.handleClientMessage(session, raw.toString());
      });

      ws.on('close', () => {
        this.removeSession(session);
      });

      ws.on('error', (err) => {
        this.logger.warn(`Error en socket usuario ${auth.userId}: ${err.message}`);
        this.removeSession(session);
      });
    } catch (err: any) {
      this.logger.error(`Error en handshake WebSocket: ${err.message}`, err.stack);
      ws.close(1011, 'Internal Error');
    }
  }

  private async handleClientMessage(session: ClientSession, rawText: string) {
    let payload: any;
    try {
      payload = JSON.parse(rawText);
    } catch {
      this.send(session.socket, {
        event: 'error',
        data: {
          code: 'VALIDATION_ERROR',
          message: 'El frame transmitido debe ser un JSON válido.',
        },
      });
      return;
    }

    const { event, data } = payload || {};

    if (event === 'ping') {
      this.send(session.socket, { event: 'pong' });
      return;
    }

    if (event === 'message:send') {
      const { clientMessageId, recipientId, body } = data || {};

      if (!recipientId || recipientId !== session.friendId) {
        this.send(session.socket, {
          event: 'error',
          data: {
            code: 'VALIDATION_ERROR',
            message: 'El recipientId debe coincidir con la conversación activa.',
            clientMessageId,
          },
        });
        return;
      }

      const trimmedBody = (body || '').trim();
      if (!trimmedBody || trimmedBody.length > 4000) {
        this.send(session.socket, {
          event: 'error',
          data: {
            code: 'VALIDATION_ERROR',
            message: 'El mensaje debe contener entre 1 y 4000 caracteres.',
            clientMessageId,
          },
        });
        return;
      }

      try {
        await this.databaseService.saveMessage(
          session.userId,
          recipientId,
          trimmedBody,
          clientMessageId,
        );
        // La notificación se propaga vía ChatSubscriberService (pg_notify o eventEmitter)
      } catch (err: any) {
        this.logger.error(`Error al persistir mensaje: ${err.message}`);
        this.send(session.socket, {
          event: 'error',
          data: {
            code: err.response?.code || 'INTERNAL_ERROR',
            message: err.response?.message || 'Error al persistir el mensaje.',
            clientMessageId,
          },
        });
      }
      return;
    }

    this.logger.warn(`Evento no reconocido recibido en WebSocket: ${event}`);
  }

  private handleNotification(payload: ChatNotificationPayload) {
    const { messageId, clientMessageId, senderId, recipientId, body, createdAt } = payload;

    // 1. Confirmar al emisor (message:ack) si está conectado en esta instancia
    const senderSessions = this.sessions.get(senderId);
    if (senderSessions) {
      for (const session of senderSessions) {
        if (session.friendId === recipientId && session.socket.readyState === WebSocket.OPEN) {
          this.send(session.socket, {
            event: 'message:ack',
            data: {
              clientMessageId,
              messageId,
              senderId,
              recipientId,
              body,
              createdAt,
            },
          });
        }
      }
    }

    // 2. Entregar al receptor (message:new) si está conectado en esta instancia
    const recipientSessions = this.sessions.get(recipientId);
    if (recipientSessions) {
      for (const session of recipientSessions) {
        if (session.friendId === senderId && session.socket.readyState === WebSocket.OPEN) {
          this.send(session.socket, {
            event: 'message:new',
            data: {
              messageId,
              senderId,
              recipientId,
              body,
              createdAt,
              readAt: null,
            },
          });
        }
      }
    }
  }

  private send(socket: WebSocket, message: any) {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
    }
  }

  private removeSession(session: ClientSession) {
    const userSessions = this.sessions.get(session.userId);
    if (userSessions) {
      userSessions.delete(session);
      if (userSessions.size === 0) {
        this.sessions.delete(session.userId);
      }
    }
  }

  onModuleDestroy() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.wss) {
      this.wss.close();
      this.wss = null;
    }
    this.sessions.clear();
  }
}
