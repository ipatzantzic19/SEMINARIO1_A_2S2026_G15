import {
  Injectable,
  Logger,
  HttpException,
  HttpStatus,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createHash } from 'node:crypto';
import { LexRuntimeV2Client, RecognizeTextCommand } from '@aws-sdk/client-lex-runtime-v2';
import { BotMessageRequestDto, BotMessageResponseDto } from './dto/bot-message.dto';

export const EMPTY_RESPONSE_FALLBACK =
  'No tengo una respuesta para eso en este momento. Intenta reformular tu consulta.';

/**
 * Deriva el sessionId que se envía a Amazon Lex V2.
 * Fórmula oficial según docs/api/bot.md:
 * "u" + hex( SHA-256( UTF-8( sub + ":" + sessionId ) ) )[0:64]
 */
export function deriveLexSessionId(cognitoSub: string, clientSessionId: string): string {
  const digest = createHash('sha256')
    .update(`${cognitoSub}:${clientSessionId}`, 'utf8')
    .digest('hex');
  return 'u' + digest.slice(0, 64);
}

@Injectable()
export class BotService {
  private readonly logger = new Logger('BotService');
  private lexClient: LexRuntimeV2Client | null = null;
  private readonly mockMode: boolean;
  private readonly botId: string;
  private readonly botAliasId: string;
  private readonly localeId: string;
  private readonly region: string;

  constructor(private configService: ConfigService) {
    this.region = this.configService.get<string>('awsRegion') || 'us-east-1';
    this.botId = this.configService.get<string>('lex.botId') || 'HEE55FCSTB';
    this.botAliasId = this.configService.get<string>('lex.botAliasId') || 'Y1CGMUEYYK';
    this.localeId = this.configService.get<string>('lex.localeId') || 'es_419';
    this.mockMode = this.configService.get<boolean>('mockMode') || false;

    if (!this.mockMode) {
      try {
        this.lexClient = new LexRuntimeV2Client({ region: this.region });
      } catch (err: any) {
        this.logger.warn(`No se pudo inicializar LexRuntimeV2Client: ${err.message}. Modo fallback activo.`);
      }
    }
  }

  async sendMessage(cognitoSub: string, dto: BotMessageRequestDto): Promise<BotMessageResponseDto> {
    const text = dto.text.trim();
    const clientSessionId = dto.sessionId.trim();
    const lexSessionId = deriveLexSessionId(cognitoSub, clientSessionId);

    if (!this.mockMode && this.lexClient) {
      try {
        const command = new RecognizeTextCommand({
          botId: this.botId,
          botAliasId: this.botAliasId,
          localeId: this.localeId,
          sessionId: lexSessionId,
          text,
        });

        const response = await this.lexClient.send(command);

        const messages = (response.messages || [])
          .filter((msg) => (!msg.contentType || msg.contentType === 'PlainText') && msg.content && msg.content.trim())
          .map((msg) => msg.content!.trim());

        if (!messages.length) {
          this.logger.warn(`Lex devolvió respuesta vacía para session ${lexSessionId}`);
          return {
            messages: [EMPTY_RESPONSE_FALLBACK],
            sessionId: clientSessionId,
          };
        }

        return {
          messages,
          sessionId: clientSessionId,
        };
      } catch (err: any) {
        this.logger.error(`Error al invocar Amazon Lex V2: ${err.message}`, err.stack);

        const errorCode = err.name || err.Code || '';
        if (errorCode === 'ThrottlingException' || errorCode === 'ConflictException') {
          throw new HttpException(
            {
              code: 'RATE_LIMITED',
              message: 'Límite de solicitudes o concurrencia excedido en el asistente. Intente más tarde.',
            },
            HttpStatus.TOO_MANY_REQUESTS,
          );
        }

        // Si estamos en desarrollo local y falla por falta de credenciales AWS en consola
        if (process.env.NODE_ENV !== 'production') {
          this.logger.warn('Falla de conexión con AWS Lex en desarrollo local; usando fallback simulado.');
          return this.getMockBotResponse(text, clientSessionId);
        }

        throw new ServiceUnavailableException({
          code: 'SERVICE_UNAVAILABLE',
          message: 'El asistente virtual de la facultad no está disponible en este momento.',
        });
      }
    }

    // Modo Mock para pruebas locales
    return this.getMockBotResponse(text, clientSessionId);
  }

  private getMockBotResponse(text: string, sessionId: string): BotMessageResponseDto {
    const lower = text.toLowerCase();
    let reply =
      'Hola, soy el asistente virtual de la Facultad de Ingeniería de la USAC. Los horarios de atención son de lunes a viernes de 8:00 a 16:00 horas.\nFuente: Portal de Ingeniería USAC (consultado 2026-10-16).';

    if (lower.includes('hola') || lower.includes('buenos dias') || lower.includes('buenas')) {
      reply =
        '¡Hola! Te doy la bienvenida al asistente virtual de la Facultad de Ingeniería. ¿En qué puedo orientarte hoy?';
    } else if (lower.includes('gracias')) {
      reply = '¡Con gusto! Si tienes otra duda sobre trámites o servicios de la Facultad, aquí estoy para ayudarte.';
    }

    return {
      messages: [reply],
      sessionId,
    };
  }
}
