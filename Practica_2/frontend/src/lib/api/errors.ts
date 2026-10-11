export class ApiError extends Error {
  status: number;
  code: string;
  constructor(message: string, status = 0, code = 'CONEXION') {
    super(message); this.name = 'ApiError'; this.status = status; this.code = code;
  }
}
