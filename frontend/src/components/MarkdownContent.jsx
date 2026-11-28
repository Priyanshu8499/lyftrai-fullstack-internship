import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import javascript from "highlight.js/lib/languages/javascript";
import typescript from "highlight.js/lib/languages/typescript";
import python from "highlight.js/lib/languages/python";
import bash from "highlight.js/lib/languages/bash";
import json from "highlight.js/lib/languages/json";
import css from "highlight.js/lib/languages/css";
import xml from "highlight.js/lib/languages/xml";
import sql from "highlight.js/lib/languages/sql";
import { Check, Copy } from "lucide-react";
import { useState } from "react";
import "highlight.js/styles/github-dark.css";

const codeLanguages = {
  javascript,
  js: javascript,
  typescript,
  ts: typescript,
  python,
  py: python,
  bash,
  sh: bash,
  json,
  css,
  html: xml,
  xml,
  sql,
};

function CodeBlock({ children, ...props }) {
  const [copied, setCopied] = useState(false);
  const code = children?.props?.children;
  const language =
    children?.props?.className?.replace("language-", "") || "code";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(String(code ?? ""));
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* Clipboard may be unavailable in insecure contexts. */
    }
  };

  return (
    <div className="code-block">
      <div className="code-head">
        <span>{language}</span>
        <button onClick={copy} aria-label="Copy code">
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy code"}
        </button>
      </div>
      <pre {...props}>{children}</pre>
    </div>
  );
}

export default function MarkdownContent({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[[rehypeHighlight, { languages: codeLanguages }]]}
      components={{
        pre: CodeBlock,
        a: ({ node, ...props }) => (
          <a {...props} target="_blank" rel="noreferrer" />
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
