// Cliente de la API del MVP. El token vive solo en memoria: al recargar se vuelve a iniciar sesión.
export type Rol = 'secretario' | 'juez' | 'admin' | 'abogado'
export type Estado = 'radicado' | 'en_tramite' | 'en_audiencia' | 'con_sentencia' | 'archivado'

export interface Sesion { token: string; rol: Rol; nombre: string }
export interface Usuario { id: number; username: string; nombre: string; rol: Rol; activo: boolean }
export interface Expediente {
  id: number; numero: string; materia: string; demandante: string; demandado: string; descripcion: string
  estado: Estado; juez_id: number | null; abogado_id: number | null; fecha_limite: string | null
  creado_en: string; actualizado_en: string
}
export interface Actuacion { id: number; tipo: string; detalle: string; fecha: string; usuario_id: number }
export interface ExpedienteDetalle extends Expediente { actuaciones: Actuacion[] }
export interface ExpedienteCreado extends Expediente { codigo_consulta: string }
export interface RegistroAuditoria {
  id: number; fecha: string; usuario: string; accion: string; entidad: string; entidad_id: string
  expediente_id: number | null; antes: string; despues: string; ip: string; hash: string
}
// HU-10 (Sprint 7)
export interface Documento { id: number; expediente_id: number; nombre: string; tamano: number; sha256: string; subido_por: number; fecha: string }
export interface VerificacionDocumento { integro: boolean; sha256_guardado: string; sha256_actual: string | null }
export interface Verificacion { integra: boolean; registros: number; roto_en_id?: number }
// HU-12 (Sprint 9): panel de congestión del administrador
export interface Congestion {
  fecha: string; total: number; activos: number; vencidos: number; antiguedad_promedio_dias: number; cuello_de_botella: Estado | null
  por_estado: { estado: Estado; cantidad: number; dias_promedio_en_etapa: number }[]
  por_juez: { juez_id: number | null; juez: string; activos: number; vencidos: number; antiguedad_promedio_dias: number }[]
  mas_antiguos: { id: number; numero: string; estado: Estado; materia: string; juez: string; dias: number; en_etapa_dias: number; vencido: boolean }[]
}
export interface ConsultaPublica { numero: string; materia: string; estado: Estado; actualizado_en: string; ultima_actuacion: string | null }

export class ApiError extends Error {
  campos?: { loc: (string | number)[]; msg: string }[]
  status: number
  constructor(msg: string, status: number) { super(msg); this.status = status }
}

let token: string | null = null
export const setToken = (t: string | null) => { token = t }

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const r = await fetch(path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  const data = await r.json().catch(() => null)
  if (!r.ok) {
    const d = data?.detail
    const msg = typeof d === 'string' ? d : typeof d?.mensaje === 'string' ? d.mensaje : 'Revisa los datos ingresados.'
    const err = new ApiError(msg, r.status)
    if (Array.isArray(d)) err.campos = d
    throw err
  }
  return data as T
}

export const post = <T>(path: string, body: unknown) => api<T>(path, { method: 'POST', body: JSON.stringify(body) })

// HU-10: subir un PDF (multipart) y descargarlo como blob con su huella SHA-256
async function errorDe(r: Response) {
  const data = await r.json().catch(() => null)
  const d = data?.detail
  return new ApiError(typeof d === 'string' ? d : 'No se pudo completar la operación.', r.status)
}
export async function subirArchivo<T>(path: string, archivo: File): Promise<T> {
  const fd = new FormData(); fd.append('archivo', archivo)
  const r = await fetch(path, { method: 'POST', body: fd, headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!r.ok) throw await errorDe(r)
  return (await r.json()) as T
}
export async function descargarArchivo(path: string): Promise<{ blob: Blob; sha256: string | null }> {
  const r = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!r.ok) throw await errorDe(r)
  return { blob: await r.blob(), sha256: r.headers.get('X-Content-SHA256') }
}
