import { ApiProperty } from '@nestjs/swagger';
import { IsNotEmpty, IsString, MaxLength, MinLength } from 'class-validator';

export class BotMessageRequestDto {
  @ApiProperty({
    description: 'Texto de la consulta para el Asistente Virtual de la Facultad (1 a 500 caracteres)',
    example: '¿Cuál es el horario de atención de la facultad?',
    minLength: 1,
    maxLength: 500,
  })
  @IsString()
  @IsNotEmpty({ message: 'El texto del mensaje no puede estar vacío.' })
  @MinLength(1, { message: 'El texto debe contener al menos 1 carácter.' })
  @MaxLength(500, { message: 'El texto no puede superar los 500 caracteres.' })
  text: string;

  @ApiProperty({
    description: 'Identificador de sesión generado por el cliente (UUID o cadena de 1 a 100 caracteres)',
    example: '3f2504e0-4f89-41d3-9a0c-0305e82c3301',
    minLength: 1,
    maxLength: 100,
  })
  @IsString()
  @IsNotEmpty({ message: 'El sessionId es obligatorio.' })
  @MinLength(1, { message: 'El sessionId debe contener al menos 1 carácter.' })
  @MaxLength(100, { message: 'El sessionId no puede superar los 100 caracteres.' })
  sessionId: string;
}

export class BotMessageResponseDto {
  @ApiProperty({
    description: 'Arreglo ordenado con las respuestas de texto generadas por el bot',
    example: [
      'El horario de atención es de lunes a viernes de 8:00 a 16:00 horas.\nFuente: Horarios de Atención (consultado 2026-10-16).',
    ],
    type: [String],
  })
  messages: string[];

  @ApiProperty({
    description: 'El mismo sessionId enviado por el cliente sin alteraciones',
    example: '3f2504e0-4f89-41d3-9a0c-0305e82c3301',
  })
  sessionId: string;
}
