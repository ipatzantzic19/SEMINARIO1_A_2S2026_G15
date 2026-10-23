import {
  Controller,
  Get,
  Post,
  Body,
  Query,
  HttpCode,
  HttpStatus,
  ForbiddenException,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiBearerAuth,
  ApiQuery,
  ApiResponse,
} from '@nestjs/swagger';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { DatabaseService } from '../../database/database.service';
import { RekognitionService } from './rekognition.service';
import { CreatePostRequestDto, FeedQueryDto } from './dto/post.dto';

@ApiTags('Publicaciones')
@ApiBearerAuth()
@Controller()
export class PostsController {
  constructor(
    private databaseService: DatabaseService,
    private rekognitionService: RekognitionService,
  ) {}

  @Get('posts')
  @ApiOperation({
    summary: 'Obtener feed de publicaciones (propias y de amigos confirmados)',
    description: 'Devuelve publicaciones ordenadas de más reciente a más antigua con paginación por cursor y filtros opcionales.',
  })
  @ApiResponse({ status: 200, description: 'Feed de publicaciones obtenido exitosamente' })
  @ApiResponse({ status: 401, description: 'Token no provisto o inválido' })
  @ApiResponse({ status: 403, description: 'Perfil incompleto' })
  async getFeed(
    @CurrentUser() user: AuthUser,
    @Query() query: FeedQueryDto,
  ) {
    return this.databaseService.getFeed(user.userId, {
      limit: query.limit,
      cursor: query.cursor,
      label: query.label,
      q: query.q,
    });
  }

  @Post('posts')
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({
    summary: 'Crear una nueva publicación y procesar etiquetas con Rekognition',
    description: 'Registra la publicación, invoca DetectLabels y persiste las etiquetas detectadas en RDS.',
  })
  @ApiResponse({ status: 201, description: 'Publicación creada exitosamente con etiquetas' })
  @ApiResponse({ status: 400, description: 'Clave de imagen ausente o formato inválido' })
  @ApiResponse({ status: 403, description: 'La imagen pertenece a otro usuario o perfil incompleto' })
  async createPost(
    @CurrentUser() user: AuthUser,
    @Body() body: CreatePostRequestDto,
  ) {
    // 1. Validar propiedad de la clave S3 según contrato compartido
    const expectedPrefix = `Fotos_Publicadas/${user.cognitoSub}/`;
    const isAcademicFixture = body.imageKey.startsWith('Fotos_Publicadas/examples/');

    if (!body.imageKey.startsWith(expectedPrefix) && !isAcademicFixture) {
      throw new ForbiddenException({
        code: 'FORBIDDEN',
        message: 'La clave de imagen debe pertenecer al usuario autenticado.',
      });
    }

    // 2. Invocar AWS Rekognition DetectLabels (con reintentos y normalización)
    const labels = await this.rekognitionService.detectLabels(body.imageKey);

    // 3. Persistir en RDS de forma transaccional (posts y post_labels)
    const post = await this.databaseService.createPost(
      user.userId,
      body.imageKey,
      body.description || null,
      labels,
    );

    return post;
  }

  @Get('labels')
  @ApiOperation({
    summary: 'Listar catálogo dinámico de etiquetas detectadas para filtros y búsqueda',
    description: 'Devuelve lista con conteo de publicaciones por etiqueta, incluyendo la opción Todos.',
  })
  @ApiQuery({ name: 'q', required: false, description: 'Filtrar etiquetas por nombre' })
  @ApiResponse({ status: 200, description: 'Catálogo de etiquetas obtenido' })
  async getLabels(@CurrentUser() user: AuthUser, @Query('q') q?: string) {
    return this.databaseService.getLabels(user.userId, q);
  }
}
