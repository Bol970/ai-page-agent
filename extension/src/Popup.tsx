import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";
import { getPageContent } from "@/lib/page";
import { askAgent } from "@/lib/api";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

export function Popup() {
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
        { role: "assistant", content: `⚠️ ${(e as Error).message}` },
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
    <div className="flex h-[500px] w-[380px] flex-col bg-background text-foreground">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-sm font-semibold">AI Page Agent</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setMessages([])}
          disabled={loading}
        >
          Очистить
        </Button>
      </div>

      <ScrollArea className="flex-1 px-3 py-2">
        <div className="flex flex-col gap-2">
          {messages.length === 0 && (
            <p className="text-xs text-muted-foreground">
              Спросите что-нибудь об этой странице. Например: «О чём эта страница?»
              или «Найди свежие новости по теме».
            </p>
          )}
          {messages.map((m, i) => (
            <Card
              key={i}
              className={
                "max-w-[90%] whitespace-pre-wrap px-3 py-2 text-sm " +
                (m.role === "user"
                  ? "self-end bg-primary text-primary-foreground"
                  : "self-start")
              }
            >
              {m.content}
            </Card>
          ))}
          {loading && (
            <Card className="self-start px-3 py-2 text-sm text-muted-foreground">
              Думаю…
            </Card>
          )}
          <div ref={endRef} />
        </div>
      </ScrollArea>

      <div className="flex gap-2 border-t p-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ваш вопрос…"
          className="min-h-[40px] resize-none text-sm"
        />
        <Button onClick={send} disabled={loading || !input.trim()}>
          ➤
        </Button>
      </div>
    </div>
  );
}
