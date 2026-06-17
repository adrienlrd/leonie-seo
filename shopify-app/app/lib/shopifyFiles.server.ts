import { json } from "@remix-run/node";

interface AdminClient {
  graphql(query: string, options?: { variables?: Record<string, unknown> }): Promise<Response>;
}

export interface ShopifyFile {
  id: string;
  url: string;
  alt: string;
  width: number | null;
  height: number | null;
}

interface PageInfo {
  hasNextPage: boolean;
  endCursor: string | null;
}

export interface BrowseFilesResult {
  type: "browseShopifyFiles";
  ok: boolean;
  files: ShopifyFile[];
  pageInfo: PageInfo;
  error: string | null;
}

export interface StagedUploadResult {
  type: "requestStagedUpload";
  ok: boolean;
  target: { url: string; resourceUrl: string; parameters: Array<{ name: string; value: string }> } | null;
  error: string | null;
}

export interface FileCreateResult {
  type: "createFileFromUpload";
  ok: boolean;
  file: ShopifyFile | null;
  error: string | null;
}

const FILES_QUERY = `
  query ShopifyFiles($first: Int!, $after: String, $query: String) {
    files(first: $first, after: $after, query: $query, sortKey: CREATED_AT, reverse: true) {
      edges {
        node {
          ... on MediaImage {
            id
            alt
            image { url width height }
          }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
`;

const STAGED_UPLOADS_CREATE = `
  mutation StagedUploadsCreate($input: [StagedUploadInput!]!) {
    stagedUploadsCreate(input: $input) {
      stagedTargets {
        url
        resourceUrl
        parameters { name value }
      }
      userErrors { field message }
    }
  }
`;

const FILE_CREATE = `
  mutation FileCreate($files: [FileCreateInput!]!) {
    fileCreate(files: $files) {
      files {
        ... on MediaImage {
          id
          fileStatus
          alt
          image { url width height }
        }
      }
      userErrors { field message }
    }
  }
`;

const FILE_STATUS_QUERY = `
  query FileStatus($id: ID!) {
    node(id: $id) {
      ... on MediaImage {
        id
        fileStatus
        alt
        image { url width height }
      }
    }
  }
`;

export async function handleShopifyFilesIntent(
  intent: string,
  formData: FormData,
  admin: AdminClient,
): Promise<Response | null> {
  if (intent === "browseShopifyFiles") {
    const search = String(formData.get("search") ?? "").trim();
    const after = formData.get("after") as string | null;
    const query = search ? `media_type:IMAGE ${search}` : "media_type:IMAGE";

    const res = await admin.graphql(FILES_QUERY, {
      variables: { first: 24, after: after || null, query },
    });
    const { data } = await res.json();
    const edges = data?.files?.edges ?? [];
    const files: ShopifyFile[] = edges
      .filter((e: any) => e.node?.image?.url)
      .map((e: any) => ({
        id: e.node.id,
        url: e.node.image.url,
        alt: e.node.alt ?? "",
        width: e.node.image.width ?? null,
        height: e.node.image.height ?? null,
      }));
    const pageInfo: PageInfo = data?.files?.pageInfo ?? { hasNextPage: false, endCursor: null };

    return json<BrowseFilesResult>({ type: "browseShopifyFiles", ok: true, files, pageInfo, error: null });
  }

  if (intent === "requestStagedUpload") {
    const filename = String(formData.get("filename") ?? "");
    const mimeType = String(formData.get("mimeType") ?? "image/jpeg");
    const fileSize = String(formData.get("fileSize") ?? "0");

    const res = await admin.graphql(STAGED_UPLOADS_CREATE, {
      variables: {
        input: [{ resource: "IMAGE", filename, mimeType, httpMethod: "POST", fileSize }],
      },
    });
    const { data } = await res.json();
    const errors = data?.stagedUploadsCreate?.userErrors ?? [];
    if (errors.length > 0) {
      return json<StagedUploadResult>({
        type: "requestStagedUpload",
        ok: false,
        target: null,
        error: errors.map((e: any) => e.message).join(", "),
      });
    }
    const target = data?.stagedUploadsCreate?.stagedTargets?.[0];
    if (!target) {
      return json<StagedUploadResult>({
        type: "requestStagedUpload",
        ok: false,
        target: null,
        error: "No staged target returned",
      });
    }
    return json<StagedUploadResult>({
      type: "requestStagedUpload",
      ok: true,
      target: { url: target.url, resourceUrl: target.resourceUrl, parameters: target.parameters },
      error: null,
    });
  }

  if (intent === "createFileFromUpload") {
    const resourceUrl = String(formData.get("resourceUrl") ?? "");
    const alt = String(formData.get("alt") ?? "");

    const res = await admin.graphql(FILE_CREATE, {
      variables: {
        files: [{ alt, originalSource: resourceUrl, contentType: "IMAGE" }],
      },
    });
    const { data } = await res.json();
    const errors = data?.fileCreate?.userErrors ?? [];
    if (errors.length > 0) {
      return json<FileCreateResult>({
        type: "createFileFromUpload",
        ok: false,
        file: null,
        error: errors.map((e: any) => e.message).join(", "),
      });
    }
    const created = data?.fileCreate?.files?.[0];
    if (!created) {
      return json<FileCreateResult>({
        type: "createFileFromUpload",
        ok: false,
        file: null,
        error: "No file returned",
      });
    }

    // Poll until READY (max 5 attempts, 1s apart)
    if (created.fileStatus !== "READY") {
      for (let i = 0; i < 5; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        const pollRes = await admin.graphql(FILE_STATUS_QUERY, {
          variables: { id: created.id },
        });
        const pollData = await pollRes.json();
        const node = pollData?.data?.node;
        if (node?.fileStatus === "READY" && node?.image?.url) {
          return json<FileCreateResult>({
            type: "createFileFromUpload",
            ok: true,
            file: {
              id: node.id,
              url: node.image.url,
              alt: node.alt ?? alt,
              width: node.image.width ?? null,
              height: node.image.height ?? null,
            },
            error: null,
          });
        }
        if (node?.fileStatus === "FAILED") {
          return json<FileCreateResult>({
            type: "createFileFromUpload",
            ok: false,
            file: null,
            error: "File processing failed",
          });
        }
      }
      return json<FileCreateResult>({
        type: "createFileFromUpload",
        ok: false,
        file: null,
        error: "File still processing — try again shortly",
      });
    }

    return json<FileCreateResult>({
      type: "createFileFromUpload",
      ok: true,
      file: {
        id: created.id,
        url: created.image?.url ?? "",
        alt: created.alt ?? alt,
        width: created.image?.width ?? null,
        height: created.image?.height ?? null,
      },
      error: null,
    });
  }

  return null;
}
