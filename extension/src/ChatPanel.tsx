import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { renderMarkdown } from "@/lib/markdown";
import type { ChatMeta } from "@/lib/chatsApi";

export interface DisplayMsg {
  role: "user" | "assistant";
  content: string;
  isError?: boolean;
}

const QUICK_PROMPTS = [
  "О чём эта страница?",
  "Кратко перескажи",
  "Главные тезисы списком",
  "Найди свежее по теме",
];

// Ссылки на mp3, которые генерирует инструмент text_to_speech бэкенда.
const AUDIO_URL_RE = /http:\/\/localhost:8000\/audio\/[0-9a-f-]+\.mp3/g;

function extractAudioUrls(content: string): string[] {
  return Array.from(new Set(content.match(AUDIO_URL_RE) ?? []));
}

interface ChatPanelProps {
  chat: ChatMeta | null;
  messages: DisplayMsg[];
  loading: boolean;
  pageReadable: boolean;
  onSend: (question: string) => void;
  onToggleSidebar: () => void;
  onAddTag: (tag: string) => void;
  onRemoveTag: (tag: string) => void;
}

export function ChatPanel({
  chat,
  messages,
  loading,
  pageReadable,
  onSend,
  onToggleSidebar,
  onAddTag,
  onRemoveTag,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [tagInput, setTagInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function submit() {
    const q = input.trim();
    if (!q || loading || !pageReadable) return;
    setInput("");
    onSend(q);
  }
  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }
  function commitTag() {
    const t = tagInput.trim();
    if (!t) return;
    setTagInput("");
    onAddTag(t);
  }

  return (
    <div className="flex h-full w-full flex-col bg-background text-foreground">
      <header className="flex items-center gap-2 border-b px-3 py-2">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onToggleSidebar}>
          ☰
        </Button>
        <span className="flex-1 truncate text-sm font-semibold">
          {chat?.title || "Новый чат"}
        </span>
      </header>

      {chat && (
        <div className="flex flex-wrap items-center gap-1 border-b px-3 py-2">
          {chat.tags.map((t) => (
            <span
              key={t}
              className="flex items-center gap-1 rounded bg-secondary px-1.5 py-0.5 text-[10px] text-secondary-foreground"
            >
              #{t}
              <button onClick={() => onRemoveTag(t)} className="opacity-70 hover:opacity-100">
                ✕
              </button>
            </span>
          ))}
          <input
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commitTag();
              }
            }}
            placeholder="+ тег"
            className="w-16 bg-transparent text-[11px] outline-none placeholder:text-muted-foreground"
          />
        </div>
      )}

      <ScrollArea className="flex-1">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {messages.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {pageReadable ? (
                <>
                  Спросите что-нибудь об этой странице. Например: «О чём эта
                  страница?» или «Найди свежие новости по теме».
                </>
              ) : (
                <>
                  Эту страницу нельзя прочитать (служебная страница браузера,
                  страница расширений или пустая вкладка). Откройте обычный сайт,
                  чтобы задать вопрос.
                </>
              )}
            </p>
          )}
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-primary px-4 py-2 text-sm text-primary-foreground">
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={i} className="flex gap-3">
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary text-[10px] font-semibold text-secondary-foreground">
                  AI
                </div>
                {m.isError ? (
                  <div className="pt-0.5 text-sm text-destructive">{m.content}</div>
                ) : (
                  <div className="min-w-0 flex-1">
                    <div
                      className="assistant-html pt-0.5"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }}
                    />
                    {extractAudioUrls(m.content).map((src) => (
                      <audio key={src} controls src={src} className="mt-2 w-full" />
                    ))}
                  </div>
                )}
              </div>
            )
          )}
          {loading && (
            <div className="flex gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary text-[10px] font-semibold text-secondary-foreground">
                AI
              </div>
              <div className="flex items-center gap-1 pt-2">
                <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" />
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </ScrollArea>

      <div className="border-t px-4 py-3">
        {!loading && pageReadable && (
          <div className="mx-auto mb-2 flex max-w-3xl flex-wrap gap-1.5">
            {QUICK_PROMPTS.map((q) => (
              <button
                key={q}
                onClick={() => onSend(q)}
                className="rounded-full border bg-secondary px-3 py-1 text-xs text-secondary-foreground hover:bg-accent"
              >
                {q}
              </button>
            ))}
          </div>
        )}
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border bg-card px-3 py-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={!pageReadable}
            placeholder={
              pageReadable ? "Спросите об этой странице…" : "Страница недоступна для чтения"
            }
            className="max-h-40 min-h-[40px] flex-1 resize-none border-0 bg-transparent text-sm shadow-none focus-visible:ring-0 disabled:cursor-not-allowed"
          />
          <Button
            size="icon"
            className="h-9 w-9 shrink-0 rounded-full"
            onClick={submit}
            disabled={loading || !input.trim() || !pageReadable}
          >
            ➤
          </Button>
        </div>
      </div>
    </div>
  );
}
