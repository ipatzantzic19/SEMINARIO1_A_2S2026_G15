import { Controller, Post, Body, HttpCode, HttpStatus } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiProperty } from '@nestjs/swagger';
import { IsNotEmpty, IsOptional, IsString } from 'class-validator';

export class BotMessageDto {
  @ApiProperty({ example: '¿Cuáles son los horarios de atención de la facultad de ingeniería?' })
  @IsString()
  @IsNotEmpty()
  message: string;

  @ApiProperty({ required: false })
  @IsOptional()
  sessionState?: Record<string, any>;
}

@ApiTags('Chatbot')
@ApiBearerAuth()
@Controller('bot')
export class BotController {
  @Post('messages')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Enviar consulta al Asistente Virtual de la Facultad (Amazon Lex)' })
  async sendMessage(@Body() body: BotMessageDto) {
    return {
      reply: 'Hola, soy el asistente virtual de la Facultad de Ingeniería de la USAC. Los horarios de atención son de lunes a viernes de 8:00 a 16:00 horas.',
      sessionState: body.sessionState || null,
    };
  }
}
