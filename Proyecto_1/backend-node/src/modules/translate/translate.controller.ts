import { Controller, Post, Body, BadRequestException } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiProperty } from '@nestjs/swagger';
import { IsIn, IsNotEmpty, IsOptional, IsString } from 'class-validator';

export class TranslateRequestDto {
  @ApiProperty({ example: 'Hola, bienvenidos a Semi-Social.' })
  @IsString()
  @IsNotEmpty()
  text: string;

  @ApiProperty({ example: 'en', enum: ['es', 'en', 'fr', 'de'], description: 'Idioma destino (español o 3 adicionales)' })
  @IsIn(['es', 'en', 'fr', 'de'], { message: 'El idioma destino debe ser uno de: es, en, fr, de' })
  targetLang: string;

  @ApiProperty({ example: 'es', required: false })
  @IsString()
  @IsOptional()
  sourceLang?: string;
}

@ApiTags('Traducción')
@ApiBearerAuth()
@Controller('translate')
export class TranslateController {
  @Post()
  @ApiOperation({ summary: 'Traducir texto de publicaciones o comentarios (Amazon Translate)' })
  async translate(@Body() body: TranslateRequestDto) {
    // Mapeo básico de simulación para desarrollo local
    const mockTranslations: Record<string, string> = {
      en: `[EN] ${body.text} (Translated)`,
      fr: `[FR] ${body.text} (Traduit)`,
      de: `[DE] ${body.text} (Übersetzt)`,
      es: `[ES] ${body.text} (Traducido)`,
    };

    return {
      translatedText: mockTranslations[body.targetLang] || body.text,
      sourceLang: body.sourceLang || 'auto',
      targetLang: body.targetLang,
    };
  }
}
