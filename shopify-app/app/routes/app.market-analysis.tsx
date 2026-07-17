import type { LoaderFunctionArgs } from "@remix-run/node";
import { redirect } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { resolveLocale } from "../lib/i18n.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = await resolveLocale(request, session.shop, session.accessToken);
  const url = new URL(request.url);
  const params = new URLSearchParams(url.search);
  params.set("locale", locale);
  return redirect(`/app/products?${params.toString()}`);
};
