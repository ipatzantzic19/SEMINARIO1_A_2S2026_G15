import { Controller, Get, Post, Put, Body, Query, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiResponse } from '@nestjs/swagger';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';

@ApiTags('Usuarios')
@ApiBearerAuth()
@Controller()
export class UsersController {
  @Get('me')
  @ApiOperation({ summary: 'Obtener el perfil del usuario autenticado' })
  async getMyProfile(@CurrentUser() user: AuthUser) {
    return {
      userId: user.userId,
      cognitoSub: user.cognitoSub,
      email: user.email,
      fullName: 'Daniel Abraham Ortiz',
      dpi: '1234567890101',
      profileImageKey: 'Fotos_Perfil/public/mock-sub/avatar.jpg',
      profileImageUrl: 'https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/mock-sub/avatar.jpg',
      profileComplete: user.profileComplete,
      createdAt: new Date().toISOString(),
    };
  }

  @Post('me/complete-profile')
  @ApiOperation({ summary: 'Completar foto inicial de perfil tras el primer inicio de sesión' })
  async completeProfile(
    @CurrentUser() user: AuthUser,
    @Body() body: { profileImageKey: string; faceReferenceKey: string },
  ) {
    return {
      userId: user.userId,
      profileComplete: true,
      profileImageKey: body.profileImageKey,
      message: 'Perfil completado correctamente. Funcionalidades sociales habilitadas.',
    };
  }

  @Put('me')
  @ApiOperation({ summary: 'Editar datos del perfil (requiere contraseña actual)' })
  async updateProfile(
    @CurrentUser() user: AuthUser,
    @Body() body: { fullName?: string; dpi?: string; profileImageKey?: string; currentPassword: string },
  ) {
    return {
      userId: user.userId,
      fullName: body.fullName || 'Daniel Abraham Ortiz',
      dpi: body.dpi || '1234567890101',
      profileImageKey: body.profileImageKey || 'Fotos_Perfil/public/mock-sub/avatar.jpg',
      updatedAt: new Date().toISOString(),
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
