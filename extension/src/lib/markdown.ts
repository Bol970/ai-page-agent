import { marked } from "marked";
import DOMPurify from "dompurify";

// Ссылки в ответах открываем в новой вкладке.
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noreferrer noopener");
  }
});

/** Превращает markdown в безопасный HTML. При сбое — экранированный текст. */
export function renderMarkdown(md: string): string {
  try {
    const html = marked.parse(md, { async: false }) as string;
    return DOMPurify.sanitize(html);
  } catch {
    return md
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
}
