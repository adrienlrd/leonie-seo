import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { Outlet, useLoaderData, useLocation, useRouteError } from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";
import { AppProvider } from "@shopify/shopify-app-remix/react";
import { NavMenu } from "@shopify/app-bridge-react";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { localizedPath, t, type Locale } from "../lib/i18n";
import { resolveLocale } from "../lib/i18n.server";
import { SupportChat } from "../components/SupportChat";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);

  // Plan feeds the PlanBadge on every page title; the "Forfait" nav entry is
  // always visible.
  let plan = "free";
  try {
    const resp = await callBackendForShop(session.shop, `/api/shops/${session.shop}/billing/status`, {
      accessToken: session.accessToken,
      signal: AbortSignal.timeout(3_000),
    });
    if (resp.ok) {
      const data = (await resp.json()) as { plan?: string };
      plan = data.plan ?? "free";
    }
  } catch {
    // backend unavailable → default to free (hides the Forfaits nag, shows Free badge)
  }

  return json({
    apiKey: process.env.SHOPIFY_API_KEY || "",
    locale: await resolveLocale(request, session.shop, session.accessToken, admin),
    // Optional support-chat widget (e.g. a Tawk.to embed URL). Empty → no widget.
    supportChatSrc: process.env.LEONIE_SUPPORT_CHAT_SRC || "",
    shop: session.shop,
    plan,
  });
};

export default function App() {
  const { apiKey, locale, supportChatSrc, shop } = useLoaderData<typeof loader>() as {
    apiKey: string;
    locale: Locale;
    supportChatSrc: string;
    shop: string;
    plan: string;
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
        {!onOnboarding && (
          <a href={localizedPath("/app/billing", locale)}>{t(locale, "navPlans")}</a>
        )}
        {!onOnboarding && <a href={localizedPath("/app/account", locale)}>{t(locale, "settings")}</a>}
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
