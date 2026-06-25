from pydantic import BaseModel


class Page(BaseModel):
    title: str = ""
    url: str = ""
    text: str = ""


class ChatRequest(BaseModel):
    thread_id: str
    question: str
    page: Page


class ChatResponse(BaseModel):
    answer: str
