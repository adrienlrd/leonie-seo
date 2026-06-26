import { useCallback, useEffect, useRef, useState } from "react";
import { useFetcher } from "@remix-run/react";
import {
  Banner,
  BlockStack,
  Button,
  DropZone,
  InlineStack,
  Modal,
  ProgressBar,
  Spinner,
  Tabs,
  Text,
  TextField,
  Thumbnail,
} from "@shopify/polaris";
import type { Locale } from "../lib/i18n";
import { t } from "../lib/i18n";
import type { ShopifyFile, BrowseFilesResult, StagedUploadResult, FileCreateResult } from "../lib/shopifyFiles.server";

interface Props {
  locale: Locale;
  imageUrl: string | null;
  imageAlt: string | null;
  onSelect: (url: string, alt: string) => void;
  onAltChange: (alt: string) => void;
  onRemove: () => void;
  label?: string;
}

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB

export function ShopifyImagePicker({ locale, imageUrl, imageAlt, onSelect, onAltChange, onRemove, label }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <BlockStack gap="200">
      <Text as="h3" variant="headingSm">
        {label ?? (locale === "fr" ? "Image de couverture" : "Cover image")}
      </Text>

      {imageUrl ? (
        <BlockStack gap="200">
          <InlineStack gap="300" blockAlign="center">
            <div style={{ borderRadius: 8, overflow: "hidden", border: "1px solid var(--p-color-border)" }}>
              <img src={imageUrl} alt={imageAlt ?? ""} style={{ maxWidth: 200, maxHeight: 140, display: "block" }} />
            </div>
            <BlockStack gap="100">
              <Button size="slim" onClick={() => setOpen(true)}>{t(locale, "coverImageChange")}</Button>
              <Button size="slim" tone="critical" variant="plain" onClick={onRemove}>{t(locale, "coverImageRemove")}</Button>
            </BlockStack>
          </InlineStack>
          <TextField
            label={t(locale, "coverImageAlt")}
            value={imageAlt ?? ""}
            onChange={onAltChange}
            autoComplete="off"
            helpText={t(locale, "coverImageAltHelp")}
          />
        </BlockStack>
      ) : (
        <Button onClick={() => setOpen(true)}>{t(locale, "coverImageAdd")}</Button>
      )}

      {open && (
        <ImagePickerModal
          locale={locale}
          onClose={() => setOpen(false)}
          onSelect={(url, alt) => {
            onSelect(url, alt);
            setOpen(false);
          }}
        />
      )}
    </BlockStack>
  );
}

function ImagePickerModal({
  locale,
  onClose,
  onSelect,
}: {
  locale: Locale;
  onClose: () => void;
  onSelect: (url: string, alt: string) => void;
}) {
  const [tab, setTab] = useState(0);
  const [selected, setSelected] = useState<ShopifyFile | null>(null);

  const tabs = [
    { id: "browse", content: t(locale, "coverImageBrowse") },
    { id: "upload", content: t(locale, "coverImageUpload") },
  ];

  return (
    <Modal
      open
      onClose={onClose}
      title={locale === "fr" ? "Image de couverture" : "Cover image"}
      primaryAction={
        tab === 0 && selected
          ? { content: t(locale, "coverImageSelect"), onAction: () => onSelect(selected.url, selected.alt) }
          : undefined
      }
      secondaryActions={[{ content: locale === "fr" ? "Annuler" : "Cancel", onAction: onClose }]}
      size="large"
    >
      <Modal.Section>
        <Tabs tabs={tabs} selected={tab} onSelect={setTab}>
          {tab === 0 ? (
            <BrowseTab locale={locale} selected={selected} onSelect={setSelected} />
          ) : (
            <UploadTab locale={locale} onUploaded={onSelect} />
          )}
        </Tabs>
      </Modal.Section>
    </Modal>
  );
}

function BrowseTab({
  locale,
  selected,
  onSelect,
}: {
  locale: Locale;
  selected: ShopifyFile | null;
  onSelect: (f: ShopifyFile) => void;
}) {
  const fetcher = useFetcher<BrowseFilesResult>();
  const [search, setSearch] = useState("");
  const [files, setFiles] = useState<ShopifyFile[]>([]);
  const [pageInfo, setPageInfo] = useState<{ hasNextPage: boolean; endCursor: string | null }>({
    hasNextPage: false,
    endCursor: null,
  });
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const initialLoadDone = useRef(false);

  const load = useCallback(
    (searchVal: string, after?: string | null) => {
      const fd = new FormData();
      fd.set("intent", "browseShopifyFiles");
      fd.set("search", searchVal);
      if (after) fd.set("after", after);
      fetcher.submit(fd, { method: "post" });
    },
    [fetcher],
  );

  useEffect(() => {
    if (!initialLoadDone.current) {
      initialLoadDone.current = true;
      load("");
    }
  }, [load]);

  useEffect(() => {
    if (fetcher.data?.ok) {
      const isLoadMore = fetcher.data.pageInfo.endCursor && files.length > 0 &&
        fetcher.data.files.length > 0 && !fetcher.data.files.some((f) => files.some((ef) => ef.id === f.id));

      if (isLoadMore && fetcher.formData?.get("after")) {
        setFiles((prev) => [...prev, ...fetcher.data!.files]);
      } else {
        setFiles(fetcher.data.files);
      }
      setPageInfo(fetcher.data.pageInfo);
    }
  }, [fetcher.data]);

  const onSearchChange = useCallback(
    (val: string) => {
      setSearch(val);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        setFiles([]);
        load(val);
      }, 400);
    },
    [load],
  );

  const loading = fetcher.state !== "idle";

  return (
    <BlockStack gap="300">
      <div style={{ paddingTop: 12 }}>
        <TextField
          label=""
          labelHidden
          placeholder={t(locale, "coverImageSearch")}
          value={search}
          onChange={onSearchChange}
          autoComplete="off"
          clearButton
          onClearButtonClick={() => onSearchChange("")}
        />
      </div>

      {loading && files.length === 0 ? (
        <InlineStack align="center"><Spinner size="small" /></InlineStack>
      ) : files.length === 0 ? (
        <Text as="p" tone="subdued">{locale === "fr" ? "Aucune image trouvée" : "No images found"}</Text>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(100px, 1fr))",
            gap: 8,
            maxHeight: 400,
            overflowY: "auto",
            padding: "4px 0",
          }}
        >
          {files.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => onSelect(f)}
              style={{
                cursor: "pointer",
                border: selected?.id === f.id ? "2px solid var(--p-color-border-interactive)" : "2px solid transparent",
                borderRadius: 8,
                padding: 2,
                background: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Thumbnail source={f.url} alt={f.alt} size="large" />
            </button>
          ))}
        </div>
      )}

      {pageInfo.hasNextPage && (
        <InlineStack align="center">
          <Button
            onClick={() => load(search, pageInfo.endCursor)}
            loading={loading}
            size="slim"
          >
            {t(locale, "coverImageLoadMore")}
          </Button>
        </InlineStack>
      )}
    </BlockStack>
  );
}

function UploadTab({
  locale,
  onUploaded,
}: {
  locale: Locale;
  onUploaded: (url: string, alt: string) => void;
}) {
  const stageFetcher = useFetcher<StagedUploadResult>();
  const createFetcher = useFetcher<FileCreateResult>();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const pendingFileRef = useRef<File | null>(null);

  // Fetch gives no upload progress events, so simulate a climb to ~90% while the
  // upload + Shopify file processing run, then jump to 100% on completion.
  useEffect(() => {
    if (!uploading) {
      setProgress(0);
      return;
    }
    setProgress(10);
    const id = setInterval(
      () => setProgress((p) => (p < 90 ? p + Math.max(1, Math.round((90 - p) / 6)) : p)),
      350,
    );
    return () => clearInterval(id);
  }, [uploading]);

  const handleDrop = useCallback(
    (_dropped: File[], accepted: File[]) => {
      const file = accepted[0];
      if (!file) return;
      if (file.size > MAX_FILE_SIZE) {
        setError(t(locale, "coverImageTooLarge"));
        return;
      }
      setError(null);
      setUploading(true);
      pendingFileRef.current = file;

      const fd = new FormData();
      fd.set("intent", "requestStagedUpload");
      fd.set("filename", file.name);
      fd.set("mimeType", file.type || "image/jpeg");
      fd.set("fileSize", String(file.size));
      stageFetcher.submit(fd, { method: "post" });
    },
    [locale, stageFetcher],
  );

  // Step 2: once we have the staged target, upload the file directly
  useEffect(() => {
    if (!stageFetcher.data || stageFetcher.state !== "idle") return;
    if (!stageFetcher.data.ok || !stageFetcher.data.target) {
      setError(stageFetcher.data.error ?? t(locale, "coverImageError"));
      setUploading(false);
      return;
    }

    const file = pendingFileRef.current;
    if (!file) return;
    pendingFileRef.current = null;
    const target = stageFetcher.data.target;

    (async () => {
      try {
        const uploadForm = new FormData();
        for (const p of target.parameters) {
          uploadForm.append(p.name, p.value);
        }
        uploadForm.append("file", file);

        const uploadRes = await fetch(target.url, { method: "POST", body: uploadForm });
        if (!uploadRes.ok) {
          setError(t(locale, "coverImageError"));
          setUploading(false);
          return;
        }

        const fd = new FormData();
        fd.set("intent", "createFileFromUpload");
        fd.set("resourceUrl", target.resourceUrl);
        fd.set("alt", "");
        createFetcher.submit(fd, { method: "post" });
      } catch {
        setError(t(locale, "coverImageError"));
        setUploading(false);
      }
    })();
  }, [stageFetcher.data, stageFetcher.state, locale, createFetcher]);

  // Step 3: once the file is created, return the CDN URL
  useEffect(() => {
    if (!createFetcher.data || createFetcher.state !== "idle") return;
    setUploading(false);
    if (createFetcher.data.ok && createFetcher.data.file) {
      onUploaded(createFetcher.data.file.url, createFetcher.data.file.alt);
    } else {
      setError(createFetcher.data.error ?? t(locale, "coverImageError"));
    }
  }, [createFetcher.data, createFetcher.state, locale, onUploaded]);

  return (
    <BlockStack gap="300">
      <div style={{ paddingTop: 12 }}>
        {error && <Banner tone="critical" onDismiss={() => setError(null)}>{error}</Banner>}
        {uploading ? (
          <BlockStack gap="200">
            <InlineStack gap="200" blockAlign="center">
              <Spinner size="small" />
              <Text as="span">{t(locale, "coverImageUploading")}</Text>
            </InlineStack>
            <ProgressBar progress={progress} size="small" tone="primary" />
          </BlockStack>
        ) : (
          <DropZone
            accept="image/*"
            type="image"
            onDrop={handleDrop}
            allowMultiple={false}
          >
            <DropZone.FileUpload actionHint={t(locale, "coverImageDropHint")} />
          </DropZone>
        )}
      </div>
    </BlockStack>
  );
}
