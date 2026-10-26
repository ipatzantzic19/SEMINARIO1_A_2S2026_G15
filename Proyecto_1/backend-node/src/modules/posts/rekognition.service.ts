import {
  Injectable,
  Logger,
  NotFoundException,
  BadRequestException,
  ServiceUnavailableException,
  BadGatewayException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  RekognitionClient,
  DetectLabelsCommand,
} from '@aws-sdk/client-rekognition';

export interface NormalizedLabel {
  name: string;
  confidence: number;
  sourceName: string;
}

// Diccionario base de normalización español <-> inglés según labels.md
const SPANISH_LABEL_MAP: Record<string, string> = {
  dog: 'perro',
  canine: 'canino',
  pet: 'mascota',
  animal: 'animal',
  mammal: 'mamífero',
  cat: 'gato',
  feline: 'felino',
  outdoors: 'exterior',
  nature: 'naturaleza',
  building: 'edificio',
  architecture: 'arquitectura',
  campus: 'campus',
  university: 'universidad',
  school: 'escuela',
  person: 'persona',
  human: 'humano',
  people: 'gente',
  landscape: 'paisaje',
  tree: 'árbol',
  plant: 'planta',
  flower: 'flor',
  technology: 'tecnología',
  computer: 'computadora',
  electronics: 'electrónica',
  city: 'ciudad',
  urban: 'urbano',
  street: 'calle',
  car: 'vehículo',
  automobile: 'automóvil',
  sky: 'cielo',
  cloud: 'nube',
  water: 'agua',
};

@Injectable()
export class RekognitionService {
  private readonly logger = new Logger('RekognitionService');
  private rekognitionClient: RekognitionClient;
  private bucket: string;
  private mockMode: boolean;

  constructor(private configService: ConfigService) {
    const region = this.configService.get<string>('awsRegion') || 'us-east-1';
    this.bucket =
      this.configService.get<string>('s3.imagesBucket') ||
      'semisocial-g15-images-581117996165';
    this.mockMode = this.configService.get<boolean>('mockMode') || false;

    this.rekognitionClient = new RekognitionClient({ region });
  }

  /**
   * Normaliza una etiqueta de Rekognition según docs/api/labels.md
   */
  normalizeLabel(sourceName: string, rawConfidence: number): NormalizedLabel {
    const trimmed = (sourceName || '').trim().normalize('NFC');
    const lower = trimmed.toLowerCase();
    const translated = SPANISH_LABEL_MAP[lower] || lower;
    const confidence = Math.round(Number(rawConfidence) * 100) / 100;

    return {
      name: translated,
      confidence,
      sourceName: trimmed,
    };
  }

  /**
   * Invoca DetectLabels sobre un objeto en S3 dentro de Fotos_Publicadas/
   */
  async detectLabels(imageKey: string): Promise<NormalizedLabel[]> {
    if (!imageKey || !imageKey.startsWith('Fotos_Publicadas/')) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'La clave de imagen debe pertenecer al prefijo Fotos_Publicadas/.',
      });
    }

    if (this.mockMode) {
      this.logger.log(`[MOCK] DetectLabels para ${imageKey}`);
      return this.getMockLabels(imageKey);
    }

    const command = new DetectLabelsCommand({
      Image: {
        S3Object: {
          Bucket: this.bucket,
          Name: imageKey,
        },
      },
      MaxLabels: 20,
      MinConfidence: 80.0,
    });

    // Estrategia de reintentos compartida (hasta 2 reintentos con backoff 250ms/750ms)
    const maxRetries = 2;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const response = await this.rekognitionClient.send(command);
        const labels: NormalizedLabel[] = [];

        for (const item of response.Labels || []) {
          if (item.Name && item.Confidence && item.Confidence >= 80.0) {
            labels.push(this.normalizeLabel(item.Name, item.Confidence));
          }
        }

        // Si Rekognition no detectó etiquetas válidas, devolver arreglo vacío conforme a OpenAPI
        return labels;
      } catch (err: any) {
        const code = err.name || err.Code || '';
        this.logger.warn(`Intento ${attempt + 1} DetectLabels falló: ${code} - ${err.message}`);

        if (code === 'InvalidS3ObjectException' || code === 'NoSuchKey') {
          throw new NotFoundException({
            code: 'POST_IMAGE_NOT_FOUND',
            message: 'El objeto de imagen especificado no existe en S3.',
          });
        }

        if (code === 'InvalidImageFormatException' || code === 'UnsupportedImageException') {
          throw new BadRequestException({
            code: 'POST_IMAGE_INVALID',
            message: 'Formato de imagen inválido o no soportado para análisis visual.',
          });
        }

        if (code === 'AccessDeniedException') {
          throw new BadGatewayException({
            code: 'LABELS_NOT_AUTHORIZED',
            message: 'Permiso denegado por política IAM para invocar Rekognition DetectLabels.',
          });
        }

        // Throttling o InternalServerError: reintentar con backoff
        if (attempt < maxRetries && (code === 'ProvisionedThroughputExceededException' || code === 'InternalServerError')) {
          const delay = attempt === 0 ? 250 : 750;
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }

        if (attempt === maxRetries) {
          throw new ServiceUnavailableException({
            code: 'LABELS_TEMPORARILY_UNAVAILABLE',
            message: 'El servicio de detección de etiquetas no está disponible temporalmente.',
          });
        }
      }
    }

    return [];
  }

  private getMockLabels(imageKey: string): NormalizedLabel[] {
    const keyLower = imageKey.toLowerCase();
    if (keyLower.includes('dog') || keyLower.includes('perro')) {
      return [
        { name: 'perro', confidence: 98.12, sourceName: 'Dog' },
        { name: 'canino', confidence: 95.4, sourceName: 'Canine' },
        { name: 'exterior', confidence: 91.44, sourceName: 'Outdoors' },
      ];
    }
    if (keyLower.includes('cat') || keyLower.includes('gato')) {
      return [
        { name: 'gato', confidence: 97.5, sourceName: 'Cat' },
        { name: 'felino', confidence: 93.2, sourceName: 'Feline' },
      ];
    }
    if (keyLower.includes('labels-example-1') || keyLower.includes('campus') || keyLower.includes('universidad')) {
      return [
        { name: 'campus', confidence: 99.12, sourceName: 'Campus' },
        { name: 'universidad', confidence: 98.45, sourceName: 'University' },
        { name: 'exterior', confidence: 96.2, sourceName: 'Outdoors' },
        { name: 'arquitectura', confidence: 92.15, sourceName: 'Architecture' },
      ];
    }
    if (keyLower.includes('labels-example-2') || keyLower.includes('paisaje')) {
      return [
        { name: 'paisaje', confidence: 98.8, sourceName: 'Landscape' },
        { name: 'naturaleza', confidence: 94.6, sourceName: 'Nature' },
        { name: 'árbol', confidence: 91.3, sourceName: 'Tree' },
      ];
    }

    return [
      { name: 'campus', confidence: 97.45, sourceName: 'Campus' },
      { name: 'exterior', confidence: 93.8, sourceName: 'Outdoors' },
      { name: 'tecnología', confidence: 89.2, sourceName: 'Technology' },
    ];
  }
}
