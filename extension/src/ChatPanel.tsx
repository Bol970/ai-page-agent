import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getPageContent } from "@/lib/page";
import { askAgent } from "@/lib/api";
import { renderMarkdown } from "@/lib/markdown";

interface Msg {
  role: "user" | "assistant";
  content: string;
  isError?: boolean;
}

export function ChatPanel() {
  const [threadId, setThreadId] = useState<string>("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
      if (tab?.id) setThreadId(`tab-${tab.id}`);
    });
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send() {
    const question = input.trim();
    if (!question || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);
    try {
      const page = await getPageContent();
      const answer = await askAgent(threadId, question, {
        title: page.title,
        url: page.url,
        text: page.text,
      });
      setMessages((m) => [...m, { role: "assistant", content: answer }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `⚠️ ${(e as Error).message}`, isError: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="flex h-screen w-full flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <span className="text-sm font-semibold">AI Page Agent</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setMessages([])}
          disabled={loading}
        >
          Очистить
        </Button>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {messages.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Спросите что-нибудь об этой странице. Например: «О чём эта
              страница?» или «Найди свежие новости по теме».
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
                  <div
                    className="assistant-html min-w-0 flex-1 pt-0.5"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }}
                  />
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
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border bg-card px-3 py-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Спросите об этой странице…"
            className="max-h-40 min-h-[40px] flex-1 resize-none border-0 bg-transparent text-sm shadow-none focus-visible:ring-0"
          />
          <Button
            size="icon"
            className="h-9 w-9 shrink-0 rounded-full"
            onClick={send}
            disabled={loading || !input.trim()}
          >
            ➤
          </Button>
        </div>
      </div>
    </div>
  );
}
