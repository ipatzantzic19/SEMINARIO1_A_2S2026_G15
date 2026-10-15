import { Controller, Post, Body, HttpCode, HttpStatus } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiProperty } from '@nestjs/swagger';
import { IsIn, IsNotEmpty, IsOptional, IsString } from 'class-validator';

export class TranslationRequestDto {
  @ApiProperty({ example: 'Bienvenidos a Semi-Social.' })
  @IsString()
  @IsNotEmpty()
  text: string;

  @ApiProperty({
    example: 'en',
    enum: ['es', 'en', 'fr', 'de'],
    description: 'Idioma destino soportado (español o 3 adicionales)',
  })
  @IsIn(['es', 'en', 'fr', 'de'], { message: 'El idioma destino debe ser uno de: es, en, fr, de' })
  targetLanguage?: string;

  @ApiProperty({ example: 'en', required: false })
  @IsOptional()
  @IsIn(['es', 'en', 'fr', 'de'])
  targetLang?: string;

  @ApiProperty({ example: 'es', required: false })
  @IsString()
  @IsOptional()
  sourceLanguage?: string;

  @ApiProperty({ example: 'es', required: false })
  @IsString()
  @IsOptional()
  sourceLang?: string;
}

@ApiTags('Traducción')
@ApiBearerAuth()
@Controller()
export class TranslateController {
  @Post(['translations', 'translate'])
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Traducir texto de publicaciones o comentarios (Amazon Translate)' })
  async translate(@Body() body: TranslationRequestDto) {
    const target = body.targetLanguage || body.targetLang || 'en';
    const source = body.sourceLanguage || body.sourceLang || 'auto';

    const mockTranslations: Record<string, string> = {
      en: `[EN] ${body.text} (Translated)`,
      fr: `[FR] ${body.text} (Traduit)`,
      de: `[DE] ${body.text} (Übersetzt)`,
      es: `[ES] ${body.text} (Traducido)`,
    };

    return {
      translatedText: mockTranslations[target] || body.text,
      sourceLanguage: source,
      targetLanguage: target,
      sourceLang: source,
      targetLang: target,
    };
  }
}
