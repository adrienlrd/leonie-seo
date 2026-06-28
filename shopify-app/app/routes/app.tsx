import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { Outlet, useLoaderData, useRouteError } from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";
import { AppProvider } from "@shopify/shopify-app-remix/react";
import { NavMenu } from "@shopify/app-bridge-react";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";
import { authenticate } from "../shopify.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { SupportChat } from "../components/SupportChat";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  return json({
    apiKey: process.env.SHOPIFY_API_KEY || "",
    locale: getLocale(request),
    // Optional support-chat widget (e.g. a Tawk.to embed URL). Empty → no widget.
    supportChatSrc: process.env.LEONIE_SUPPORT_CHAT_SRC || "",
    shop: session.shop,
  });
};

export default function App() {
  const { apiKey, locale, supportChatSrc, shop } = useLoaderData<typeof loader>() as {
    apiKey: string;
    locale: Locale;
    supportChatSrc: string;
    shop: string;
  };

  return (
    <AppProvider isEmbeddedApp apiKey={apiKey}>
      <SupportChat src={supportChatSrc} shop={shop} />
      <NavMenu>
        <a href={localizedPath("/app", locale)} rel="home">
          {t(locale, "dashboard")}
        </a>
        <a href={localizedPath("/app/products", locale)}>{t(locale, "navProducts")}</a>
        <a href={localizedPath("/app/blog", locale)}>Blog</a>
        <a href={localizedPath("/app/analyse", locale)}>{t(locale, "analyseNav")}</a>
        <a href={localizedPath("/app/measure", locale)}>{t(locale, "measureNav")}</a>
        <a href={localizedPath("/app/geo-llms-txt", locale)}>{t(locale, "llmsTxtTitle")}</a>
        <a href={localizedPath("/app/account", locale)}>{t(locale, "settings")}</a>
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
