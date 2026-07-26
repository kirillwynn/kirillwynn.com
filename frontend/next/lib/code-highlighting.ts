export type HighlightToken = {
    text: string;
    kind: "plain" | "comment" | "string" | "number" | "keyword" | "literal";
};

export type HighlightedCode = {
    language: string;
    supported: boolean;
    tokens: HighlightToken[];
};

type LanguageDefinition = {
    aliases: string[];
    keywords: Set<string>;
    hashComments?: boolean;
};

const definitions: Record<string, LanguageDefinition> = {
    javascript: {
        aliases: ["javascript", "js", "jsx"],
        keywords: new Set([
            "async",
            "await",
            "break",
            "case",
            "catch",
            "class",
            "const",
            "continue",
            "default",
            "else",
            "export",
            "extends",
            "finally",
            "for",
            "from",
            "function",
            "if",
            "import",
            "in",
            "let",
            "new",
            "of",
            "return",
            "static",
            "switch",
            "throw",
            "try",
            "typeof",
            "var",
            "while",
            "yield",
        ]),
    },
    typescript: {
        aliases: ["typescript", "ts", "tsx"],
        keywords: new Set([
            "as",
            "async",
            "await",
            "class",
            "const",
            "else",
            "enum",
            "export",
            "extends",
            "function",
            "if",
            "implements",
            "import",
            "interface",
            "keyof",
            "let",
            "namespace",
            "new",
            "private",
            "protected",
            "public",
            "readonly",
            "return",
            "satisfies",
            "static",
            "throw",
            "type",
            "typeof",
        ]),
    },
    python: {
        aliases: ["python", "py"],
        hashComments: true,
        keywords: new Set([
            "and",
            "as",
            "async",
            "await",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "nonlocal",
            "not",
            "or",
            "pass",
            "raise",
            "return",
            "try",
            "while",
            "with",
            "yield",
        ]),
    },
    bash: {
        aliases: ["bash", "sh", "shell", "zsh"],
        hashComments: true,
        keywords: new Set([
            "case",
            "do",
            "done",
            "elif",
            "else",
            "esac",
            "export",
            "fi",
            "for",
            "function",
            "if",
            "in",
            "local",
            "then",
            "while",
        ]),
    },
    json: {
        aliases: ["json"],
        keywords: new Set(),
    },
    css: {
        aliases: ["css"],
        keywords: new Set(["@container", "@font-face", "@import", "@media"]),
    },
    sql: {
        aliases: ["sql"],
        keywords: new Set([
            "alter",
            "and",
            "as",
            "by",
            "create",
            "delete",
            "distinct",
            "drop",
            "from",
            "group",
            "having",
            "insert",
            "into",
            "join",
            "limit",
            "not",
            "null",
            "on",
            "or",
            "order",
            "select",
            "set",
            "table",
            "union",
            "update",
            "values",
            "where",
        ]),
    },
    html: {
        aliases: ["html", "xml"],
        keywords: new Set(),
    },
    markdown: {
        aliases: ["markdown", "md"],
        keywords: new Set(),
        hashComments: false,
    },
};

const aliases = new Map(
    Object.entries(definitions).flatMap(([name, definition]) =>
        definition.aliases.map((alias) => [alias, name] as const),
    ),
);

const tokenPattern =
    /\/\*[\s\S]*?\*\/|\/\/[^\n]*|#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|\b\d+(?:\.\d+)?\b|\b[A-Za-z_$][\w$-]*\b/g;

export function highlightCode(language: string, code: string): HighlightedCode {
    const normalized = aliases.get(language.trim().toLowerCase());
    if (!normalized) {
        return {
            language: language.trim() || "plain text",
            supported: false,
            tokens: [{ text: code, kind: "plain" }],
        };
    }

    const definition = definitions[normalized];
    const tokens: HighlightToken[] = [];
    let cursor = 0;
    for (const match of code.matchAll(tokenPattern)) {
        const index = match.index;
        if (index > cursor) {
            tokens.push({
                text: code.slice(cursor, index),
                kind: "plain",
            });
        }
        const text = match[0];
        let kind: HighlightToken["kind"] = "plain";
        if (
            text.startsWith("/*") ||
            text.startsWith("//") ||
            (text.startsWith("#") && definition.hashComments)
        ) {
            kind = "comment";
        } else if (/^["'`]/.test(text)) {
            kind = "string";
        } else if (/^\d/.test(text)) {
            kind = "number";
        } else if (
            ["true", "false", "null", "None", "True", "False"].includes(text)
        ) {
            kind = "literal";
        } else if (
            definition.keywords.has(text) ||
            definition.keywords.has(text.toLowerCase())
        ) {
            kind = "keyword";
        }
        tokens.push({ text, kind });
        cursor = index + text.length;
    }
    if (cursor < code.length) {
        tokens.push({ text: code.slice(cursor), kind: "plain" });
    }

    return { language: normalized, supported: true, tokens };
}
