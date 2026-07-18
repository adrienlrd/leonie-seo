import { Badge } from "@shopify/polaris";
import { useRouteLoaderData } from "@remix-run/react";
import type { Locale } from "../lib/i18n";
import { t } from "../lib/i18n";

const PLAN_LABEL_KEYS: Record<string, string> = {
  free: "pbFree",
  pro: "pbPro",
  agency: "pbAgency",
};

/**
 * Plan badge shown next to each page title (Polaris `titleMetadata`).
 * Reads the plan from the parent `routes/app` loader, so no per-page loader change is needed.
 */
export function PlanBadge() {
  const data = useRouteLoaderData("routes/app") as { plan?: string; locale?: Locale } | undefined;
  const plan = data?.plan ?? "free";
  const locale = data?.locale ?? "fr";
  const labelKey = PLAN_LABEL_KEYS[plan] ?? PLAN_LABEL_KEYS.free;
  return <Badge tone={plan === "free" ? undefined : "info"}>{t(locale, labelKey)}</Badge>;
}
