import { Controller, Get, Post, Patch, Param, Body } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiProperty } from '@nestjs/swagger';
import { IsIn, IsNotEmpty, IsString } from 'class-validator';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { v4 as uuidv4 } from 'uuid';

export class SendFriendRequestDto {
  @ApiProperty({ example: 'user-javier-uuid-222' })
  @IsString()
  @IsNotEmpty()
  addresseeId: string;
}

export class DecideFriendRequestDto {
  @ApiProperty({ example: 'accept', enum: ['accept', 'reject'] })
  @IsIn(['accept', 'reject'])
  decision: 'accept' | 'reject';
}

@ApiTags('Amigos')
@ApiBearerAuth()
@Controller()
export class FriendsController {
  @Get('friends')
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

  @Get('friend-requests')
  @ApiOperation({ summary: 'Listar solicitudes de amistad recibidas y enviadas' })
  async getFriendRequests(@CurrentUser() user: AuthUser) {
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

  @Post('friend-requests')
  @ApiOperation({ summary: 'Enviar una solicitud de amistad' })
  async sendFriendRequest(
    @CurrentUser() user: AuthUser,
    @Body() body: SendFriendRequestDto,
  ) {
    return {
      requestId: uuidv4(),
      requesterId: user.userId,
      addresseeId: body.addresseeId,
      status: 'pending',
      createdAt: new Date().toISOString(),
    };
  }

  @Patch('friend-requests/:requestId')
  @ApiOperation({ summary: 'Aceptar o rechazar una solicitud de amistad' })
  async decideFriendRequest(
    @Param('requestId') requestId: string,
    @Body() body: DecideFriendRequestDto,
  ) {
    const status = body.decision === 'accept' ? 'accepted' : 'rejected';
    return {
      requestId,
      status,
      message: `Solicitud de amistad ${status === 'accepted' ? 'aceptada' : 'rechazada'}.`,
    };
  }
}
