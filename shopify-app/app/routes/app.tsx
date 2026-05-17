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
        <a href={localizedPath("/app/audit", locale)}>{t(locale, "audit")}</a>
        <a href={localizedPath("/app/longtail", locale)}>{t(locale, "longtail")}</a>
        <a href={localizedPath("/app/cannibalization", locale)}>{t(locale, "cannibalization")}</a>
        <a href={localizedPath("/app/internal-links", locale)}>{t(locale, "internalLinks")}</a>
        <a href={localizedPath("/app/alt-text", locale)}>{t(locale, "altText")}</a>
        <a href={localizedPath("/app/descriptions", locale)}>{t(locale, "descriptions")}</a>
        <a href={localizedPath("/app/redirects", locale)}>{t(locale, "redirects")}</a>
        <a href={localizedPath("/app/jsonld", locale)}>{t(locale, "jsonld")}</a>
        <a href={localizedPath("/app/rollback", locale)}>{t(locale, "rollback")}</a>
        <a href={localizedPath("/app/reports", locale)}>{t(locale, "reports")}</a>
        <a href={localizedPath("/app/ga4", locale)}>{t(locale, "ga4")}</a>
        <a href={localizedPath("/app/semantics", locale)}>{t(locale, "semantics")}</a>
        <a href={localizedPath("/app/content", locale)}>{t(locale, "content")}</a>
        <a href={localizedPath("/app/hreflang", locale)}>{t(locale, "hreflang")}</a>
        <a href={localizedPath("/app/review", locale)}>{t(locale, "review")}</a>
        <a href={localizedPath("/app/niche", locale)}>{t(locale, "niche")}</a>
        <a href={localizedPath("/app/onboarding", locale)}>
          {t(locale, "onboarding")}
        </a>
        <a href={localizedPath("/app/jobs", locale)}>{t(locale, "jobs")}</a>
        <a href={localizedPath("/app/billing", locale)}>{t(locale, "billing")}</a>
        <a href={localizedPath("/app/settings", locale)}>{t(locale, "settings")}</a>
        <a href={localizedPath("/app/privacy", locale)}>{t(locale, "privacy")}</a>
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
