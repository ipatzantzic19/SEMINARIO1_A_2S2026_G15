import { Controller, Get, Param, ParseUUIDPipe, Query } from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiBearerAuth,
  ApiQuery,
  ApiPropertyOptional,
  ApiResponse,
} from '@nestjs/swagger';
import { Type } from 'class-transformer';
import { IsInt, IsOptional, IsString, Max, Min } from 'class-validator';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { DatabaseService } from '../../database/database.service';

class ChatMessagesQueryDto {
  @ApiPropertyOptional({ description: 'Puntero de paginación por fecha ISO 8601' })
  @IsOptional()
  @IsString()
  cursor?: string;

  @ApiPropertyOptional({ default: 20, minimum: 1, maximum: 50 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(50)
  limit = 20;
}

@ApiTags('Chat')
@ApiBearerAuth()
@Controller()
export class ChatController {
  constructor(private readonly databaseService: DatabaseService) {}

  @Get(['conversations/:friendId/messages', 'chat/conversations/:friendId/messages'])
  @ApiOperation({ summary: 'Obtener historial de mensajes con un amigo (paginación por cursor)' })
  @ApiQuery({ name: 'cursor', required: false, description: 'Puntero de paginación por fecha ISO 8601' })
  @ApiQuery({ name: 'limit', required: false, minimum: 1, maximum: 50, example: 20 })
  @ApiResponse({ status: 400, description: 'Identificador, cursor o límite inválido.' })
  @ApiResponse({ status: 401, description: 'No autenticado.' })
  @ApiResponse({ status: 403, description: 'Perfil incompleto o conversación no autorizada.' })
  @ApiResponse({ status: 404, description: 'Usuario o conversación no encontrada.' })
  async getMessages(
    @CurrentUser() user: AuthUser,
    @Param('friendId', new ParseUUIDPipe({ version: '4' })) friendId: string,
    @Query() query: ChatMessagesQueryDto,
  ) {
    const result = await this.databaseService.getConversationMessages(
      user.userId,
      friendId,
      query.cursor,
      query.limit,
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
