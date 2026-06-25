const BACKEND_URL = "http://localhost:8000/chat";

export interface PagePayload {
  title: string;
  url: string;
  text: string;
}

export async function askAgent(
  threadId: string,
  question: string,
  page: PagePayload
): Promise<string> {
  let resp: Response;
  try {
    resp = await fetch(BACKEND_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, question, page }),
    });
  } catch {
    throw new Error("Не удалось подключиться к серверу. Запущен ли backend на :8000?");
  }
  if (!resp.ok) throw new Error(`Сервер вернул ошибку ${resp.status}`);
  const data = (await resp.json()) as { answer: string };
  return data.answer;
}
