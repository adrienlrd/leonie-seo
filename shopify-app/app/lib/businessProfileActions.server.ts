/**
 * Shared server-side helpers for the business profile analysis flow.
 *
 * Extracted from app._index.tsx so app.onboarding.tsx (and any other route)
 * can drive the same analyze/poll/save intents with identical backend
 * contracts (paths, payloads, response shapes).
 */

import { callBackendForShop } from "./api.server";
import type { BusinessProfile } from "./marketAnalysisShared";

export async function startBusinessAnalysis(
  shop: string,
  accessToken: string | undefined,
  params: { shopName: string; focusKeywords: string[] },
): Promise<{ jobId: string | null; error: string | null }> {
  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/business-profile/analyze`,
      {
        accessToken,
        method: "POST",
        body: JSON.stringify({ shop_name: params.shopName, focus_keywords: params.focusKeywords }),
      },
    );
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

export async function pollBusinessAnalysis(
  shop: string,
  accessToken: string | undefined,
  bizJobId: string,
): Promise<{ status: string; profile: BusinessProfile | null; error: string | null }> {
  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/business-profile/job/${bizJobId}`,
      { accessToken },
    );
    if (!resp.ok) return { status: "unknown", profile: null, error: `HTTP ${resp.status}` };
    const job = (await resp.json()) as {
      status: string;
      profile?: BusinessProfile | null;
      error?: string | null;
    };
    const jobError =
      job.status === "failed" || job.status === "unknown" ? (job.error ?? "Analyse échouée") : null;
    return { status: job.status, profile: job.profile ?? null, error: jobError };
  } catch (err) {
    return { status: "unknown", profile: null, error: String(err) };
  }
}

export async function saveBusinessProfile(
  shop: string,
  accessToken: string | undefined,
  profile: BusinessProfile,
): Promise<{ profile: BusinessProfile | null; error: string | null }> {
  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/business-profile`, {
      accessToken,
      method: "POST",
      body: JSON.stringify(profile),
    });
    if (!resp.ok) {
      const txt = await resp.text();
      return { profile: null, error: `HTTP ${resp.status}: ${txt}` };
    }
    const saved = (await resp.json()) as BusinessProfile;
    return { profile: saved, error: null };
  } catch (err) {
    return { profile: null, error: String(err) };
  }
}

export async function saveBusinessProfileAndStartIdentification(
  shop: string,
  accessToken: string | undefined,
  profile: BusinessProfile,
): Promise<{ profile: BusinessProfile | null; identifyJobId: string | null; error: string | null }> {
  try {
    const saveResp = await callBackendForShop(shop, `/api/shops/${shop}/business-profile`, {
      accessToken,
      method: "POST",
      body: JSON.stringify(profile),
    });
    if (!saveResp.ok) {
      const txt = await saveResp.text();
      return { profile: null, identifyJobId: null, error: `HTTP ${saveResp.status}: ${txt}` };
    }
    const savedProfile = (await saveResp.json()) as BusinessProfile;

    const identifyResp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/market-analysis/identify`,
      { accessToken, method: "POST" },
    );
    if (!identifyResp.ok) {
      const txt = await identifyResp.text();
      return { profile: savedProfile, identifyJobId: null, error: `HTTP ${identifyResp.status}: ${txt}` };
    }
    const identifyData = (await identifyResp.json()) as { job_id: string };
    return { profile: savedProfile, identifyJobId: identifyData.job_id, error: null };
  } catch (err) {
    return { profile: null, identifyJobId: null, error: String(err) };
  }
}

/** Returns the validated/last-completed business profile, or null (404 / network error). */
export async function fetchLatestBusinessProfile(
  shop: string,
  accessToken: string | undefined,
): Promise<BusinessProfile | null> {
  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/business-profile/latest`, {
      accessToken,
    });
    if (!resp.ok) return null;
    return (await resp.json()) as BusinessProfile;
  } catch {
    return null;
  }
}
