import { IsEmail, IsNotEmpty, IsString, Length, MinLength } from 'class-validator';

export class RegistroDto {
  @IsEmail({}, { message: 'correoElectronico debe ser un correo electrónico válido' })
  @IsNotEmpty({ message: 'correoElectronico no debe estar vacío' })
  @Length(4, 254, { message: 'correoElectronico debe tener entre 4 y 254 caracteres' })
  correoElectronico: string;

  @IsString({ message: 'nombreCompleto debe ser una cadena de caracteres' })
  @IsNotEmpty({ message: 'nombreCompleto no debe estar vacío' })
  @Length(1, 150, { message: 'nombreCompleto debe tener entre 1 y 150 caracteres' })
  nombreCompleto: string;

  @IsString({ message: 'contrasena debe ser una cadena de caracteres' })
  @IsNotEmpty({ message: 'contrasena no debe estar vacío' })
  @Length(6, 72, { message: 'contrasena debe tener entre 6 y 72 caracteres' })
  contrasena: string;

  @IsString({ message: 'confirmacionContrasena debe ser una cadena de caracteres' })
  @IsNotEmpty({ message: 'confirmacionContrasena no debe estar vacío' })
  @Length(6, 72, { message: 'confirmacionContrasena debe tener entre 6 y 72 caracteres' })
  confirmacionContrasena: string;
}

export class InicioSesionDto {
  @IsEmail({}, { message: 'correoElectronico debe ser un correo electrónico válido' })
  @IsNotEmpty({ message: 'correoElectronico no debe estar vacío' })
  @Length(4, 254, { message: 'correoElectronico debe tener entre 4 y 254 caracteres' })
  correoElectronico: string;

  @IsString({ message: 'contrasena debe ser una cadena de caracteres' })
  @IsNotEmpty({ message: 'contrasena no debe estar vacío' })
  @Length(6, 72, { message: 'contrasena debe tener entre 6 y 72 caracteres' })
  contrasena: string;
}
