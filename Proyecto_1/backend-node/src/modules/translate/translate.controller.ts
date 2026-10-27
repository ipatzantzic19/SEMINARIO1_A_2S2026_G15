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
import { TranslateService } from './translate.service';
import { TranslateRequestDto, TranslateResponseDto } from './dto/translate.dto';

@ApiTags('Traducción')
@ApiBearerAuth()
@Controller()
export class TranslateController {
  constructor(private readonly translateService: TranslateService) {}

  @Post(['translations', 'translate'])
  @HttpCode(HttpStatus.OK)
  @ApiOperation({
    summary: 'Traducir texto de publicaciones o comentarios (Amazon Translate)',
    description:
      'Traduce texto a uno de los 4 idiomas soportados: es, en, fr, de. Requiere autenticación con perfil completo.',
  })
  @ApiResponse({
    status: HttpStatus.OK,
    description: 'Texto traducido exitosamente.',
    type: TranslateResponseDto,
  })
  @ApiBadRequestResponse({ description: 'Error de validación en texto o idioma destino.' })
  @ApiUnauthorizedResponse({ description: 'No autenticado.' })
  @ApiForbiddenResponse({ description: 'Perfil incompleto.' })
  @ApiServiceUnavailableResponse({ description: 'Servicio de traducción no disponible.' })
  async translate(@Body() body: TranslateRequestDto): Promise<TranslateResponseDto> {
    return this.translateService.translate(body);
  }
}
