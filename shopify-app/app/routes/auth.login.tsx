import { useState } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { Form, useActionData, useLoaderData } from "@remix-run/react";
import {
  AppProvider as PolarisAppProvider,
  Button,
  Card,
  FormLayout,
  Page,
  Text,
  TextField,
} from "@shopify/polaris";
import polarisTranslations from "@shopify/polaris/locales/en.json";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";

import { login } from "../shopify.server";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

interface LoginErrors {
  shop?: string;
}

function loginErrorMessage(loginErrors: LoginErrors): LoginErrors {
  if (loginErrors?.shop === "MISSING_SHOP") {
    return { shop: "Please enter your shop domain to log in" };
  }
  if (loginErrors?.shop === "INVALID_SHOP") {
    return { shop: "Please enter a valid shop domain to log in" };
  }
  return {};
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const errors = loginErrorMessage((await login(request)) as LoginErrors);
  return json({ errors, polarisTranslations });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const errors = loginErrorMessage((await login(request)) as LoginErrors);
  return json({ errors });
};

export default function Auth() {
  const loaderData = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const [shop, setShop] = useState("");
  const errors = actionData?.errors ?? loaderData.errors;

  return (
    <PolarisAppProvider i18n={loaderData.polarisTranslations}>
      <Page>
        <Card>
          <Form method="post">
            <FormLayout>
              <Text variant="headingMd" as="h2">
                Log in
              </Text>
              <TextField
                type="text"
                name="shop"
                label="Shop domain"
                helpText="example.myshopify.com"
                value={shop}
                onChange={setShop}
                autoComplete="on"
                error={errors.shop}
              />
              <Button submit>Log in</Button>
            </FormLayout>
          </Form>
        </Card>
      </Page>
    </PolarisAppProvider>
  );
}
