import { Controller, Get, Post, Param, Body } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { v4 as uuidv4 } from 'uuid';

@ApiTags('Amigos')
@ApiBearerAuth()
@Controller('friends')
export class FriendsController {
  @Get()
  @ApiOperation({ summary: 'Listar amigos confirmados del usuario' })
  async getFriends(@CurrentUser() user: AuthUser) {
    return {
      friends: [
        {
          userId: 'user-javier-uuid-222',
          fullName: 'Javier Velasquez',
          email: 'javier@example.com',
          profileImageUrl: 'https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/javier.jpg',
          friendshipDate: new Date().toISOString(),
        },
      ],
    };
  }

  @Get('requests')
  @ApiOperation({ summary: 'Listar solicitudes de amistad entrantes y salientes' })
  async getRequests(@CurrentUser() user: AuthUser) {
    return {
      incoming: [
        {
          requestId: 'req-friend-111',
          sender: {
            userId: 'user-guo-uuid-333',
            fullName: 'Guo Jhonatan',
            profileImageUrl: 'https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/guo.jpg',
          },
          createdAt: new Date().toISOString(),
        },
      ],
      outgoing: [],
    };
  }

  @Post('requests')
  @ApiOperation({ summary: 'Enviar una nueva solicitud de amistad' })
  async sendRequest(
    @CurrentUser() user: AuthUser,
    @Body() body: { addresseeId: string },
  ) {
    return {
      requestId: uuidv4(),
      requesterId: user.userId,
      addresseeId: body.addresseeId,
      status: 'pending',
      createdAt: new Date().toISOString(),
    };
  }

  @Post('requests/:requestId/accept')
  @ApiOperation({ summary: 'Aceptar una solicitud de amistad' })
  async acceptRequest(@Param('requestId') requestId: string) {
    return {
      requestId,
      status: 'accepted',
      message: 'Solicitud de amistad aceptada exitosamente.',
    };
  }

  @Post('requests/:requestId/reject')
  @ApiOperation({ summary: 'Rechazar una solicitud de amistad' })
  async rejectRequest(@Param('requestId') requestId: string) {
    return {
      requestId,
      status: 'rejected',
      message: 'Solicitud de amistad rechazada.',
    };
  }
}
