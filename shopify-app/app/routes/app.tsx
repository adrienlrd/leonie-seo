import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { Outlet, useLoaderData, useRouteError } from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";
import { AppProvider } from "@shopify/shopify-app-remix/react";
import { NavMenu } from "@shopify/app-bridge-react";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";
import { authenticate } from "../shopify.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return json({ apiKey: process.env.SHOPIFY_API_KEY || "", locale: getLocale(request) });
};

export default function App() {
  const { apiKey, locale } = useLoaderData<typeof loader>() as {
    apiKey: string;
    locale: Locale;
  };

  return (
    <AppProvider isEmbeddedApp apiKey={apiKey}>
      <NavMenu>
        <a href={localizedPath("/app", locale)} rel="home">
          {t(locale, "dashboard")}
        </a>
        <a href={localizedPath("/app/audit-hub", locale)}>{t(locale, "hubAudit")}</a>
        <a href={localizedPath("/app/safe-apply", locale)}>{t(locale, "hubOptimization")}</a>
        <a href={localizedPath("/app/impact", locale)}>{t(locale, "hubInsights")}</a>
        <a href={localizedPath("/app/account", locale)}>{t(locale, "hubSettings")}</a>
      </NavMenu>
      <Outlet />
    </AppProvider>
  );
}

export function ErrorBoundary() {
  const error = useRouteError();
  return boundary.error(error);
}

export const headers = boundary.headers;
