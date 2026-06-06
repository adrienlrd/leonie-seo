import { Links, Meta, Outlet, Scripts, ScrollRestoration, useLoaderData } from "@remix-run/react";
import { json } from "@remix-run/node";
import type { LinksFunction } from "@remix-run/node";

export const links: LinksFunction = () => [];

// Exposes the (public) Shopify API key to every document so the App Bridge CDN
// script can be rendered in <head>. Runs for ALL routes (auth, errors, /app/*),
// so it must not call authenticate.admin — reading the env var is enough.
export const loader = async () => json({ apiKey: process.env.SHOPIFY_API_KEY || "" });

export default function App() {
  const { apiKey } = useLoaderData<typeof loader>();
  return (
    <html>
      <head>
        {/*
          Built for Shopify requires App Bridge to be the FIRST script in <head>
          (synchronous, no async/defer/module) so it initializes before paint and
          Shopify can measure Web Vitals (LCP/CLS/INP). It self-guards against double
          init, so AppProvider in app.tsx will not re-inject it once window.shopify exists.
          https://shopify.dev/docs/api/app-bridge-library
        */}
        <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js" data-api-key={apiKey} />
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width,initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        <Outlet />
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}
