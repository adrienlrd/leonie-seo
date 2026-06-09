import type { LoaderFunctionArgs } from "@remix-run/node";
import { redirect } from "@remix-run/node";
import { getLocale, localizedPath } from "../lib/i18n";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  return redirect(localizedPath("/app/products", getLocale(request)));
};

export default function MarketAnalysisRedirect() {
  return null;
}
