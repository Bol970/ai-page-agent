const BASE = "http://localhost:8000";

export interface ChatMeta {
  id: string;
  page_url: string;
  page_title: string;
  title: string;
  pinned: boolean;
  tags: string[];
  created_at: string;
  updated_at: string;
  preview: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface PagePayload {
  title: string;
  url: string;
  text: string;
  html: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new Error("Не удалось подключиться к серверу. Запущен ли backend на :8000?");
  }
  if (!resp.ok) throw new Error(`Сервер вернул ошибку ${resp.status}`);
  return (await resp.json()) as T;
}

export function listChats(url: string): Promise<{ page: ChatMeta[]; all: ChatMeta[] }> {
  return req(`/chats?url=${encodeURIComponent(url)}`);
}

export function createChat(page_url: string, page_title: string): Promise<ChatMeta> {
  return req("/chats", { method: "POST", body: JSON.stringify({ page_url, page_title }) });
}

export function getChat(id: string): Promise<{ chat: ChatMeta; messages: Message[] }> {
  return req(`/chats/${id}`);
}

export function sendMessage(
  id: string,
  question: string,
  page: PagePayload
): Promise<{ answer: string }> {
  return req(`/chats/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ question, page }),
  });
}

export function updateChat(
  id: string,
  patch: { pinned?: boolean; title?: string; tags?: string[] }
): Promise<ChatMeta> {
  return req(`/chats/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export async function deleteChat(id: string): Promise<void> {
  await req(`/chats/${id}`, { method: "DELETE" });
}
