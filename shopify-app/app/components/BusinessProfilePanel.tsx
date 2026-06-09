import { useState } from "react";
import { BlockStack, Card, InlineGrid, Text, TextField } from "@shopify/polaris";
import type { Locale } from "../lib/i18n";
import { t } from "../lib/i18n";

export interface BusinessPersona {
  name?: string;
  description?: string;
  main_need?: string;
  buying_trigger?: string;
}

export interface BusinessProfile {
  niche_summary?: string;
  brand_name?: string;
  brand_voice?: string;
  target_personas?: BusinessPersona[];
  competitor_domains?: string[];
  competitor_insights?: string[];
  key_themes?: string[];
  status?: string;
}

function lines(value?: string[]): string {
  return (value ?? []).join("\n");
}

export function BusinessProfilePanel({ profile, locale }: { profile: BusinessProfile | null; locale: Locale }) {
  const [nicheSummary, setNicheSummary] = useState(profile?.niche_summary ?? "");
  const [brandName, setBrandName] = useState(profile?.brand_name ?? "");
  const [brandVoice, setBrandVoice] = useState(profile?.brand_voice ?? "");
  const [personas, setPersonas] = useState((profile?.target_personas ?? [])
    .map((persona) => [persona.name, persona.description, persona.main_need, persona.buying_trigger].filter(Boolean).join(" — "))
    .join("\n"));
  const [competitors, setCompetitors] = useState(lines(profile?.competitor_domains));
  const [themes, setThemes] = useState(lines(profile?.key_themes));

  return (
    <Card>
      <BlockStack gap="300">
        <Text as="h2" variant="headingMd">{t(locale, "onboardingProfileTitle")}</Text>
        <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
          <TextField label={t(locale, "businessProfileNicheSummary")} name="niche_summary" value={nicheSummary} onChange={setNicheSummary} multiline={4} autoComplete="off" />
          <BlockStack gap="300">
            <TextField label={t(locale, "onboardingBrandName")} name="brand_name" value={brandName} onChange={setBrandName} autoComplete="off" />
            <TextField label={t(locale, "businessProfileBrandVoice")} name="brand_voice" value={brandVoice} onChange={setBrandVoice} multiline={3} autoComplete="off" />
          </BlockStack>
        </InlineGrid>
        <TextField label={t(locale, "businessProfilePersonas")} name="target_personas_text" value={personas} onChange={setPersonas} helpText={t(locale, "onboardingOneItemPerLine")} multiline={5} autoComplete="off" />
        <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
          <TextField label={t(locale, "onboardingCompetitors")} name="competitor_domains_text" value={competitors} onChange={setCompetitors} helpText={t(locale, "onboardingOneItemPerLine")} multiline={4} autoComplete="off" />
          <TextField label={t(locale, "businessProfileKeyThemes")} name="key_themes_text" value={themes} onChange={setThemes} helpText={t(locale, "onboardingOneItemPerLine")} multiline={4} autoComplete="off" />
        </InlineGrid>
      </BlockStack>
    </Card>
  );
}
