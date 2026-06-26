import { useCallback, useEffect, useRef, useState } from "react";
import { ChatPanel, type DisplayMsg } from "@/ChatPanel";
import { Sidebar } from "@/Sidebar";
import { getPageContent, type PageContent } from "@/lib/page";
import * as api from "@/lib/chatsApi";
import type { ChatMeta } from "@/lib/chatsApi";

// Нормализация как на бэкенде: схема+host+path, без query/hash.
function normalizeUrl(u: string): string {
  try {
    const x = new URL(u);
    return x.origin + x.pathname;
  } catch {
    return u;
  }
}

export function App() {
  const [page, setPage] = useState<PageContent | null>(null);
  const [pageChats, setPageChats] = useState<ChatMeta[]>([]);
  const [allChats, setAllChats] = useState<ChatMeta[]>([]);
  const [chat, setChat] = useState<ChatMeta | null>(null);
  const [messages, setMessages] = useState<DisplayMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const chatRef = useRef<ChatMeta | null>(null);
  useEffect(() => {
    chatRef.current = chat;
  }, [chat]);

  const refresh = useCallback(async (url: string) => {
    const data = await api.listChats(url);
    setPageChats(data.page);
    setAllChats(data.all);
    return data;
  }, []);

  // Читает активную вкладку и подтягивает её чаты (открывает последний или пустой новый).
  const syncActiveTab = useCallback(async () => {
    let p: PageContent;
    try {
      p = await getPageContent();
    } catch (e) {
      setPage(null);
      setChat(null);
      setMessages([
        {
          role: "assistant",
          content:
            `⚠️ Не удалось прочитать страницу: ${(e as Error).message}. ` +
            "Откройте панель на обычной веб-странице (не chrome://, не странице расширений).",
          isError: true,
        },
      ]);
      return;
    }
    setPage(p);
    try {
      const data = await refresh(p.url);
      if (data.page.length > 0) {
        const { chat, messages } = await api.getChat(data.page[0].id);
        setChat(chat);
        setMessages(messages.map((m) => ({ role: m.role, content: m.content })));
      } else {
        setChat(null);
        setMessages([]);
      }
    } catch {
      setChat(null);
      setMessages([
        {
          role: "assistant",
          content:
            "⚠️ Бэкенд недоступен. Запустите сервер: uvicorn app.main:app --port 8000",
          isError: true,
        },
      ]);
    }
  }, [refresh]);

  // Первичная загрузка + реакция на смену/обновление активной вкладки.
  useEffect(() => {
    syncActiveTab();
    const onActivated = () => syncActiveTab();
    const onUpdated = (
      _tabId: number,
      info: chrome.tabs.TabChangeInfo,
      tab: chrome.tabs.Tab
    ) => {
      if (info.status === "complete" && tab.active) syncActiveTab();
    };
    chrome.tabs.onActivated.addListener(onActivated);
    chrome.tabs.onUpdated.addListener(onUpdated);
    return () => {
      chrome.tabs.onActivated.removeListener(onActivated);
      chrome.tabs.onUpdated.removeListener(onUpdated);
    };
  }, [syncActiveTab]);

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

  async function send(question: string) {
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);

    // Всегда читаем АКТУАЛЬНУЮ страницу заново — ответ должен быть про неё.
    let p: PageContent;
    try {
      p = await getPageContent();
      setPage(p);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `⚠️ Не удалось прочитать страницу: ${(e as Error).message}`,
          isError: true,
        },
      ]);
      setLoading(false);
      return;
    }

    try {
      let active = chatRef.current;
      // Если активный чат принадлежит другой странице — начинаем новый для текущей.
      if (active && normalizeUrl(active.page_url) !== normalizeUrl(p.url)) {
        active = null;
      }
      if (!active) {
        active = await api.createChat(p.url, p.title);
        setChat(active);
      }
      const { answer } = await api.sendMessage(active.id, question, {
        title: p.title,
        url: p.url,
        text: p.text,
      });
      setMessages((m) => [...m, { role: "assistant", content: answer }]);
      const fresh = await api.getChat(active.id);
      setChat(fresh.chat);
      await refresh(p.url);
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
    if (chatRef.current?.id === c.id) setChat(updated);
    if (page) await refresh(page.url);
  }

  async function remove(c: ChatMeta) {
    if (!confirm(`Удалить чат «${c.title || "Без названия"}»?`)) return;
    await api.deleteChat(c.id);
    if (chatRef.current?.id === c.id) newChat();
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
