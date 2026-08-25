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

  constructor(private configService: ConfigService) {}

  onModuleInit() {
    this.region = this.configService.get<string>('aws.region') || 'us-east-1';
    this.bucketName = this.configService.get<string>('aws.bucket') || 'practica1-images-g15';

    this.logger.log(`Initializing AWS S3 Client for region: ${this.region}, bucket: ${this.bucketName}`);

    // The SDK will automatically fetch credentials from IAM Instance Profile
    // when deployed to EC2, or from local environment variables (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
    this.s3Client = new S3Client({ region: this.region });
  }

  /**
   * Uploads an image buffer to S3 under the specified prefix.
   * Returns the S3 key (e.g. "Fotos_Perfil/uuid.jpg").
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
   * Builds the public URL for an S3 key.
   * e.g. "https://{BUCKET_IMAGENES}.s3.{REGION_AWS}.amazonaws.com/{clave_portada}"
   */
  getPublicUrl(key: string): string {
    if (!key) return '';
    // Avoid double prefixing if the key already has it
    return `https://${this.bucketName}.s3.${this.region}.amazonaws.com/${key}`;
  }
}
