import { ApiProperty } from '@nestjs/swagger';
import { IsIn, IsNotEmpty, IsOptional, IsString, MaxLength } from 'class-validator';

export class TranslateRequestDto {
  @ApiProperty({
    description: 'Texto a traducir (1 a 5,000 caracteres)',
    example: 'Bienvenidos a Semi-Social.',
    minLength: 1,
    maxLength: 5000,
  })
  @IsString()
  @IsNotEmpty({ message: 'El texto a traducir no puede estar vacío.' })
  @MaxLength(5000, { message: 'El texto no puede superar los 5,000 caracteres.' })
  text: string;

  @ApiProperty({
    description: 'Idioma origen del texto (código ISO 639-1 o "auto")',
    example: 'auto',
    default: 'auto',
    required: false,
  })
  @IsString()
  @IsOptional()
  sourceLanguage?: string;

  @ApiProperty({
    description: 'Idioma destino soportado (es, en, fr, de)',
    example: 'en',
    enum: ['es', 'en', 'fr', 'de'],
  })
  @IsString()
  @IsNotEmpty({ message: 'El idioma destino es obligatorio.' })
  @IsIn(['es', 'en', 'fr', 'de'], {
    message: 'El idioma destino debe ser uno de los permitidos: es, en, fr, de.',
  })
  targetLanguage: 'es' | 'en' | 'fr' | 'de';
}

export class TranslateResponseDto {
  @ApiProperty({ example: 'Welcome to Semi-Social.' })
  translatedText: string;

  @ApiProperty({ example: 'es' })
  sourceLanguage: string;

  @ApiProperty({ example: 'en' })
  targetLanguage: string;
}
