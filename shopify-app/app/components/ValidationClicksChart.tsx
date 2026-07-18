import { Text } from "@shopify/polaris";

export interface ClicksSeriesPoint {
  day: number;
  date: string;
  total: number | null;
  future: boolean;
}

interface ValidationClicksChartProps {
  series: ClicksSeriesPoint[];
  label: string;
  emptyLabel: string;
  locale: string;
  width?: number;
  height?: number;
  color?: string;
}

const WINDOW_DAYS = 28;

// Daily Google + AI organic clicks over the 28-day measurement window that starts
// at the last validation. Past/present days are drawn as a solid line; days that
// haven't happened yet extend as a dashed horizontal line at the last known level.
export function ValidationClicksChart({
  series,
  label,
  emptyLabel,
  locale,
  width = 480,
  height = 120,
  color = "#008060",
}: ValidationClicksChartProps) {
  const numberLocale = { fr: "fr-FR", en: "en-US", de: "de-DE", es: "es-ES" }[locale];

  if (!series || series.length === 0) {
    return (
      <div style={{ minHeight: 40 }}>
        <Text as="p" variant="bodySm" tone="subdued">
          {emptyLabel}
        </Text>
      </div>
    );
  }

  const padding = 8;
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;

  const xFor = (day: number) =>
    padding + ((day - 1) / (WINDOW_DAYS - 1)) * innerWidth;

  const real = series.filter((p) => !p.future && p.total !== null);
  const maxVal = Math.max(1, ...real.map((p) => p.total ?? 0));
  const yFor = (value: number) =>
    padding + (1 - value / maxVal) * innerHeight;

  const solidPath = real
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(p.day).toFixed(1)} ${yFor(p.total ?? 0).toFixed(1)}`)
    .join(" ");

  const lastReal = real[real.length - 1];
  const hasFuture = series.some((p) => p.future);
  const totalClicks = real.reduce((sum, p) => sum + (p.total ?? 0), 0);

  return (
    <div>
      <Text as="p" variant="bodySm" tone="subdued">
        {label} · {totalClicks.toLocaleString(numberLocale)}
      </Text>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={label}
        style={{ display: "block", maxWidth: width }}
      >
        <line
          x1={padding}
          y1={yFor(0)}
          x2={width - padding}
          y2={yFor(0)}
          stroke="#E1E3E5"
          strokeWidth={1}
        />
        {hasFuture && lastReal ? (
          <line
            x1={xFor(lastReal.day)}
            y1={yFor(lastReal.total ?? 0)}
            x2={xFor(WINDOW_DAYS)}
            y2={yFor(lastReal.total ?? 0)}
            stroke={color}
            strokeWidth={2}
            strokeDasharray="4 4"
            opacity={0.6}
          />
        ) : null}
        <path d={solidPath} fill="none" stroke={color} strokeWidth={2} />
        {real.map((p) => (
          <circle
            key={p.date}
            cx={xFor(p.day)}
            cy={yFor(p.total ?? 0)}
            r={2}
            fill={color}
          >
            <title>{`${p.date}: ${(p.total ?? 0).toLocaleString(numberLocale)}`}</title>
          </circle>
        ))}
      </svg>
      <Text as="p" variant="bodySm" tone="subdued">
        {`${series[0].date} → ${series[series.length - 1].date}`}
      </Text>
    </div>
  );
}
