import { lazy, memo, Suspense, useState } from "react";
import { Check, Copy, Sparkles } from "lucide-react";

const MarkdownContent = lazy(() => import("./MarkdownContent"));

function MessageBubble({ message }) {
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
          <Suspense fallback={<span className="markdown-loading">Preparing response…</span>}>
            <MarkdownContent content={content} />
          </Suspense>
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

export default memo(MessageBubble);
