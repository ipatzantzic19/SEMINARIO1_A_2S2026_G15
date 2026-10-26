import { IsString, IsNotEmpty, MaxLength, MinLength } from 'class-validator';
import { BadRequestException } from '@nestjs/common';
import { ApiProperty } from '@nestjs/swagger';

export class CreateCommentRequestDto {
  @ApiProperty({
    example: '¡Excelente fotografía del evento en la facultad!',
    description: 'Contenido del comentario conforme a OpenAPI (máximo 1000 caracteres)',
  })
  @IsString({ message: 'El campo body debe ser una cadena de texto.' })
  @IsNotEmpty({ message: 'El campo body es obligatorio.' })
  @MinLength(1, { message: 'El comentario debe tener al menos 1 caracter.' })
  @MaxLength(1000, { message: 'El comentario no puede exceder 1000 caracteres.' })
  body: string;

  /**
   * Obtiene y valida el texto del comentario desde el campo oficial body.
   */
  getCommentText(): string {
    const clean = (this.body || '').trim();
    if (!clean) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'El comentario debe contener texto (campo body no vacío).',
      });
    }
    return clean;
  }
}
