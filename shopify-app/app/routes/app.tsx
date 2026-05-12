import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { Link, Outlet, useLoaderData, useRouteError } from "@remix-run/react";
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
        <Link to={localizedPath("/app", locale)} rel="home">
          {t(locale, "dashboard")}
        </Link>
        <Link to={localizedPath("/app/review", locale)}>{t(locale, "review")}</Link>
        <Link to={localizedPath("/app/niche", locale)}>{t(locale, "niche")}</Link>
        <Link to={localizedPath("/app/onboarding", locale)}>
          {t(locale, "onboarding")}
        </Link>
        <Link to={localizedPath("/app/jobs", locale)}>{t(locale, "jobs")}</Link>
        <Link to={localizedPath("/app/billing", locale)}>{t(locale, "billing")}</Link>
        <Link to={localizedPath("/app/settings", locale)}>{t(locale, "settings")}</Link>
        <Link to={localizedPath("/app/privacy", locale)}>{t(locale, "privacy")}</Link>
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
