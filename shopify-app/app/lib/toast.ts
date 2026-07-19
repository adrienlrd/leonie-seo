/** App Bridge v4 toast — window.shopify.toast, typed once here. */
export function showToast(message: string): void {
  if (typeof window === "undefined") return;
  (window as { shopify?: { toast?: { show: (m: string) => void } } }).shopify?.toast?.show(
    message,
  );
}
