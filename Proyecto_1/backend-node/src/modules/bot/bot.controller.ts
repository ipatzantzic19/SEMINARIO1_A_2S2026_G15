import { Controller, Post, Body, HttpCode, HttpStatus } from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiBearerAuth,
  ApiResponse,
  ApiBadRequestResponse,
  ApiUnauthorizedResponse,
  ApiForbiddenResponse,
  ApiServiceUnavailableResponse,
} from '@nestjs/swagger';
import { BotService } from './bot.service';
import { BotMessageRequestDto, BotMessageResponseDto } from './dto/bot-message.dto';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';

@ApiTags('Bot')
@ApiBearerAuth()
@Controller('bot')
export class BotController {
  constructor(private readonly botService: BotService) {}

  @Post('messages')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({
    summary: 'Enviar consulta al Asistente Virtual de la Facultad (Amazon Lex V2)',
    description:
      'Envía una pregunta de texto al bot oficial de la facultad y retorna los mensajes en orden junto con el sessionId. Requiere perfil completo.',
  })
  @ApiResponse({
    status: HttpStatus.OK,
    description: 'Respuesta del bot generada exitosamente.',
    type: BotMessageResponseDto,
  })
  @ApiBadRequestResponse({ description: 'Error de validación en texto o sessionId.' })
  @ApiUnauthorizedResponse({ description: 'No autenticado.' })
  @ApiForbiddenResponse({ description: 'Perfil incompleto.' })
  @ApiServiceUnavailableResponse({ description: 'Asistente virtual no disponible.' })
  async sendMessage(
    @CurrentUser() user: AuthUser,
    @Body() body: BotMessageRequestDto,
  ): Promise<BotMessageResponseDto> {
    const cognitoSub = user?.cognitoSub || '11111111-1111-4111-8111-111111111111';
    return this.botService.sendMessage(cognitoSub, body);
  }
}
