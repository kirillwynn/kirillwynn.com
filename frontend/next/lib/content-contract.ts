export type Rendition = {
    url: string;
    width: number;
    height: number;
};

export type ContentImage = {
    id: number;
    title: string;
    alt: string;
    decorative: boolean;
    width: number;
    height: number;
    renditions: Record<"480w" | "960w" | "1440w", Rendition>;
};

type Block<TType extends string, TValue> = {
    id: string;
    type: TType;
    value: TValue;
};

export type ContentBlock =
    | Block<"rich_text", { html: string }>
    | Block<"heading", { level: "h2" | "h3" | "h4"; text: string }>
    | Block<"image", ContentImage>
    | Block<"gallery", { images: ContentImage[] }>
    | Block<"quote", { text: string; attribution: string | null }>
    | Block<"bulleted_list", { items: string[] }>
    | Block<"numbered_list", { items: string[] }>
    | Block<"checklist", { items: Array<{ text: string; checked: boolean }> }>
    | Block<"inline_code", { code: string }>
    | Block<"code_block", { language: string; code: string }>
    | Block<
          "table",
          { rows: string[][]; header: { row: boolean; column: boolean } }
      >
    | Block<"horizontal_divider", Record<string, never>>
    | Block<
          "link",
          {
              text: string;
              kind: "internal" | "external";
              href: string | null;
              target: { id: number; type: string; slug: string } | null;
          }
      >;

export type PostDetail = {
    api_version: "1.0";
    id: number;
    slug: string;
    title: string;
    excerpt: string;
    published_at: string | null;
    updated_at: string | null;
    tags: Array<{ name: string; slug: string }>;
    canonical_path: string;
    canonical_url: string;
    seo: { title: string; description: string };
    open_graph: {
        title: string;
        description: string;
        image: ContentImage | null;
    };
    body: ContentBlock[];
};
