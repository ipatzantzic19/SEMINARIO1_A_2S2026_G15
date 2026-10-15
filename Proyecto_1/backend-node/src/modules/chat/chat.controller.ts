import { Controller, Get, Param, Query } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiQuery } from '@nestjs/swagger';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { v4 as uuidv4 } from 'uuid';

@ApiTags('Chat')
@ApiBearerAuth()
@Controller('chat')
export class ChatController {
  @Get('conversations/:friendId/messages')
  @ApiOperation({ summary: 'Obtener historial de mensajes con un amigo (paginación por cursor para reconexión WebSocket)' })
  @ApiQuery({ name: 'cursor', required: false })
  @ApiQuery({ name: 'limit', required: false })
  async getMessages(
    @CurrentUser() user: AuthUser,
    @Param('friendId') friendId: string,
    @Query('cursor') cursor?: string,
    @Query('limit') limit = 30,
  ) {
    return {
      friendId,
      messages: [
        {
          id: uuidv4(),
          senderId: friendId,
          recipientId: user.userId,
          content: '¡Hola Daniel! ¿Cómo va el despliegue en AWS?',
          createdAt: new Date(Date.now() - 3600000).toISOString(),
        },
        {
          id: uuidv4(),
          senderId: user.userId,
          recipientId: friendId,
          content: '¡Todo excelente! Ya tenemos la base de NestJS y los contratos configurados.',
          createdAt: new Date().toISOString(),
        },
      ],
      nextCursor: null,
    };
  }
}
