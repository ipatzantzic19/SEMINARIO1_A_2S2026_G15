import {
  Controller,
  Get,
  Post,
  Patch,
  Param,
  Body,
  HttpCode,
  HttpStatus,
  ParseUUIDPipe,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiBearerAuth,
  ApiProperty,
  ApiResponse,
} from '@nestjs/swagger';
import { IsIn, IsNotEmpty, IsUUID } from 'class-validator';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { FriendsService } from './friends.service';

export class SendFriendRequestDto {
  @ApiProperty({
    example: '596bdc55-48ac-47b9-a93d-fd15b7646db5',
    description: 'UUID del usuario destinatario de la solicitud',
  })
  @IsUUID('4', { message: 'addresseeId debe ser un UUID v4 válido.' })
  @IsNotEmpty({ message: 'addresseeId es obligatorio.' })
  addresseeId: string;
}

export class DecideFriendRequestDto {
  @ApiProperty({
    example: 'accepted',
    enum: ['accepted', 'rejected'],
    description: 'Decisión sobre la solicitud de amistad',
  })
  @IsIn(['accepted', 'rejected'], {
    message: 'decision debe ser "accepted" o "rejected".',
  })
  @IsNotEmpty({ message: 'decision es obligatoria.' })
  decision: 'accepted' | 'rejected';
}

@ApiTags('Amistades')
@ApiBearerAuth()
@Controller()
export class FriendsController {
  constructor(private readonly friendsService: FriendsService) {}

  @Get('friends')
  @ApiOperation({
    summary: 'Listar amigos aceptados disponibles para chat',
    description: 'Devuelve la lista de usuarios que tienen una relación de amistad confirmada con el usuario autenticado.',
  })
  @ApiResponse({
    status: 200,
    description: 'Lista de amigos confirmados.',
  })
  @ApiResponse({ status: 401, description: 'No autenticado.' })
  @ApiResponse({ status: 403, description: 'Perfil incompleto.' })
  async getFriends(@CurrentUser() user: AuthUser) {
    return this.friendsService.getFriends(user.userId);
  }

  @Get('friend-requests')
  @ApiOperation({
    summary: 'Listar solicitudes de amistad pendientes recibidas y enviadas',
    description: 'Devuelve todas las solicitudes pendientes donde el usuario actual es el solicitante o el destinatario.',
  })
  @ApiResponse({
    status: 200,
    description: 'Lista de solicitudes pendientes.',
  })
  @ApiResponse({ status: 401, description: 'No autenticado.' })
  @ApiResponse({ status: 403, description: 'Perfil incompleto.' })
  async getFriendRequests(@CurrentUser() user: AuthUser) {
    return this.friendsService.getFriendRequests(user.userId);
  }

  @Post('friend-requests')
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({
    summary: 'Enviar una solicitud de amistad',
    description: 'Crea una nueva solicitud pendiente hacia otro usuario registrado con perfil completo.',
  })
  @ApiResponse({
    status: 201,
    description: 'Solicitud creada con éxito en estado pending.',
  })
  @ApiResponse({ status: 400, description: 'Destinatario inválido o perfil incompleto.' })
  @ApiResponse({ status: 401, description: 'No autenticado.' })
  @ApiResponse({ status: 403, description: 'Perfil incompleto.' })
  @ApiResponse({ status: 404, description: 'Usuario destinatario no encontrado.' })
  @ApiResponse({ status: 409, description: 'Ya existe una solicitud o amistad.' })
  async sendFriendRequest(
    @CurrentUser() user: AuthUser,
    @Body() body: SendFriendRequestDto,
  ) {
    return this.friendsService.sendFriendRequest(user.userId, body.addresseeId);
  }

  @Patch('friend-requests/:requestId')
  @ApiOperation({
    summary: 'Aceptar o rechazar una solicitud de amistad',
    description: 'Permite exclusivamente al destinatario aceptar o rechazar una solicitud pendiente.',
  })
  @ApiResponse({
    status: 200,
    description: 'Solicitud resuelta con éxito.',
  })
  @ApiResponse({ status: 400, description: 'Decisión inválida.' })
  @ApiResponse({ status: 401, description: 'No autenticado.' })
  @ApiResponse({ status: 403, description: 'Solo el destinatario puede resolver la solicitud.' })
  @ApiResponse({ status: 404, description: 'Solicitud no encontrada.' })
  async decideFriendRequest(
    @CurrentUser() user: AuthUser,
    @Param('requestId', new ParseUUIDPipe({ version: '4' })) requestId: string,
    @Body() body: DecideFriendRequestDto,
  ) {
    return this.friendsService.decideFriendRequest(
      requestId,
      user.userId,
      body.decision,
    );
  }
}
