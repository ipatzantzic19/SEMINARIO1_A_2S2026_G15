import {
  Controller,
  Get,
  Post,
  Param,
  Body,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiBearerAuth,
  ApiResponse,
  ApiParam,
} from '@nestjs/swagger';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { DatabaseService } from '../../database/database.service';
import { CreateCommentRequestDto } from './dto/comment.dto';

@ApiTags('Comentarios')
@ApiBearerAuth()
@Controller('posts/:postId/comments')
export class CommentsController {
  constructor(private databaseService: DatabaseService) {}

  @Get()
  @ApiOperation({
    summary: 'Listar comentarios de una publicación',
    description: 'Permitido solo para el autor de la publicación o sus amigos confirmados.',
  })
  @ApiParam({ name: 'postId', description: 'UUID de la publicación' })
  @ApiResponse({ status: 200, description: 'Comentarios obtenidos ordenados cronológicamente' })
  @ApiResponse({ status: 403, description: 'No tienes permiso para ver esta publicación ni sus comentarios' })
  @ApiResponse({ status: 404, description: 'Publicación no encontrada' })
  async getComments(
    @CurrentUser() user: AuthUser,
    @Param('postId') postId: string,
  ) {
    return this.databaseService.getComments(postId, user.userId);
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({
    summary: 'Agregar un comentario a una publicación',
    description: 'Solo el autor o sus amigos confirmados pueden comentar en la publicación.',
  })
  @ApiParam({ name: 'postId', description: 'UUID de la publicación' })
  @ApiResponse({ status: 201, description: 'Comentario creado exitosamente' })
  @ApiResponse({ status: 400, description: 'Texto del comentario vacío o inválido' })
  @ApiResponse({ status: 403, description: 'No eres amigo del autor de la publicación' })
  @ApiResponse({ status: 404, description: 'Publicación no encontrada' })
  async addComment(
    @CurrentUser() user: AuthUser,
    @Param('postId') postId: string,
    @Body() body: CreateCommentRequestDto,
  ) {
    const text = body.getCommentText();
    return this.databaseService.createComment(postId, user.userId, text);
  }
}
