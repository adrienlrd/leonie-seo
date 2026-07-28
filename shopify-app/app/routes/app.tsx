import type { LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { Outlet, useLoaderData, useLocation, useNavigation, useRouteError } from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";
import { AppProvider } from "@shopify/shopify-app-remix/react";
import { NavMenu } from "@shopify/app-bridge-react";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { localizedPath, t, type Locale } from "../lib/i18n";
import { PageSkeleton } from "../components/PageSkeleton";
import { resolveLocale } from "../lib/i18n.server";
import { SupportChat } from "../components/SupportChat";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);

  const call = (path: string) =>
    callBackendForShop(session.shop, path, {
      accessToken: session.accessToken,
      signal: AbortSignal.timeout(3_000),
    });

  const [billingResp, onboardingResp] = await Promise.allSettled([
    call(`/api/shops/${session.shop}/billing/status`),
    call(`/api/shops/${session.shop}/onboarding/status`),
  ]);

  // Plan feeds the PlanBadge on every page title; the "Forfait" nav entry is
  // always visible.
  let plan = "free";
  try {
    if (billingResp.status === "fulfilled" && billingResp.value.ok) {
      const data = (await billingResp.value.json()) as { plan?: string };
      plan = data.plan ?? "free";
    }
  } catch {
    // backend unavailable → default to free (hides the Forfaits nag, shows Free badge)
  }

  // Until onboarding is done, this layout is the only gate: every app.* route
  // renders through it, so one check here covers them all. Fails open — a
  // backend hiccup must never lock the merchant out of the whole app.
  let onboardingComplete = true;
  try {
    if (onboardingResp.status === "fulfilled" && onboardingResp.value.ok) {
      const data = (await onboardingResp.value.json()) as { complete?: boolean };
      onboardingComplete = data.complete !== false;
    }
  } catch {
    // keep the app unlocked
  }

  const url = new URL(request.url);
  const locale = await resolveLocale(request, session.shop, session.accessToken, admin);
  if (!onboardingComplete && !url.pathname.endsWith("/onboarding")) {
    // Carry the embedded auth context (shop, host, embedded, id_token) — dropping
    // it makes the onboarding loader see a non-embedded request and bounce to
    // /auth/login, the "asks for shop domain" loop on fresh installs.
    const params = new URLSearchParams(url.searchParams);
    params.set("locale", locale);
    return redirect(`/app/onboarding?${params.toString()}`);
  }

  return json({
    onboardingComplete,
    apiKey: process.env.SHOPIFY_API_KEY || "",
    locale,
    // Optional support-chat widget (e.g. a Tawk.to embed URL). Empty → no widget.
    supportChatSrc: process.env.LEONIE_SUPPORT_CHAT_SRC || "",
    shop: session.shop,
    plan,
  });
};

export default function App() {
  const { apiKey, locale, supportChatSrc, shop, onboardingComplete } = useLoaderData<typeof loader>() as {
    apiKey: string;
    locale: Locale;
    supportChatSrc: string;
    shop: string;
    plan: string;
    onboardingComplete: boolean;
  };

  // Hide every secondary nav link until onboarding is done — their pages are
  // empty before the first analysis, and the loader redirects away from them
  // anyway. The rel="home" link must always stay — App Bridge requires it as
  // the app root.
  const location = useLocation();
  const onOnboarding = !onboardingComplete;
  const navigation = useNavigation();
  // Skeleton only for real page-to-page navigations; revalidations of the
  // current page (fetcher polls, save redirects to self) keep the live UI.
  const navigatingToNewPage =
    navigation.state === "loading" &&
    navigation.location != null &&
    navigation.location.pathname !== location.pathname;

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
      {navigatingToNewPage ? <PageSkeleton /> : <Outlet />}
    </AppProvider>
  );
}

export function ErrorBoundary() {
  const error = useRouteError();
  return boundary.error(error);
}

export const headers = boundary.headers;
