import { IsString, IsNotEmpty, IsOptional, MaxLength, Matches, IsInt, Min, Max } from 'class-validator';
import { Type } from 'class-transformer';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class CreatePostRequestDto {
  @ApiProperty({
    example: 'Fotos_Publicadas/c09a8123-1122-3344-5566-778899aabbcc/8f4c2e10-482a-4c22-b5b6-7e10c71a39f1.jpg',
    description: 'Clave S3 del objeto previamente cargado en Fotos_Publicadas/',
  })
  @IsString()
  @IsNotEmpty({ message: 'La clave de imagen imageKey es obligatoria.' })
  @Matches(/^Fotos_Publicadas\//, { message: 'La clave de imagen debe pertenecer al prefijo Fotos_Publicadas/' })
  imageKey: string;

  @ApiPropertyOptional({
    example: 'Vista panorámica del edificio T-3 de Ingeniería, USAC',
    description: 'Descripción textual opcional de la publicación (máx 2000 caracteres)',
  })
  @IsOptional()
  @IsString()
  @MaxLength(2000, { message: 'La descripción no puede exceder los 2000 caracteres.' })
  description?: string;
}

export class FeedQueryDto {
  @ApiPropertyOptional({ default: 10, minimum: 1, maximum: 50, description: 'Cantidad máxima de publicaciones' })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(50)
  limit?: number = 10;

  @ApiPropertyOptional({ description: 'Puntero de paginación ISO 8601' })
  @IsOptional()
  @IsString()
  cursor?: string;

  @ApiPropertyOptional({ description: 'Filtro por etiqueta detectada por Rekognition (ej. perro, campus)' })
  @IsOptional()
  @IsString()
  label?: string;

}
