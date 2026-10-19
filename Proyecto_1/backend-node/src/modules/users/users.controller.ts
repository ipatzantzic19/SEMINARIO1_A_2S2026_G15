import {
  Controller,
  Get,
  Post,
  Patch,
  Body,
  Query,
  Headers,
  HttpCode,
  HttpStatus,
  BadRequestException,
  UnauthorizedException,
  NotFoundException,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiResponse } from '@nestjs/swagger';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { DatabaseService } from '../../database/database.service';
import { AuthService } from '../auth/auth.service';
import { PatchProfileDto, CompleteProfileDto } from '../auth/dto/auth.dto';

@ApiTags('Usuarios')
@ApiBearerAuth()
@Controller()
export class UsersController {
  constructor(
    private databaseService: DatabaseService,
    private authService: AuthService,
  ) {}

  @Get('me')
  @ApiOperation({ summary: 'Obtener el perfil del usuario autenticado' })
  @ApiResponse({ status: 200, description: 'Perfil obtenido exitosamente' })
  @ApiResponse({ status: 401, description: 'Token inválido o ausente' })
  async getMyProfile(@CurrentUser() user: AuthUser) {
    const dbUser = await this.databaseService.findUserByCognitoSub(user.cognitoSub);
    if (!dbUser) {
      throw new NotFoundException({
        code: 'NOT_FOUND',
        message: 'Usuario no encontrado en la base de datos.',
      });
    }

    const s3Bucket = process.env.S3_IMAGES_BUCKET || 'semisocial-g15-images-581117996165';
    const profileImageUrl = dbUser.profile_image_key
      ? `https://${s3Bucket}.s3.us-east-1.amazonaws.com/${dbUser.profile_image_key}`
      : null;

    return {
      userId: dbUser.id,
      email: dbUser.email,
      fullName: dbUser.full_name,
      dpi: dbUser.dpi,
      profileImageKey: dbUser.profile_image_key,
      profileImageUrl,
      profileComplete: Boolean(dbUser.profile_image_key),
      createdAt: dbUser.created_at,
    };
  }

  @Post('me/complete-profile')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Completar foto inicial de perfil y generar referencia facial privada' })
  @ApiResponse({ status: 200, description: 'Foto de perfil asignada y cuenta habilitada para funciones sociales' })
  async completeProfile(
    @CurrentUser() user: AuthUser,
    @Headers('authorization') authHeader: string,
    @Body() body: CompleteProfileDto,
  ) {
    // Derivar la clave de referencia privada a partir de la clave pública recibida
    const faceReferenceKey = body.profileImageKey.startsWith('Fotos_Perfil/public/')
      ? body.profileImageKey.replace('Fotos_Perfil/public/', 'Fotos_Perfil/references/')
      : `Fotos_Perfil/references/${user.cognitoSub}/${body.profileImageKey.replace(/^Fotos_Perfil\//, '')}`;

    // 1. Guardar en PostgreSQL RDS
    const updated = await this.databaseService.completeProfile(user.cognitoSub, body.profileImageKey, faceReferenceKey);

    // 2. Guardar custom:face_reference_key en Cognito User Pool
    const token = authHeader ? authHeader.replace(/^Bearer\s+/i, '').trim() : '';
    await this.authService.updateFaceReferenceKey(user.cognitoSub, faceReferenceKey, token);

    const s3Bucket = process.env.S3_IMAGES_BUCKET || 'semisocial-g15-images-581117996165';
    const profileImageUrl = updated?.profile_image_key
      ? `https://${s3Bucket}.s3.us-east-1.amazonaws.com/${updated.profile_image_key}`
      : null;

    return {
      userId: updated?.id || user.userId,
      fullName: updated?.full_name || '',
      email: updated?.email || user.email,
      dpi: updated?.dpi || '',
      profileImageUrl,
      profileComplete: true,
      profileImageKey: body.profileImageKey,
      message: 'Foto de perfil completada exitosamente. Funciones sociales habilitadas.',
    };
  }

  @Patch('me')
  @ApiOperation({ summary: 'Modificar datos de perfil (requiere confirmar la contraseña actual)' })
  @ApiResponse({ status: 200, description: 'Perfil actualizado exitosamente en Cognito y RDS' })
  @ApiResponse({ status: 400, description: 'Contraseña actual incorrecta (INVALID_CURRENT_PASSWORD)' })
  async updateProfile(
    @CurrentUser() user: AuthUser,
    @Headers('authorization') authHeader: string,
    @Body() body: PatchProfileDto,
  ) {
    // 1. Validar que la contraseña actual sea correcta contra Cognito
    const isPasswordValid = await this.authService.verifyCurrentPassword(user.email, body.currentPassword);
    if (!isPasswordValid) {
      throw new BadRequestException({
        code: 'VALIDATION_ERROR',
        reason: 'INVALID_CURRENT_PASSWORD',
        message: 'La contraseña actual no es correcta. No se realizaron cambios.',
        details: {
          reason: 'INVALID_CURRENT_PASSWORD',
        },
      });
    }

    // 2. Extraer token para actualizar atributos en Cognito
    const token = authHeader ? authHeader.replace(/^Bearer\s+/i, '').trim() : '';
    await this.authService.updateCognitoProfile(token, {
      fullName: body.fullName,
      dpi: body.dpi,
    });

    // Si se envía nueva foto de perfil, derivar y actualizar custom:face_reference_key en Cognito
    let faceReferenceKey: string | undefined = undefined;
    if (body.profileImageKey) {
      faceReferenceKey = body.profileImageKey.startsWith('Fotos_Perfil/public/')
        ? body.profileImageKey.replace('Fotos_Perfil/public/', 'Fotos_Perfil/references/')
        : `Fotos_Perfil/references/${user.cognitoSub}/${body.profileImageKey.replace(/^Fotos_Perfil\//, '')}`;
      await this.authService.updateFaceReferenceKey(user.cognitoSub, faceReferenceKey, token);
    }

    // 3. Actualizar en PostgreSQL RDS
    const updatedUser = await this.databaseService.updateProfile(user.cognitoSub, {
      fullName: body.fullName,
      dpi: body.dpi,
      profileImageKey: body.profileImageKey,
      faceReferenceKey,
    });

    const s3Bucket = process.env.S3_IMAGES_BUCKET || 'semisocial-g15-images-581117996165';
    const profileImageUrl = updatedUser?.profile_image_key
      ? `https://${s3Bucket}.s3.us-east-1.amazonaws.com/${updatedUser.profile_image_key}`
      : null;

    return {
      userId: updatedUser?.id || user.userId,
      email: updatedUser?.email || user.email,
      fullName: updatedUser?.full_name || body.fullName,
      dpi: updatedUser?.dpi || body.dpi,
      profileImageKey: updatedUser?.profile_image_key || body.profileImageKey,
      profileImageUrl,
      profileComplete: Boolean(updatedUser?.profile_image_key || body.profileImageKey),
      updatedAt: updatedUser?.updated_at || new Date().toISOString(),
    };
  }

  @Get('users')
  @ApiOperation({
    summary: 'Listar usuarios registrados que no son amigos ni el usuario actual',
    description: 'Devuelve una página de usuarios con perfil completo que no tienen una relación de amistad con el usuario autenticado.',
  })
  @ApiResponse({
    status: 200,
    description: 'Página de usuarios no amigos con cursor para paginación.',
  })
  async listNonFriends(
    @CurrentUser() user: AuthUser,
    @Query('cursor') cursor?: string,
    @Query('limit') limit = 20,
  ) {
    const numLimit = Number(limit) || 20;
    return this.databaseService.listNonFriends(user.userId, cursor, numLimit);
  }
}

