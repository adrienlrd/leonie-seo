import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { useLoaderData, useSubmit } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackend } from "../lib/api.server";

interface Plan {
  id: string;
  name: string;
  price: number;
  currency: string;
  interval: string;
  features: string[];
  current: boolean;
}

interface LoaderData {
  shop: string;
  plans: Plan[];
  currentPlan: string;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;

  let plans: Plan[] = [];
  let currentPlan = "free";
  try {
    const resp = await callBackend(`/api/shops/${shop}/billing/plans`);
    if (resp.ok) {
      const data = await resp.json() as { plans: Plan[]; current_plan: string };
      plans = data.plans;
      currentPlan = data.current_plan ?? "free";
    }
  } catch {
    // Python backend unavailable
  }

  return json<LoaderData>({ shop, plans, currentPlan });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;

  const formData = await request.formData();
  const planId = formData.get("plan") as string;
  const intent = formData.get("intent") as string;

  if (intent === "cancel") {
    await callBackend(`/api/shops/${shop}/billing/cancel`, { method: "POST" });
    return redirect("/app/billing");
  }

  try {
    const resp = await callBackend(`/api/shops/${shop}/billing/subscribe`, {
      method: "POST",
      body: JSON.stringify({ plan: planId }),
    });
    const data = await resp.json() as { confirmation_url: string };
    if (data.confirmation_url) {
      return redirect(data.confirmation_url);
    }
  } catch {
    // error handled by redirect back
  }
  return redirect("/app/billing");
};

export default function Billing() {
  const { plans, currentPlan } = useLoaderData<typeof loader>();
  const submit = useSubmit();

  return (
    <Page title="Facturation" backAction={{ content: "Dashboard", url: "/app" }}>
      <BlockStack gap="500">
        <Text as="p" tone="subdued">
          Plan actuel : <strong>{currentPlan}</strong>
        </Text>

        <InlineGrid columns={plans.length > 0 ? String(plans.length) as "3" : "1"} gap="400">
          {plans.map((plan) => (
            <Card key={plan.id}>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">
                  {plan.name}{" "}
                  {plan.current && <Badge tone="success">Actuel</Badge>}
                </Text>
                <Text as="p" variant="headingLg">
                  {plan.price === 0 ? "Gratuit" : `${plan.price} ${plan.currency}/${plan.interval}`}
                </Text>
                <BlockStack gap="100">
                  {(plan.features ?? []).map((f) => (
                    <Text key={f} as="p" variant="bodySm">
                      ✓ {f}
                    </Text>
                  ))}
                </BlockStack>
                {!plan.current && plan.id !== "free" && (
                  <Button
                    variant="primary"
                    onClick={() =>
                      submit({ plan: plan.id }, { method: "post" })
                    }
                  >
                    Choisir {plan.name}
                  </Button>
                )}
                {plan.current && plan.id !== "free" && (
                  <Button
                    variant="plain"
                    tone="critical"
                    onClick={() =>
                      submit({ intent: "cancel" }, { method: "post" })
                    }
                  >
                    Annuler l&apos;abonnement
                  </Button>
                )}
              </BlockStack>
            </Card>
          ))}
        </InlineGrid>

        {plans.length === 0 && (
          <Card>
            <Text as="p" tone="subdued">
              Impossible de charger les plans. Vérifiez que le moteur SEO est démarré.
            </Text>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
