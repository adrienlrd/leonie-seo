import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { Outlet, useLoaderData, useLocation, useRouteError } from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";
import { AppProvider } from "@shopify/shopify-app-remix/react";
import { NavMenu } from "@shopify/app-bridge-react";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { SupportChat } from "../components/SupportChat";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // "Forfaits" nav entry is shown only to free-plan merchants. Fail closed
  // (hidden) on backend timeout so the nav never nags paying merchants.
  let isFreePlan = false;
  try {
    const resp = await callBackendForShop(session.shop, `/api/shops/${session.shop}/billing/status`, {
      accessToken: session.accessToken,
      signal: AbortSignal.timeout(3_000),
    });
    if (resp.ok) {
      const data = (await resp.json()) as { plan?: string };
      isFreePlan = data.plan === "free";
    }
  } catch {
    // backend unavailable → keep the link hidden
  }

  return json({
    apiKey: process.env.SHOPIFY_API_KEY || "",
    locale: getLocale(request),
    // Optional support-chat widget (e.g. a Tawk.to embed URL). Empty → no widget.
    supportChatSrc: process.env.LEONIE_SUPPORT_CHAT_SRC || "",
    shop: session.shop,
    isFreePlan,
  });
};

export default function App() {
  const { apiKey, locale, supportChatSrc, shop, isFreePlan } = useLoaderData<typeof loader>() as {
    apiKey: string;
    locale: Locale;
    supportChatSrc: string;
    shop: string;
    isFreePlan: boolean;
  };

  // Hide the secondary nav links while the merchant is on the onboarding screen
  // (their target pages are empty until setup completes). The rel="home" link
  // must always stay — App Bridge requires it as the app root.
  const onOnboarding = useLocation().pathname.endsWith("/onboarding");

  return (
    <AppProvider isEmbeddedApp apiKey={apiKey}>
      <SupportChat src={supportChatSrc} shop={shop} />
      <NavMenu>
        <a href={localizedPath("/app", locale)} rel="home">
          {t(locale, "dashboard")}
        </a>
        {!onOnboarding && <a href={localizedPath("/app/products", locale)}>{t(locale, "navProducts")}</a>}
        {!onOnboarding && <a href={localizedPath("/app/blog", locale)}>Blog</a>}
        {!onOnboarding && <a href={localizedPath("/app/analyse", locale)}>{t(locale, "analyseNav")}</a>}
        {!onOnboarding && <a href={localizedPath("/app/geo-llms-txt", locale)}>{t(locale, "llmsTxtTitle")}</a>}
        {!onOnboarding && <a href={localizedPath("/app/account", locale)}>{t(locale, "settings")}</a>}
        {!onOnboarding && isFreePlan && (
          <a href={localizedPath("/app/billing", locale)}>{locale === "fr" ? "Forfaits" : "Plans"}</a>
        )}
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
