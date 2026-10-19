import { IsString, IsOptional, MaxLength } from 'class-validator';
import { BadRequestException } from '@nestjs/common';
import { ApiPropertyOptional } from '@nestjs/swagger';

export class CreateCommentRequestDto {
  @ApiPropertyOptional({
    example: '¡Excelente fotografía del evento en la facultad!',
    description: 'Contenido del comentario (máximo 2000 caracteres)',
  })
  @IsOptional()
  @IsString()
  @MaxLength(2000, { message: 'El comentario no puede exceder 2000 caracteres.' })
  content?: string;

  @ApiPropertyOptional({
    example: '¡Excelente fotografía del evento en la facultad!',
    description: 'Campo alternativo compatible con contrato FastAPI/Python',
  })
  @IsOptional()
  @IsString()
  @MaxLength(2000, { message: 'El comentario no puede exceder 2000 caracteres.' })
  body?: string;

  /**
   * Obtiene y valida el texto del comentario desde cualquiera de los dos nombres admitidos.
   */
  getCommentText(): string {
    const raw = this.content || this.body || '';
    const clean = raw.trim();
    if (!clean) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'El comentario debe contener texto (campo content o body no vacío).',
      });
    }
    return clean;
  }
}
