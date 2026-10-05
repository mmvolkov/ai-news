from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    emoji: str
    headline: str = Field(description="Заголовок новости, до 55 символов")
    summary: str = Field(description="Суть одной фразой, до 70 символов")
    timestamp_sec: int = Field(description="Секунда ролика, где начинается новость")
    source_url: str = Field(description="Ссылка на первоисточник из описания ролика или пустая строка")


class Digest(BaseModel):
    title: str
    items: list[NewsItem]
    outro: str
    hashtags: list[str]


class Scene(BaseModel):
    time: str
    visual: str
    on_screen_text: str
    voiceover: str


class Reels(BaseModel):
    hook: str
    scenes: list[Scene]
    music: str
    caption: str


class Issue(BaseModel):
    digest: Digest
    image_prompt: str
    image_text_overlay: str
    reels: Reels
    video_prompt: str
    voiceover_full: str
