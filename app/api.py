from app.dependencies import pp, redisdb, redis_api_cache, redis_api_db, redis_llm_cache, register_exception_handlers
from app.routers import sessions, query, users, docs, experts, chats, bookmarks, skills, payment
from app.utils import userauth
import os
import os.path
import uvicorn
import langchain
import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from langchain.cache import RedisCache

tags_metadata = [
    {
        "name": "Default",
        "description": "Default uncategorized API functions",
    },
    {
        "name": "Session",
        "description": "Session management.",
    },
    {
        "name": "Query",
        "description": "Q&A, Summarization, Interactive Chat to LLM & Backend.",
    },
    {
        "name": "Skills",
        "description": "Pluggable skills such as search, calculator, integration, etc.",
    },
    {
        "name": "Users",
        "description": "User profile & session.",
    },
    {
        "name": "Experts",
        "description": "Expert employees management.",
    },
    {
        "name": "Chats",
        "description": "Chat history",
    },
    {
        "name": "Bookmarks",
        "description": "Bookmark management.",
    },
    {
        "name": "Docs",
        "description": "Document Management",
    },
]

app = FastAPI(
    title="Azara API", 
    summary=f"Azara AI API - {os.getenv('AZARA_ENV')} environment, {os.getenv('AZARA_API_VERSION')}",
    version=f"{os.getenv('AZARA_API_VERSION')}",
    openapi_tags=tags_metadata,
)

origin_regex = r"^https?://((localhost(:[0-9]+)?)|(127\.0\.0\.1(:[0-9]+)?)|(neuralflow-bai-dev.*\.web\.app))$"

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(sessions.unprotected_router)
app.include_router(users.router)
app.include_router(experts.router)
app.include_router(docs.router)
app.include_router(chats.router)
app.include_router(query.router)
app.include_router(bookmarks.router)
app.include_router(skills.router)
app.include_router(payment.router)


@app.on_event("startup")
async def startup():
    register_exception_handlers(app)
    print("REDIS.ping: ", pp.pformat(redisdb.ping()))   
    langchain.llm_cache = RedisCache(redis_llm_cache)
    FastAPICache.init(RedisBackend(redis_api_cache), prefix="fastapi-cache")
    # HACK: Clear these out on startup - is this a broken pattern??
    redis.Redis.flushdb(redis_llm_cache)
    redis.Redis.flushdb(redis_api_cache)
    pass


if __name__ == "__main__":
    uvicorn.run("fastapi_code:app", reload=True)