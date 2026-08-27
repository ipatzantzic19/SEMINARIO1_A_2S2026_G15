import { Module } from '@nestjs/common';
import { PerfilController } from './perfil.controller';
import { PerfilService } from './perfil.service';
import { AutenticacionModule } from '../autenticacion/autenticacion.module';

@Module({
  imports: [AutenticacionModule],
  controllers: [PerfilController],
  providers: [PerfilService],
})
export class PerfilModule {}
