import { IsBoolean, IsNotEmpty } from 'class-validator';

export class CambiarEstadoTareaDto {
  @IsBoolean({ message: 'El campo completada debe ser un valor booleano.' })
  @IsNotEmpty({ message: 'El campo completada es obligatorio.' })
  completada: boolean;
}
