from pydantic import BaseModel


class Page(BaseModel):
    title: str = ""
    url: str = ""
    text: str = ""
    html: str = ""


class CreateChatRequest(BaseModel):
    page_url: str
    page_title: str = ""


class MessageRequest(BaseModel):
    question: str
    page: Page


class UpdateChatRequest(BaseModel):
    pinned: bool | None = None
    title: str | None = None
    tags: list[str] | None = None


class ChatResponse(BaseModel):
    answer: str
