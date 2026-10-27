import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsEmail, IsNotEmpty, IsOptional, IsString, Length, Matches, MinLength } from 'class-validator';

export class RegisterRequestDto {
  @ApiProperty({ example: 'Daniel Abraham Ortiz', description: 'Nombre completo del usuario' })
  @IsString()
  @Length(2, 160)
  fullName: string;

  @ApiProperty({ example: 'daniel.ortiz@ingenieria.usac.edu.gt', description: 'Correo electrónico' })
  @IsEmail()
  email: string;

  @ApiProperty({ example: '1234567890101', description: 'DPI de 13 dígitos numéricos exactos' })
  @IsString()
  @Matches(/^\d{13}$/, { message: 'El DPI debe contener exactamente 13 dígitos numéricos' })
  dpi: string;

  @ApiProperty({
    example: 'Seguridad2026!#',
    description: 'Contraseña de mínimo 12 caracteres (requiere mayúscula, minúscula, número y símbolo según política Cognito)',
  })
  @IsString()
  @MinLength(12, { message: 'La contraseña debe contener al menos 12 caracteres' })
  @Matches(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\^$*.[\]{}()?"!@#%&/\\,><':;|_~`=+-]).{12,}$/, {
    message: 'La contraseña debe incluir al menos una mayúscula, una minúscula, un número y un símbolo especial.',
  })
  password: string;
}

export class ConfirmRequestDto {
  @ApiProperty({ example: 'daniel.ortiz@ingenieria.usac.edu.gt' })
  @IsEmail()
  email: string;

  @ApiProperty({ example: '123456', description: 'Código de confirmación de 6 dígitos enviado por correo' })
  @IsString()
  @Length(6, 8)
  code: string;
}

export class ResendConfirmationCodeRequestDto {
  @ApiProperty({ example: 'daniel.ortiz@ingenieria.usac.edu.gt' })
  @IsEmail()
  email: string;
}

export class LoginRequestDto {
  @ApiProperty({ example: 'daniel.ortiz@ingenieria.usac.edu.gt' })
  @IsEmail()
  email: string;

  @ApiProperty({ example: 'Seguridad2026!#' })
  @IsString()
  @MinLength(8)
  password: string;
}

export class FaceChallengeRequestDto {
  @ApiProperty({ example: 'daniel.ortiz@ingenieria.usac.edu.gt' })
  @IsEmail()
  email: string;
}

export class FaceVerifyRequestDto {
  @ApiProperty({ example: 'Fotos_Perfil/captures/c09a8123/capture-uuid.jpg' })
  @IsString()
  @IsNotEmpty()
  captureKey: string;

}

export class PatchProfileDto {
  @ApiPropertyOptional({ example: 'Daniel Abraham Ortiz Chinchilla' })
  @IsOptional()
  @IsString()
  @Length(2, 160)
  fullName?: string;

  @ApiPropertyOptional({ example: '1234567890101' })
  @IsOptional()
  @IsString()
  @Matches(/^\d{13}$/, { message: 'El DPI debe contener exactamente 13 dígitos numéricos' })
  dpi?: string;

  @ApiPropertyOptional({ example: 'Fotos_Perfil/public/c09a8123/avatar-nuevo.jpg' })
  @IsOptional()
  @IsString()
  profileImageKey?: string;

  @ApiProperty({ example: 'Seguridad2026!#', description: 'Contraseña actual requerida para confirmar modificaciones' })
  @IsString()
  @IsNotEmpty()
  currentPassword: string;
}

export class CompleteProfileDto {
  @ApiProperty({ example: 'Fotos_Perfil/public/c09a8123/avatar-uuid.jpg' })
  @IsString()
  @IsNotEmpty()
  profileImageKey: string;
}
