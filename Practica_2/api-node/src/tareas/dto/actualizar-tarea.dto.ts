import { IsString, IsNotEmpty, MaxLength, IsOptional } from 'class-validator';

export class ActualizarTareaDto {
  @IsString({ message: 'El título debe ser una cadena de texto.' })
  @IsNotEmpty({ message: 'El título no puede estar vacío.' })
  @MaxLength(200, { message: 'El título no puede exceder 200 caracteres.' })
  titulo: string;

  @IsOptional()
  @IsString({ message: 'La descripción debe ser una cadena de texto.' })
  descripcion?: string;
}
