import type { LoaderFunctionArgs } from "@remix-run/node";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", { status: 405 });
  }
  return new Response("ok", {
    status: 200,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
