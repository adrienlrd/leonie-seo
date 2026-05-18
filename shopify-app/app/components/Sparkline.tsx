import { Text } from "@shopify/polaris";

interface SparklinePoint {
  date: string;
  value: number;
}

interface SparklineProps {
  data: SparklinePoint[];
  label: string;
  width?: number;
  height?: number;
  color?: string;
  invertY?: boolean;
  formatValue?: (value: number) => string;
}

export function Sparkline({
  data,
  label,
  width = 320,
  height = 80,
  color = "#008060",
  invertY = false,
  formatValue,
}: SparklineProps) {
  const formatter = formatValue ?? ((v: number) => String(v));

  if (data.length === 0) {
    return (
      <div style={{ minHeight: height }}>
        <Text as="p" variant="bodySm" tone="subdued">
          {label} — aucune donnée sur la période
        </Text>
      </div>
    );
  }

  const values = data.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const padding = 4;
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;

  const points = data.map((point, index) => {
    const x =
      data.length === 1
        ? padding + innerWidth / 2
        : padding + (index / (data.length - 1)) * innerWidth;
    const normalized = (point.value - min) / range;
    const ratio = invertY ? normalized : 1 - normalized;
    const y = padding + ratio * innerHeight;
    return { x, y, value: point.value, date: point.date };
  });

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");
  const last = points[points.length - 1];

  return (
    <div>
      <Text as="p" variant="bodySm" tone="subdued">
        {label}
      </Text>
      <Text as="p" variant="headingLg">
        {formatter(last.value)}
      </Text>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${label}: ${data.length} points`}
        style={{ display: "block" }}
      >
        <path d={path} fill="none" stroke={color} strokeWidth={2} />
        {points.map((p) => (
          <circle key={`${p.date}-${p.x}`} cx={p.x} cy={p.y} r={2.5} fill={color} />
        ))}
      </svg>
      <Text as="p" variant="bodySm" tone="subdued">
        {data[0].date} → {last.date} · min {formatter(min)} · max {formatter(max)}
      </Text>
    </div>
  );
}
