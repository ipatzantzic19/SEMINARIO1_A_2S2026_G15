import { ApiProperty } from '@nestjs/swagger';
import { IsEmail, IsNotEmpty, IsString, Length, Matches, MinLength } from 'class-validator';

export class RegisterRequestDto {
  @ApiProperty({ example: 'Daniel Abraham Ortiz', description: 'Nombre completo del usuario' })
  @IsString()
  @Length(2, 160)
  fullName: string;

  @ApiProperty({ example: 'daniel.ortiz@ingenieria.usac.edu.gt', description: 'Correo electrónico institucional o personal' })
  @IsEmail()
  email: string;

  @ApiProperty({ example: '1234567890101', description: 'DPI de 13 dígitos exactos' })
  @IsString()
  @Matches(/^\d{13}$/, { message: 'El DPI debe contener exactamente 13 dígitos numéricos' })
  dpi: string;

  @ApiProperty({ example: 'Seguridad2026!', description: 'Contraseña de mínimo 8 caracteres' })
  @IsString()
  @MinLength(8, { message: 'La contraseña debe contener al menos 8 caracteres' })
  password: string;
}

export class ConfirmRequestDto {
  @ApiProperty({ example: 'daniel.ortiz@ingenieria.usac.edu.gt' })
  @IsEmail()
  email: string;

  @ApiProperty({ example: '123456', description: 'Código de confirmación enviado por correo de Cognito' })
  @IsString()
  @IsNotEmpty()
  code: string;
}

export class LoginRequestDto {
  @ApiProperty({ example: 'daniel.ortiz@ingenieria.usac.edu.gt' })
  @IsEmail()
  email: string;

  @ApiProperty({ example: 'Seguridad2026!' })
  @IsString()
  @IsNotEmpty()
  password: string;
}

export class FaceLoginInitDto {
  @ApiProperty({ example: 'daniel.ortiz@ingenieria.usac.edu.gt' })
  @IsEmail()
  email: string;
}

export class FaceLoginVerifyDto {
  @ApiProperty({ example: 'challenge-uuid-1234' })
  @IsString()
  @IsNotEmpty()
  challengeId: string;

  @ApiProperty({ example: 'Fotos_Perfil/captures/sub/capture-uuid.jpg' })
  @IsString()
  @IsNotEmpty()
  captureKey: string;
}
