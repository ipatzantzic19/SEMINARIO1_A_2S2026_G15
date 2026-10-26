import { IsString, MaxLength, IsNotEmpty } from 'class-validator';
import { BadRequestException } from '@nestjs/common';
import { ApiProperty } from '@nestjs/swagger';

export class CreateCommentRequestDto {
  @ApiProperty({
    example: '¡Excelente fotografía del evento en la facultad!',
    description: 'Contenido del comentario (máximo 1000 caracteres)',
  })
  @IsString()
  @IsNotEmpty({ message: 'El comentario debe contener texto.' })
  @MaxLength(1000, { message: 'El comentario no puede exceder 1000 caracteres.' })
  body!: string;

  /**
   * Obtiene y valida el texto del comentario desde cualquiera de los dos nombres admitidos.
   */
  getCommentText(): string {
    const clean = this.body.trim();
    if (!clean) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        message: 'El comentario debe contener texto.',
      });
    }
    return clean;
  }
}
