export interface PageContent {
  tabId: number;
  title: string;
  url: string;
  text: string;
}

export async function getPageContent(): Promise<PageContent> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("Не удалось определить активную вкладку");
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => ({
      title: document.title,
      url: location.href,
      text: document.body?.innerText ?? "",
    }),
  });
  return { tabId: tab.id, ...(result as { title: string; url: string; text: string }) };
}
