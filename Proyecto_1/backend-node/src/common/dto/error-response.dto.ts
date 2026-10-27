import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class ErrorResponseDto {
  @ApiProperty({
    description: 'Código de error estándar de la aplicación',
    example: 'VALIDATION_ERROR',
  })
  code: string;

  @ApiProperty({
    description: 'Mensaje descriptivo del error para el cliente',
    example: 'Los datos proporcionados son inválidos.',
  })
  message: string;

  @ApiProperty({
    description: 'Identificador único de la solicitud para rastreo y auditoría',
    example: 'd9b2d63d-a232-446b-80df-2699863a34a8',
  })
  requestId: string;

  @ApiPropertyOptional({
    description: 'Detalles adicionales o lista de campos con error',
    example: { field: 'email', reason: 'Formato de correo inválido' },
  })
  details?: Record<string, any> | null;
}
