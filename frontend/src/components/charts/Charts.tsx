import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, AreaChart } from 'recharts';
import type { SeriesPoint } from '@/types';
import { Empty } from '@/components/ui/basic';

export const C_OK = '#1F4E85';
export const C_BAD = '#C0342A';
const GRID = '#EEE7DB';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function Tip({ active, payload, label, suffix = '' }: any) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload as SeriesPoint;
  return (
    <div className="tt">
      <b>{label}</b>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {payload.map((p: any) => (
        <div key={p.dataKey}><span className="dot" style={{ background: p.color, marginRight: 6 }} />{p.name}: {p.value === null || p.value === undefined ? '—' : `${p.value}${suffix}`}</div>
      ))}
      {point?.entries !== undefined && payload[0].dataKey === 'compliance' && <div style={{ opacity: 0.75 }}>{point.entries} entries</div>}
    </div>
  );
}

const hasData = (data: SeriesPoint[]) => data.some((d) => d.entries > 0);

/** Compliance rate over time (single series; filled area). */
export function ComplianceTrend({ data, height = 270, target = 98 }: { data: SeriesPoint[]; height?: number; target?: number }) {
  if (!hasData(data)) return <Empty title="No entries in this period yet" />;
  const min = Math.max(0, Math.floor(Math.min(...data.filter((d) => d.compliance !== null).map((d) => d.compliance as number), 90) / 5) * 5);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 14, left: -8, bottom: 0 }}>
        <defs><linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={C_OK} stopOpacity={0.18} /><stop offset="1" stopColor={C_OK} stopOpacity={0} /></linearGradient></defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={28} />
        <YAxis domain={[min, 100]} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} width={48} />
        <Tooltip content={<Tip suffix="%" />} cursor={{ stroke: '#C9BBA6' }} />
        {target > min && <ReferenceLine y={target} stroke="#B8894A" strokeDasharray="4 4" label={{ value: `Target ${target}%`, position: 'insideTopRight', fontSize: 11, fill: '#8B7E71' }} />}
        <Area type="monotone" dataKey="compliance" name="Compliance" stroke={C_OK} strokeWidth={2.25} fill="url(#trendFill)" connectNulls dot={false} activeDot={{ r: 4.5, strokeWidth: 2, stroke: '#fff' }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Successful vs failed entries per period (stacked bars). */
export function EntriesBars({ data, height = 270 }: { data: SeriesPoint[]; height?: number }) {
  if (!hasData(data)) return <Empty title="No entries in this period yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 10, right: 14, left: -14, bottom: 0 }} barCategoryGap="28%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip content={<Tip />} cursor={{ fill: 'rgba(51,39,31,.05)' }} />
        <Legend iconType="circle" iconSize={9} wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="passed" name="Successful" stackId="a" fill={C_OK} radius={[0, 0, 3, 3]} maxBarSize={28} />
        <Bar dataKey="failed" name="Failed" stackId="a" fill={C_BAD} radius={[3, 3, 0, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Daily compliance for several modules (one line each, with legend). */
export function ModuleLines({ series, height = 270 }: { series: { name: string; color: string; points: SeriesPoint[] }[]; height?: number }) {
  if (!series.length || !series.some((s) => hasData(s.points))) return <Empty title="No entries in this period yet" />;
  const rows = series[0].points.map((p, i) => {
    const row: Record<string, string | number | null> = { label: p.label };
    series.forEach((s) => { row[s.name] = s.points[i]?.compliance ?? null; });
    return row;
  });
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 10, right: 14, left: -8, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={28} />
        <YAxis domain={[(min: number) => Math.max(0, Math.floor(Math.min(min, 90) / 5) * 5), 100]} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} width={48} />
        <Tooltip content={<Tip suffix="%" />} cursor={{ stroke: '#C9BBA6' }} />
        <Legend iconType="circle" iconSize={9} wrapperStyle={{ fontSize: 12 }} />
        {series.map((s) => <Line key={s.name} type="monotone" dataKey={s.name} stroke={s.color} strokeWidth={2} dot={false} connectNulls activeDot={{ r: 4, strokeWidth: 2, stroke: '#fff' }} />)}
      </LineChart>
    </ResponsiveContainer>
  );
}
