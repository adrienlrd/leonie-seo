import type { LoaderFunctionArgs } from "@remix-run/node";
import { redirect } from "@remix-run/node";
import { getLocale, localizedPath } from "../lib/i18n";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  return redirect(localizedPath("/app/account", getLocale(request)));
};

export default function GeoLlmsTxtRedirect() {
  return null;
}
