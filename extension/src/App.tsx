import { useCallback, useEffect, useRef, useState } from "react";
import { ChatPanel, type DisplayMsg } from "@/ChatPanel";
import { Sidebar } from "@/Sidebar";
import { getPageContent, type PageContent } from "@/lib/page";
import * as api from "@/lib/chatsApi";
import type { ChatMeta } from "@/lib/chatsApi";

export function App() {
  const [page, setPage] = useState<PageContent | null>(null);
  const [pageChats, setPageChats] = useState<ChatMeta[]>([]);
  const [allChats, setAllChats] = useState<ChatMeta[]>([]);
  const [chat, setChat] = useState<ChatMeta | null>(null);
  const [messages, setMessages] = useState<DisplayMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const chatRef = useRef<ChatMeta | null>(null);
  useEffect(() => { chatRef.current = chat; }, [chat]);

  const refresh = useCallback(async (url: string) => {
    const data = await api.listChats(url);
    setPageChats(data.page);
    setAllChats(data.all);
    return data;
  }, []);

  async function selectChat(id: string) {
    const { chat, messages } = await api.getChat(id);
    setChat(chat);
    setMessages(messages.map((m) => ({ role: m.role, content: m.content })));
    setSidebarOpen(false);
  }

  function newChat() {
    setChat(null);
    setMessages([]);
    setSidebarOpen(false);
  }

  useEffect(() => {
    (async () => {
      let p: PageContent;
      try {
        p = await getPageContent();
        setPage(p);
      } catch (e) {
        setMessages([
          {
            role: "assistant",
            content:
              `⚠️ Не удалось прочитать страницу: ${(e as Error).message}. ` +
              "Откройте панель на обычной веб-странице (не chrome://, не странице расширений) и переоткройте её.",
            isError: true,
          },
        ]);
        return;
      }
      try {
        const data = await refresh(p.url);
        if (data.page.length > 0) {
          const { chat, messages } = await api.getChat(data.page[0].id);
          setChat(chat);
          setMessages(messages.map((m) => ({ role: m.role, content: m.content })));
        }
      } catch {
        setMessages([
          {
            role: "assistant",
            content:
              "⚠️ Бэкенд недоступен. Запустите сервер: uvicorn app.main:app --port 8000",
            isError: true,
          },
        ]);
      }
    })();
  }, [refresh]);

  async function send(question: string) {
    setMessages((m) => [...m, { role: "user", content: question }]);
    if (!page) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            "⚠️ Страница ещё не прочитана. Откройте панель на обычной веб-странице и переоткройте её (кликом по иконке).",
          isError: true,
        },
      ]);
      return;
    }
    setLoading(true);
    try {
      let active = chat;
      if (!active) {
        active = await api.createChat(page.url, page.title);
        setChat(active);
      }
      const { answer } = await api.sendMessage(active.id, question, {
        title: page.title,
        url: page.url,
        text: page.text,
      });
      setMessages((m) => [...m, { role: "assistant", content: answer }]);
      const fresh = await api.getChat(active.id);
      setChat(fresh.chat);
      await refresh(page.url);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `⚠️ ${(e as Error).message}`, isError: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function setTags(tags: string[]) {
    const current = chatRef.current;
    if (!current) return;
    const updated = await api.updateChat(current.id, { tags });
    setChat(updated);
    if (page) await refresh(page.url);
  }
  const addTag = (t: string) =>
    setTags(Array.from(new Set([...(chatRef.current?.tags ?? []), t])));
  const removeTag = (t: string) =>
    setTags((chatRef.current?.tags ?? []).filter((x) => x !== t));

  async function togglePin(c: ChatMeta) {
    const updated = await api.updateChat(c.id, { pinned: !c.pinned });
    if (chat?.id === c.id) setChat(updated);
    if (page) await refresh(page.url);
  }

  async function remove(c: ChatMeta) {
    if (!confirm(`Удалить чат «${c.title || "Без названия"}»?`)) return;
    await api.deleteChat(c.id);
    if (chat?.id === c.id) newChat();
    if (page) await refresh(page.url);
  }

  return (
    <div className="relative h-screen w-full overflow-hidden">
      <ChatPanel
        chat={chat}
        messages={messages}
        loading={loading}
        onSend={send}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        onAddTag={addTag}
        onRemoveTag={removeTag}
      />
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        pageChats={pageChats}
        allChats={allChats}
        currentId={chat?.id ?? null}
        onSelect={selectChat}
        onNew={newChat}
        onTogglePin={togglePin}
        onDelete={remove}
      />
    </div>
  );
}
