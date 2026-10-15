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
    @Body() body: CompleteProfileDto,
  ) {
    const faceReferenceKey = `Fotos_Perfil/references/${user.cognitoSub}/reference.jpg`;
    const updated = await this.databaseService.completeProfile(user.cognitoSub, body.profileImageKey, faceReferenceKey);

    return {
      userId: updated?.id || user.userId,
      profileComplete: true,
      profileImageKey: body.profileImageKey,
      message: 'Foto de perfil completada exitosamente. Funciones sociales habilitadas.',
    };
  }

  @Patch('me')
  @ApiOperation({ summary: 'Modificar datos de perfil (requiere confirmar la contraseña actual)' })
  @ApiResponse({ status: 200, description: 'Perfil actualizado exitosamente en Cognito y RDS' })
  @ApiResponse({ status: 401, description: 'Contraseña actual incorrecta' })
  async updateProfile(
    @CurrentUser() user: AuthUser,
    @Headers('authorization') authHeader: string,
    @Body() body: PatchProfileDto,
  ) {
    // 1. Validar que la contraseña actual sea correcta contra Cognito
    const isPasswordValid = await this.authService.verifyCurrentPassword(user.email, body.currentPassword);
    if (!isPasswordValid) {
      throw new UnauthorizedException({
        code: 'UNAUTHENTICATED',
        message: 'La contraseña actual ingresada es incorrecta. No se realizaron cambios.',
      });
    }

    // 2. Extraer token para actualizar atributos en Cognito
    const token = authHeader ? authHeader.replace('Bearer ', '').trim() : '';
    await this.authService.updateCognitoProfile(token, {
      fullName: body.fullName,
      dpi: body.dpi,
    });

    // 3. Actualizar en PostgreSQL RDS
    const updatedUser = await this.databaseService.updateProfile(user.cognitoSub, {
      fullName: body.fullName,
      dpi: body.dpi,
      profileImageKey: body.profileImageKey,
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
      updatedAt: updatedUser?.updated_at || new Date().toISOString(),
    };
  }

  @Get('users')
  @ApiOperation({ summary: 'Listar usuarios registrados que no son amigos (para enviar solicitudes)' })
  async listNonFriends(
    @CurrentUser() user: AuthUser,
    @Query('search') search?: string,
    @Query('limit') limit = 20,
  ) {
    return {
      users: [
        {
          userId: 'user-javier-uuid-222',
          fullName: 'Javier Velasquez',
          profileImageUrl: 'https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/javier.jpg',
        },
        {
          userId: 'user-guo-uuid-333',
          fullName: 'Guo Jhonatan',
          profileImageUrl: 'https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/guo.jpg',
        },
        {
          userId: 'user-isai-uuid-444',
          fullName: 'Isai Patzan',
          profileImageUrl: 'https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/isai.jpg',
        },
      ],
      nextCursor: null,
    };
  }
}
