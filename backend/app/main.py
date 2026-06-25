from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import SystemMessage, HumanMessage

from app import config
from app.config import load_settings
from app.agent import build_agent, build_page_system_message
from app.schemas import ChatRequest, ChatResponse

config.settings = load_settings()
agent = build_agent(config.settings)

app = FastAPI(title="AI Page Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_seen_threads: set[str] = set()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    cfg = {"configurable": {"thread_id": req.thread_id}}
    messages = []
    if req.thread_id not in _seen_threads:
        sys = build_page_system_message(
            req.page.title, req.page.url, req.page.text,
            config.settings.page_text_limit,
        )
        messages.append(SystemMessage(content=sys))
        _seen_threads.add(req.thread_id)
    messages.append(HumanMessage(content=req.question))

    try:
        result = agent.invoke({"messages": messages}, cfg)
        answer = result["messages"][-1].content
    except Exception as exc:  # noqa: BLE001
        answer = f"Ошибка при обращении к агенту: {exc}"
    return ChatResponse(answer=answer)
