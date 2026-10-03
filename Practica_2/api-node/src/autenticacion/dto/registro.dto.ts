import { IsString, IsNotEmpty, IsEmail, MinLength, MaxLength, Matches, IsOptional } from 'class-validator';

export class RegistroDto {
  @IsString({ message: 'El nombre de usuario debe ser una cadena de texto.' })
  @IsNotEmpty({ message: 'El nombre de usuario no puede estar vacío.' })
  @MinLength(3, { message: 'El nombre de usuario debe tener al menos 3 caracteres.' })
  @MaxLength(50, { message: 'El nombre de usuario no puede exceder 50 caracteres.' })
  @Matches(/^[a-z0-9_]+$/, { message: 'El nombre de usuario solo debe contener minúsculas, números y guiones bajos.' })
  nombreUsuario: string;

  @IsString({ message: 'El correo electrónico debe ser una cadena de texto.' })
  @IsNotEmpty({ message: 'El correo electrónico no puede estar vacío.' })
  @IsEmail({}, { message: 'El correo electrónico debe tener un formato válido.' })
  @MaxLength(254, { message: 'El correo electrónico no puede exceder 254 caracteres.' })
  correoElectronico: string;

  @IsString({ message: 'La contraseña debe ser una cadena de texto.' })
  @IsNotEmpty({ message: 'La contraseña no puede estar vacía.' })
  @MinLength(8, { message: 'La contraseña debe tener al menos 8 caracteres.' })
  @MaxLength(72, { message: 'La contraseña no puede exceder 72 caracteres.' })
  contrasena: string;

  @IsString({ message: 'La confirmación de contraseña debe ser una cadena de texto.' })
  @IsNotEmpty({ message: 'La confirmación de contraseña no puede estar vacía.' })
  @MinLength(8, { message: 'La confirmación de contraseña debe tener al menos 8 caracteres.' })
  @MaxLength(72, { message: 'La confirmación de contraseña no puede exceder 72 caracteres.' })
  confirmacionContrasena: string;

  @IsOptional()
  @IsString({ message: 'La URL de la imagen de perfil debe ser una cadena de texto.' })
  @Matches(/^https:\/\/\S+$/, { message: 'La URL de la imagen de perfil debe ser una URL HTTPS válida.' })
  urlImagenPerfil?: string;
}
