export interface PageContent {
  tabId: number;
  title: string;
  url: string;
  text: string;
  html: string;
}

export async function getPageContent(): Promise<PageContent> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("Не удалось определить активную вкладку");
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    // func сериализуется и выполняется на странице — замыкания недоступны,
    // поэтому лимит HTML (800 000 символов) прописан числом внутри.
    func: () => ({
      title: document.title,
      url: location.href,
      text: document.body?.innerText ?? "",
      html: (document.body?.outerHTML ?? "").slice(0, 800_000),
    }),
  });
  return {
    tabId: tab.id,
    ...(result as { title: string; url: string; text: string; html: string }),
  };
}
