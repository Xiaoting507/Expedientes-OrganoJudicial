// HU-10 (Sprint 7): documentos PDF del expediente con huella SHA-256.
import * as React from 'react'
import { toast } from 'sonner'
import { Download, FileText, Loader2, ShieldAlert, ShieldCheck, Upload } from 'lucide-react'
import { api, descargarArchivo, subirArchivo, type ApiError, type Documento, type Estado, type Rol, type VerificacionDocumento } from '@/lib/api'
import { fechaHora } from '@/lib/formato'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const MAX_MB = 10
const tamano = (b: number) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`)

export function Documentos({ expId, rol, estado, onCambio }: { expId: number; rol: Rol; estado: Estado; onCambio?: () => void }) {
  const [docs, setDocs] = React.useState<Documento[] | null>(null)
  const [error, setError] = React.useState('')
  const [subiendo, setSubiendo] = React.useState(false)
  const [integridad, setIntegridad] = React.useState<Record<number, boolean>>({})
  const input = React.useRef<HTMLInputElement>(null)

  const cerrado = estado === 'archivado' || (rol === 'abogado' && estado === 'con_sentencia')
  const puedeSubir = (rol === 'secretario' || rol === 'juez' || rol === 'abogado') && !cerrado

  const cargar = React.useCallback(async () => {
    try { setDocs(await api<Documento[]>(`/api/expedientes/${expId}/documentos`)); setError('') } catch (e) { setError((e as ApiError).message) }
  }, [expId])
  React.useEffect(() => { cargar() }, [cargar])

  async function elegir(ev: React.ChangeEvent<HTMLInputElement>) {
    const archivo = ev.target.files?.[0]
    ev.target.value = ''
    if (!archivo) return
    if (archivo.type && archivo.type !== 'application/pdf') { setError('Solo se aceptan archivos PDF.'); return }
    if (archivo.size > MAX_MB * 1024 * 1024) { setError(`El PDF supera ${MAX_MB} MB.`); return }
    setSubiendo(true); setError('')
    try {
      const d = await subirArchivo<Documento>(`/api/expedientes/${expId}/documentos`, archivo)
      toast.success(`PDF adjuntado · huella ${d.sha256.slice(0, 12)}…`)
      await cargar(); onCambio?.()
    } catch (e) { setError((e as ApiError).message) } finally { setSubiendo(false) }
  }

  async function verificar(d: Documento) {
    try {
      const v = await api<VerificacionDocumento>(`/api/expedientes/${expId}/documentos/${d.id}/verificar`)
      setIntegridad((x) => ({ ...x, [d.id]: v.integro }))
      if (v.integro) toast.success('Íntegro: la huella SHA-256 coincide')
      else toast.error('Alterado: la huella no coincide con la guardada')
    } catch (e) { toast.error((e as ApiError).message) }
  }

  async function descargar(d: Documento) {
    try {
      const { blob } = await descargarArchivo(`/api/expedientes/${expId}/documentos/${d.id}`)
      const url = URL.createObjectURL(blob)
      const a = Object.assign(document.createElement('a'), { href: url, download: d.nombre })
      a.click(); URL.revokeObjectURL(url)
      onCambio?.()
    } catch (e) { setIntegridad((x) => ({ ...x, [d.id]: false })); toast.error((e as ApiError).message) }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><FileText className="text-primary size-4" /> Documentos PDF</CardTitle>
        <CardDescription>Cada archivo guarda su huella SHA-256: si alguien lo cambia, el sistema lo detecta.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {docs === null && !error && <p className="text-muted-foreground text-sm">Cargando…</p>}
        {docs?.length === 0 && <p className="text-muted-foreground text-sm">Aún no hay documentos adjuntos.</p>}
        {docs?.map((d) => (
          <div key={d.id} className="flex items-start gap-3 rounded-lg border p-3">
            {integridad[d.id] === false
              ? <ShieldAlert className="text-destructive mt-0.5 size-4 shrink-0" aria-label="Alterado" />
              : integridad[d.id] === true
                ? <ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-label="Íntegro" />
                : <FileText className="text-muted-foreground mt-0.5 size-4 shrink-0" aria-label="Sin verificar" />}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium" title={d.nombre}>{d.nombre}</p>
              <p className="text-muted-foreground text-xs">{tamano(d.tamano)} · {fechaHora(d.fecha)}</p>
              <p className="text-muted-foreground font-mono text-[11px]" title={d.sha256}>SHA-256 {d.sha256.slice(0, 16)}…</p>
            </div>
            <div className="flex shrink-0 gap-1">
              <Button size="sm" variant="ghost" onClick={() => verificar(d)} title="Verificar integridad"><ShieldCheck /></Button>
              <Button size="sm" variant="outline" onClick={() => descargar(d)} title="Descargar"><Download /></Button>
            </div>
          </div>
        ))}
        {error && <p role="alert" className="text-destructive text-sm">{error}</p>}
        {puedeSubir && (
          <>
            <input ref={input} type="file" accept="application/pdf,.pdf" className="hidden" onChange={elegir} />
            <Button variant="outline" onClick={() => input.current?.click()} disabled={subiendo}>
              {subiendo ? <Loader2 className="animate-spin" /> : <Upload />} Adjuntar PDF (máx. {MAX_MB} MB)
            </Button>
          </>
        )}
        {cerrado && <p className="text-muted-foreground text-xs">El expediente está cerrado: no admite documentos nuevos.</p>}
      </CardContent>
    </Card>
  )
}
