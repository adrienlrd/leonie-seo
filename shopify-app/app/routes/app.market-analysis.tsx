import type { LoaderFunctionArgs } from "@remix-run/node";
import { redirect } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { getLocale } from "../lib/i18n";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  const locale = getLocale(request);
  const url = new URL(request.url);
  const params = new URLSearchParams(url.search);
  params.set("locale", locale);
  return redirect(`/app/products?${params.toString()}`);
};
