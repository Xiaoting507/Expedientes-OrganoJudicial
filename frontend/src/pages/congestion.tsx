import * as React from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from 'recharts'
import { AlarmClock, FolderOpen, Hourglass, RefreshCw, TriangleAlert } from 'lucide-react'
import { api, type Congestion as Datos } from '@/lib/api'
import { ESTADOS, materia } from '@/lib/formato'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/misc'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { COLOR_ESTADO, Encabezado, EstadoBadge } from '@/components/comunes'

// HU-12 (Sprint 9): ¿dónde se atasca el proceso? Solo administrador; sin nombres de las partes.
const dias = (n: number) => `${n.toLocaleString('es-PA', { maximumFractionDigits: 1 })} día${n === 1 ? '' : 's'}`

function Kpi({ titulo, valor, detalle, icono: Icono, tono }: { titulo: string; valor: string | number; detalle: string; icono: typeof Hourglass; tono: string }) {
  return (
    <Card className="gap-3 py-4">
      <CardHeader className="px-4">
        <CardDescription className="text-[13px] font-medium">{titulo}</CardDescription>
        <CardAction><div className={cn('grid size-8 place-items-center rounded-lg', tono)}><Icono className="size-4" /></div></CardAction>
      </CardHeader>
      <CardContent className="px-4">
        <div className="text-3xl font-semibold tracking-tight tabular-nums">{valor}</div>
        <p className="text-muted-foreground mt-1 text-xs">{detalle}</p>
      </CardContent>
    </Card>
  )
}

export function Congestion() {
  const [d, setD] = React.useState<Datos | null>(null)
  const [error, setError] = React.useState(false)
  const cargar = React.useCallback(() => {
    setError(false)
    api<Datos>('/api/congestion').then(setD).catch(() => setError(true))
  }, [])
  React.useEffect(() => { cargar() }, [cargar])

  const etapas = (d?.por_estado ?? []).filter((e) => e.estado !== 'archivado')
  const cuello = d?.cuello_de_botella ? etapas.find((e) => e.estado === d.cuello_de_botella) : undefined

  return (
    <div className="space-y-6">
      <Encabezado titulo="Panel de congestión" descripcion="Dónde se atasca el proceso: carga por juez, días en cada etapa y plazos vencidos. No muestra nombres de las partes.">
        <Button variant="outline" onClick={cargar}><RefreshCw /> Actualizar</Button>
      </Encabezado>

      {error && <p role="alert" className="border-destructive/40 bg-destructive/8 rounded-xl border p-4 text-sm">No se pudo cargar el panel. Intenta de nuevo.</p>}

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {!d ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[118px] rounded-xl" />) : (
          <>
            <Kpi titulo="Expedientes activos" valor={d.activos} detalle={`${d.total} en total · sin contar archivados`} icono={FolderOpen} tono="bg-blue-500/10 text-blue-600 dark:text-blue-400" />
            <Kpi titulo="Plazos vencidos" valor={d.vencidos} detalle={d.vencidos ? 'Sin sentencia ni archivo' : 'Ninguno vencido'} icono={AlarmClock} tono="bg-red-500/10 text-red-600 dark:text-red-400" />
            <Kpi titulo="Antigüedad promedio" valor={dias(d.antiguedad_promedio_dias)} detalle="Desde la radicación" icono={Hourglass} tono="bg-amber-500/12 text-amber-600 dark:text-amber-400" />
            <Kpi titulo="Cuello de botella" valor={cuello ? ESTADOS[cuello.estado] : '—'} detalle={cuello ? `${dias(cuello.dias_promedio_en_etapa)} en promedio en esa etapa` : 'Sin expedientes activos'} icono={TriangleAlert} tono="bg-violet-500/10 text-violet-600 dark:text-violet-400" />
          </>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Días promedio en cada etapa</CardTitle>
            <CardDescription>Desde el último cambio de estado; la barra más alta es donde se acumula el tiempo</CardDescription>
          </CardHeader>
          <CardContent className="h-[240px]">
            {!d ? <Skeleton className="h-full rounded-lg" /> : (
              <ResponsiveContainer>
                <BarChart data={etapas.map((e) => ({ ...e, nombre: ESTADOS[e.estado] }))} margin={{ left: -16, right: 8, top: 8 }}>
                  <XAxis dataKey="nombre" tickLine={false} axisLine={false} fontSize={12} stroke="var(--muted-foreground)" />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={12} stroke="var(--muted-foreground)" />
                  <RTooltip cursor={{ fill: 'var(--muted)' }} formatter={(v, _n, p) => [`${dias(Number(v))} · ${p.payload.cantidad} exp.`, 'Promedio']}
                    contentStyle={{ background: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                  <Bar dataKey="dias_promedio_en_etapa" radius={[6, 6, 0, 0]} maxBarSize={56}>
                    {etapas.map((e) => <Cell key={e.estado} fill={COLOR_ESTADO[e.estado].grafico} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Carga por juez</CardTitle>
            <CardDescription>Primero los despachos con plazos vencidos</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {!d && <Skeleton className="h-24 rounded-lg" />}
            {d && d.por_juez.length === 0 && <p className="text-muted-foreground py-6 text-center text-sm">No hay expedientes activos.</p>}
            {d?.por_juez.map((j) => {
              const max = Math.max(...d.por_juez.map((x) => x.activos), 1)
              return (
                <div key={j.juez_id ?? 'sin'} className="grid gap-1.5">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="flex-1 truncate font-medium">{j.juez}</span>
                    {j.vencidos > 0 && <span className="bg-destructive/10 text-destructive rounded-full px-2 text-xs font-semibold">{j.vencidos} vencido{j.vencidos > 1 ? 's' : ''}</span>}
                    <span className="w-6 text-right tabular-nums">{j.activos}</span>
                  </div>
                  <div className="bg-muted h-1.5 overflow-hidden rounded-full">
                    <div className={cn('h-full rounded-full', j.vencidos ? 'bg-destructive' : 'bg-primary')} style={{ width: `${(j.activos / max) * 100}%` }} />
                  </div>
                  <p className="text-muted-foreground text-xs">Antigüedad promedio: {dias(j.antiguedad_promedio_dias)}</p>
                </div>
              )
            })}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Expedientes activos más antiguos</CardTitle>
          <CardDescription>Los que más esperan; un clic abre el expediente</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Número</TableHead><TableHead>Materia</TableHead><TableHead>Estado</TableHead>
                <TableHead>Juez</TableHead><TableHead className="text-right">En la etapa</TableHead><TableHead className="text-right">Desde la radicación</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d?.mas_antiguos.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="font-mono text-xs"><Link to={`/expedientes/${e.id}`} className="hover:underline">{e.numero}</Link>
                    {e.vencido && <span className="bg-destructive/10 text-destructive ml-2 rounded-full px-1.5 text-[11px] font-semibold">vencido</span>}</TableCell>
                  <TableCell>{materia(e.materia)}</TableCell>
                  <TableCell><EstadoBadge estado={e.estado} /></TableCell>
                  <TableCell className="truncate">{e.juez}</TableCell>
                  <TableCell className="text-right tabular-nums">{dias(e.en_etapa_dias)}</TableCell>
                  <TableCell className="text-right font-medium tabular-nums">{dias(e.dias)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
