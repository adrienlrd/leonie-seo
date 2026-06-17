import { json } from "@remix-run/node";
import { callBackendForShop } from "./api.server";

type Session = { shop: string; accessToken?: string };

/**
 * Handle the action intents fired by the shared `ProductCard` component
 * (apply, tags, keywords, enrichment questions, schema sync, proposal edits).
 *
 * Returns a Response when the intent is owned here, or `null` so the caller's
 * route action can fall through to its own intents. Used by both the Products
 * page and the dashboard so the same cards behave identically on either route.
 */
export async function handleProductCardIntent(
  intent: string,
  formData: FormData,
  session: Session,
): Promise<Response | null> {
  if (intent === "saveProposals") {
    const productId = formData.get("productId") as string;
    const proposalsRaw = formData.get("proposals") as string;
    try {
      const proposals = JSON.parse(proposalsRaw);
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/proposals/${encodeURIComponent(productId)}`,
        {
          accessToken: session.accessToken,
          method: "PATCH",
          body: JSON.stringify(proposals),
          signal: AbortSignal.timeout(10_000),
        },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ type: "saveProposals", error: `Erreur ${resp.status}: ${err}` });
      }
      return json({ type: "saveProposals", error: null });
    } catch (err) {
      return json({ type: "saveProposals", error: String(err) });
    }
  }

  if (intent === "syncSchemaFacts") {
    const productId = formData.get("productId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/proposals/${encodeURIComponent(productId)}/schema-facts/sync`,
        {
          accessToken: session.accessToken,
          method: "POST",
          signal: AbortSignal.timeout(15_000),
        },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ type: "syncSchemaFacts", error: `Erreur ${resp.status}: ${err}` });
      }
      const data = await resp.json();
      return json({ type: "syncSchemaFacts", error: null, data });
    } catch (err) {
      return json({ type: "syncSchemaFacts", error: String(err) });
    }
  }

  if (intent === "retireTag" || intent === "restoreTag") {
    const productId = formData.get("productId") as string;
    const tagId = formData.get("tagId") as string;
    const action = intent === "retireTag" ? "retire" : "restore";
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/products/${encodeURIComponent(productId)}/tags/${encodeURIComponent(tagId)}/${action}`,
      { accessToken: session.accessToken, method: "POST" },
    );
    const data = resp.ok ? await resp.json() : null;
    return json({ type: intent, ok: resp.ok, data });
  }

  if (intent === "addTag") {
    const productId = formData.get("productId") as string;
    const label = formData.get("label") as string;
    const tagType = (formData.get("tagType") as string) || "merchant";
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/products/${encodeURIComponent(productId)}/tags`,
      {
        accessToken: session.accessToken,
        method: "POST",
        body: JSON.stringify({ label, tag_type: tagType, status: "forced", locked_by_merchant: true }),
      },
    );
    const data = resp.ok ? await resp.json() : null;
    return json({ type: "addTag", ok: resp.ok, data });
  }

  if (intent === "retireKeyword") {
    const productId = formData.get("productId") as string;
    const label = formData.get("label") as string;
    const tagType = (formData.get("tagType") as string) || "keyword";
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/products/${encodeURIComponent(productId)}/tags`,
      {
        accessToken: session.accessToken,
        method: "POST",
        body: JSON.stringify({ label, tag_type: tagType, status: "negative", locked_by_merchant: true }),
      },
    );
    const data = resp.ok ? await resp.json() : null;
    return json({ type: "retireKeyword", ok: resp.ok, data });
  }

  if (intent === "validateQuestion") {
    const productId = String(formData.get("productId") ?? "");
    const key = String(formData.get("key") ?? "");
    const answer = String(formData.get("answer") ?? "");
    if (key && answer.trim()) {
      try {
        await callBackendForShop(
          session.shop,
          `/api/shops/${session.shop}/market-analysis/facts/${encodeURIComponent(productId)}`,
          {
            accessToken: session.accessToken,
            method: "POST",
            body: JSON.stringify({ answers: { [key]: answer } }),
            signal: AbortSignal.timeout(10_000),
          },
        );
      } catch { /* best-effort */ }
    }
    return json({ type: "validateQuestion", ok: true, error: null });
  }

  if (intent === "retireQuestion" || intent === "restoreQuestion") {
    const productId = String(formData.get("productId") ?? "");
    const key = String(formData.get("key") ?? "");
    const action = intent === "retireQuestion" ? "retire" : "restore";
    try {
      await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/products/${encodeURIComponent(productId)}/questions/${encodeURIComponent(key)}/${action}`,
        { accessToken: session.accessToken, method: "POST", signal: AbortSignal.timeout(10_000) },
      );
    } catch { /* best-effort */ }
    return json({ type: intent, ok: true, error: null });
  }

  if (intent === "setAutoPublishFields") {
    const productId = String(formData.get("productId") ?? "");
    const autoPublishFields = JSON.parse(String(formData.get("autoPublishFields") ?? "[]")) as string[];
    try {
      await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/proposals/${encodeURIComponent(productId)}`,
        {
          accessToken: session.accessToken,
          method: "PATCH",
          body: JSON.stringify({ auto_publish_fields: autoPublishFields }),
          signal: AbortSignal.timeout(10_000),
        },
      );
    } catch { /* best-effort */ }
    return json({ type: "setAutoPublishFields", ok: true });
  }

  if (intent === "applyToShopify") {
    const productId = String(formData.get("productId") ?? "");
    const fields = JSON.parse(String(formData.get("fields") ?? "[]")) as string[];
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/proposals/${encodeURIComponent(productId)}/apply-to-shopify`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify({ fields, confirm_live_write: true }),
          signal: AbortSignal.timeout(30_000),
        },
      );
      const data = await resp.json().catch(() => ({})) as { results?: Record<string, { applied: boolean; error: string | null }>; applied_fields?: Record<string, string>; detail?: string };
      return json({ type: "applyToShopify", ok: resp.ok, results: data.results ?? {}, applied_fields: data.applied_fields ?? {}, error: resp.ok ? null : (data.detail ?? `Backend ${resp.status}`) });
    } catch (err) {
      return json({ type: "applyToShopify", ok: false, results: {}, applied_fields: {}, error: String(err) });
    }
  }

  return null;
}
