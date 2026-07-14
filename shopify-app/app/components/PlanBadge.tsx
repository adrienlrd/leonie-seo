import { Badge } from "@shopify/polaris";
import { useRouteLoaderData } from "@remix-run/react";
import type { Locale } from "../lib/i18n";

const PLAN_LABELS: Record<string, { fr: string; en: string }> = {
  free: { fr: "Gratuit", en: "Free" },
  pro: { fr: "Pro", en: "Pro" },
  agency: { fr: "Grande boutique", en: "Large store" },
};

/**
 * Plan badge shown next to each page title (Polaris `titleMetadata`).
 * Reads the plan from the parent `routes/app` loader, so no per-page loader change is needed.
 */
export function PlanBadge() {
  const data = useRouteLoaderData("routes/app") as { plan?: string; locale?: Locale } | undefined;
  const plan = data?.plan ?? "free";
  const fr = (data?.locale ?? "fr") === "fr";
  const label = PLAN_LABELS[plan] ?? PLAN_LABELS.free;
  return <Badge tone={plan === "free" ? undefined : "info"}>{fr ? label.fr : label.en}</Badge>;
}
