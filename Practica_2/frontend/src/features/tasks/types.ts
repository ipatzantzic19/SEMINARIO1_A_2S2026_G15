export type Task = {
  id: number;
  usuarioId: number;
  titulo: string;
  descripcion: string;
  fechaCreacion: string;
  completada: boolean;
  fechaCompletada: string | null;
  actualizadoEn?: string;
};
export type TaskInput = { titulo: string; descripcion: string; fechaCreacion?: string };
export type TaskChange =
  | { kind: 'create'; input: TaskInput }
  | { kind: 'edit'; id: number; input: TaskInput }
  | { kind: 'complete'; id: number; completada: boolean }
  | { kind: 'delete'; id: number };
