import { IsNotEmpty, IsOptional, IsString, Length } from 'class-validator';

export class ActualizarPerfilDto {
  @IsString({ message: 'contrasenaActual debe ser una cadena de caracteres' })
  @IsNotEmpty({ message: 'contrasenaActual no debe estar vacío' })
  contrasenaActual: string;

  @IsOptional()
  @IsString({ message: 'nombreCompleto debe ser una cadena de caracteres' })
  @Length(1, 150, { message: 'nombreCompleto debe tener entre 1 y 150 caracteres' })
  nombreCompleto?: string;
}
