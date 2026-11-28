import { useState } from "react";
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
import { Check, Copy, Sparkles } from "lucide-react";

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

export default function MessageBubble({ message }) {
  const { role, content, metadata } = message;
  const [copied, setCopied] = useState(false);

  if (role === "user")
    return (
      <div className="message-row message-row--user">
        <div className="user-message">{content}</div>
      </div>
    );
  if (role === "system")
    return (
      <div className="notice-message" role="status">
        {content}
      </div>
    );

  const copyResponse = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* Clipboard may be unavailable in insecure contexts. */
    }
  };

  return (
    <article className="assistant-message" data-testid="assistant-message">
      <div className="assistant-avatar">
        <Sparkles size={16} />
      </div>
      <div className="assistant-content">
        <div className="assistant-name">Jimmy</div>
        <div className="markdown-body">
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
        </div>
        {metadata && (
          <div className="message-meta">
            <span
              className={
                metadata.resolution_source === "LLM_CACHE" ? "cache-pill" : ""
              }
              data-testid="meta-source"
            >
              {metadata.resolution_source === "LLM_CACHE"
                ? "Cached"
                : "Answered"}
            </span>
            {metadata.model && <span>{metadata.model}</span>}
            {Number.isFinite(metadata.latency_ms) && (
              <span>{metadata.latency_ms} ms</span>
            )}
            {Number.isFinite(metadata.input_tokens) &&
              Number.isFinite(metadata.output_tokens) && (
                <span>
                  {metadata.input_tokens} in · {metadata.output_tokens} out
                </span>
              )}
          </div>
        )}
        <div className="message-tools">
          <button onClick={copyResponse} aria-label="Copy response">
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
    </article>
  );
}
