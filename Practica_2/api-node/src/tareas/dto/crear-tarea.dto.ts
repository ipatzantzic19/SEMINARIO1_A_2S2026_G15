import { IsString, IsNotEmpty, MaxLength, IsOptional, Matches } from 'class-validator';

export class CrearTareaDto {
  @IsString({ message: 'El título debe ser una cadena de texto.' })
  @IsNotEmpty({ message: 'El título no puede estar vacío.' })
  @MaxLength(200, { message: 'El título no puede exceder 200 caracteres.' })
  titulo: string;

  @IsOptional()
  @IsString({ message: 'La descripción debe ser una cadena de texto.' })
  descripcion?: string;

  @IsOptional()
  @IsString({ message: 'La fecha de creación debe ser una cadena de texto con formato ISO 8601.' })
  @Matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt ][0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?([Zz]|[+-][0-9]{2}:?[0-9]{2})?$/, {
    message: 'La fecha de creación debe ser un formato de fecha ISO 8601 válido con zona horaria.',
  })
  fechaCreacion?: string;
}
