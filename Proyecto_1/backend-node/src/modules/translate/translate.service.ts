import {
  Injectable,
  Logger,
  HttpException,
  HttpStatus,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { TranslateClient, TranslateTextCommand } from '@aws-sdk/client-translate';
import { TranslateRequestDto, TranslateResponseDto } from './dto/translate.dto';

@Injectable()
export class TranslateService {
  private readonly logger = new Logger('TranslateService');
  private translateClient: TranslateClient | null = null;
  private readonly mockMode: boolean;
  private readonly region: string;

  constructor(private configService: ConfigService) {
    this.region = this.configService.get<string>('awsRegion') || 'us-east-1';
    this.mockMode = this.configService.get<boolean>('mockMode') || false;

    if (!this.mockMode) {
      try {
        this.translateClient = new TranslateClient({ region: this.region });
      } catch (err: any) {
        this.logger.warn(`No se pudo inicializar TranslateClient: ${err.message}. Modo fallback activo.`);
      }
    }
  }

  async translate(dto: TranslateRequestDto): Promise<TranslateResponseDto> {
    const text = dto.text.trim();
    const sourceLanguage = dto.sourceLanguage || 'auto';
    const targetLanguage = dto.targetLanguage;

    if (!this.mockMode && this.translateClient) {
      try {
        const command = new TranslateTextCommand({
          Text: text,
          SourceLanguageCode: sourceLanguage,
          TargetLanguageCode: targetLanguage,
        });

        const response = await this.translateClient.send(command);

        return {
          translatedText: response.TranslatedText || text,
          sourceLanguage: response.SourceLanguageCode || sourceLanguage,
          targetLanguage: response.TargetLanguageCode || targetLanguage,
        };
      } catch (err: any) {
        this.logger.error(`Error al invocar Amazon Translate: ${err.message}`, err.stack);

        const errorCode = err.name || err.Code || '';
        if (errorCode === 'TooManyRequestsException' || errorCode === 'LimitExceededException') {
          throw new HttpException(
            {
              code: 'RATE_LIMITED',
              message: 'Límite de solicitudes de traducción excedido. Intente más tarde.',
            },
            HttpStatus.TOO_MANY_REQUESTS,
          );
        }

        // Si estamos en desarrollo y falla por credenciales, podemos hacer fallback
        if (process.env.NODE_ENV !== 'production') {
          this.logger.warn('Falla de conexión con AWS Translate en desarrollo local; usando fallback simulado.');
          return this.getMockTranslation(text, sourceLanguage, targetLanguage);
        }

        throw new ServiceUnavailableException({
          code: 'SERVICE_UNAVAILABLE',
          message: 'El servicio de traducción no está disponible en este momento.',
        });
      }
    }

    // Modo Mock
    return this.getMockTranslation(text, sourceLanguage, targetLanguage);
  }

  private getMockTranslation(
    text: string,
    sourceLanguage: string,
    targetLanguage: string,
  ): TranslateResponseDto {
    const mockDict: Record<string, string> = {
      en: `[EN] ${text}`,
      fr: `[FR] ${text}`,
      de: `[DE] ${text}`,
      es: `[ES] ${text}`,
    };

    return {
      translatedText: mockDict[targetLanguage] || text,
      sourceLanguage: sourceLanguage === 'auto' ? 'es' : sourceLanguage,
      targetLanguage,
    };
  }
}
