/**
 * Shared server-side helpers for the product identification + market analysis flow.
 *
 * Extracted from app._index.tsx so app.onboarding.tsx (and any other route)
 * can drive the same identify/poll/save intents with identical backend
 * contracts (paths, payloads, response shapes).
 */

import { callBackendForShop } from "./api.server";
import type { MarketJobState } from "./marketAnalysisShared";

export async function startProductAnalysis(
  shop: string,
  accessToken: string | undefined,
): Promise<{ jobId: string | null; error: string | null }> {
  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/market-analysis/identify`, {
      accessToken,
      method: "POST",
    });
    if (!resp.ok) {
      const txt = await resp.text();
      return { jobId: null, error: `HTTP ${resp.status}: ${txt}` };
    }
    const data = (await resp.json()) as { job_id: string };
    return { jobId: data.job_id, error: null };
  } catch (err) {
    return { jobId: null, error: String(err) };
  }
}

export async function pollProductIdentification(
  shop: string,
  accessToken: string | undefined,
  identifyJobId: string,
): Promise<{ job: MarketJobState | null; error: string | null }> {
  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/market-analysis/jobs/${identifyJobId}`,
      { accessToken },
    );
    if (!resp.ok) return { job: null, error: `HTTP ${resp.status}` };
    const job = (await resp.json()) as MarketJobState;
    return { job, error: null };
  } catch (err) {
    return { job: null, error: String(err) };
  }
}

export async function saveProductIdentificationAndStartAnalysis(
  shop: string,
  accessToken: string | undefined,
  identifications: Record<string, string>,
): Promise<{ productJobId: string | null; error: string | null }> {
  try {
    const saveResp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/market-analysis/identifications`,
      {
        accessToken,
        method: "POST",
        body: JSON.stringify({ identifications }),
      },
    );
    if (!saveResp.ok) {
      const txt = await saveResp.text();
      return { productJobId: null, error: `HTTP ${saveResp.status}: ${txt}` };
    }

    const productResp = await callBackendForShop(shop, `/api/shops/${shop}/market-analysis/jobs`, {
      accessToken,
      method: "POST",
    });
    if (!productResp.ok) {
      const txt = await productResp.text();
      return { productJobId: null, error: `HTTP ${productResp.status}: ${txt}` };
    }
    const productData = (await productResp.json()) as { job_id: string };
    return { productJobId: productData.job_id, error: null };
  } catch (err) {
    return { productJobId: null, error: String(err) };
  }
}

export async function pollProductAnalysis(
  shop: string,
  accessToken: string | undefined,
  productJobId: string,
): Promise<{ job: MarketJobState | null; error: string | null }> {
  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/market-analysis/jobs/${productJobId}`,
      { accessToken },
    );
    if (!resp.ok) return { job: null, error: `HTTP ${resp.status}` };
    const job = (await resp.json()) as MarketJobState;
    return { job, error: null };
  } catch (err) {
    return { job: null, error: String(err) };
  }
}
