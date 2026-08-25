import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { v4 as uuidv4 } from 'uuid';

@Injectable()
export class S3Service implements OnModuleInit {
  private s3Client: S3Client;
  private readonly logger = new Logger(S3Service.name);
  private bucketName: string;
  private region: string;

  constructor(private configService: ConfigService) { }

  onModuleInit() {
    this.region = this.configService.get<string>('aws.region') || 'us-east-1';
    this.bucketName = this.configService.get<string>('aws.bucket') || 'practica1-images-g15';

    this.logger.log(`Initializing AWS S3 Client for region: ${this.region}, bucket: ${this.bucketName}`);


    // El SDK obtendrá automáticamente las credenciales del perfil de instancia de IAM
    // al desplegarse en EC2, o de las variables de entorno locales (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
    this.s3Client = new S3Client({ region: this.region });
  }


  /**
   * Sube un búfer de imagen a S3 bajo el prefijo especificado.
   * Devuelve la clave de S3 (p. ej., "Fotos_Perfil/uuid.jpg").
   */
  async uploadImage(
    buffer: Buffer,
    originalFilename: string,
    prefix: 'Fotos_Perfil/' | 'Fotos_Peliculas/',
    contentType: string,
  ): Promise<string> {
    const extension = originalFilename.split('.').pop() || 'jpg';
    const key = `${prefix}${uuidv4()}.${extension}`;

    this.logger.log(`Uploading file to S3: Bucket="${this.bucketName}", Key="${key}", ContentType="${contentType}"`);

    const command = new PutObjectCommand({
      Bucket: this.bucketName,
      Key: key,
      Body: buffer,
      ContentType: contentType,
    });

    try {
      await this.s3Client.send(command);
      this.logger.log(`Successfully uploaded file to S3: ${key}`);
      return key;
    } catch (error) {
      this.logger.error(`Failed to upload file to S3: ${error.message}`);
      throw error;
    }
  }

  /**
   * Construyes la URL pública para una clave S3.
   * p. ej. "https://{BUCKET_IMAGENES}.s3.{REGION_AWS}.amazonaws.com/{clave_portada}"
   */
  getPublicUrl(key: string): string {
    if (!key) return '';
    // Evitar añadir el prefijo dos veces si la clave ya lo tiene
    return `https://${this.bucketName}.s3.${this.region}.amazonaws.com/${key}`;
  }
}
