import { Controller, Get, Param, Query } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiQuery } from '@nestjs/swagger';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { DatabaseService } from '../../database/database.service';

@ApiTags('Chat')
@ApiBearerAuth()
@Controller()
export class ChatController {
  constructor(private readonly databaseService: DatabaseService) {}

  @Get(['conversations/:friendId/messages', 'chat/conversations/:friendId/messages'])
  @ApiOperation({ summary: 'Obtener historial de mensajes con un amigo (paginación por cursor)' })
  @ApiQuery({ name: 'cursor', required: false })
  @ApiQuery({ name: 'limit', required: false })
  async getMessages(
    @CurrentUser() user: AuthUser,
    @Param('friendId') friendId: string,
    @Query('cursor') cursor?: string,
    @Query('limit') limit = 50,
  ) {
    const result = await this.databaseService.getConversationMessages(
      user.userId,
      friendId,
      cursor,
      Number(limit) || 50,
    );

    return {
      items: result.items,
      nextCursor: result.nextCursor,
      // Retrocompatibilidad con esquemas alternativos
      messages: result.items,
      friendId,
    };
  }
}
