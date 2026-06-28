import { useEffect } from "react";

/**
 * Merchant → developer support chat (bottom-right of the embedded app).
 *
 * Loads a third-party chat widget (Tawk.to by default — free, you reply from its
 * web/mobile dashboard) only when `src` is provided. The widget's online hours and
 * offline "leave a message" behaviour are configured in the Tawk.to dashboard, so
 * there is nothing business-hours-specific to hardcode here.
 *
 * `src` is the embed URL from Tawk.to, e.g. https://embed.tawk.to/<property>/<widget>.
 * `shop` identifies which merchant is writing in the agent inbox.
 */
export function SupportChat({ src, shop }: { src: string; shop: string }) {
  useEffect(() => {
    if (!src || typeof window === "undefined") return;
    if (document.getElementById("leonie-support-chat")) return; // load once

    const w = window as unknown as Record<string, unknown>;
    w.Tawk_API = (w.Tawk_API as Record<string, unknown>) || {};
    // Pre-fill the visitor name with the shop so you know who is contacting you.
    (w.Tawk_API as Record<string, unknown>).visitor = { name: shop };
    w.Tawk_LoadStart = new Date();

    const script = document.createElement("script");
    script.id = "leonie-support-chat";
    script.async = true;
    script.src = src;
    script.charset = "UTF-8";
    script.setAttribute("crossorigin", "*");
    document.body.appendChild(script);
  }, [src, shop]);

  return null;
}
