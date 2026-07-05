/** Shared types for the onboarding step cards. */

export interface ShopStatus {
  installed: boolean;
  snapshot_available: boolean;
  product_count: number;
  collection_count: number;
  plan: string;
  can_apply: boolean;
}

export interface Health {
  status: string;
  missing_env: string[];
}

export interface GSCStatus {
  configured: boolean;
  connected: boolean;
  email: string | null;
  site_url: string;
  latest_import: {
    available: boolean;
    row_count: number;
    imported_at: string | null;
  };
  action_required: string | null;
}

export interface CrawlIssue {
  url: string;
  issue_type: string;
  severity: string;
  detail: string;
}

export interface CrawlStatus {
  available: boolean;
  url_count: number;
  issue_count: number;
  by_severity: Record<string, number>;
  issues: CrawlIssue[];
  imported_at: string | null;
}

export interface GA4Status {
  shop: string;
  oauth_connected: boolean;
  oauth_configured: boolean;
  email: string | null;
  property_id: string | null;
  property_name: string | null;
  ready: boolean;
  ga4_property_id_set: boolean;
  credentials_file_set: boolean;
}

export interface OnboardingActionData {
  jobId?: string;
  authorizationUrl?: string;
  disconnected?: boolean;
  ga4PropertySaved?: boolean;
  error?: string;
}

export interface GA4Property {
  property_id: string;
  property_name: string;
  account_name: string;
}
