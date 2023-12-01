from app.models import Expert, Doc, SummarizedDoc, SummarizedExpert
import os
import os.path
# import json
import traceback
import logging
import pprint
from dotenv import load_dotenv
from fastapi import FastAPI, status, Request, HTTPException
from fastapi.responses import JSONResponse
import openai
from langchain.chat_models import ChatOpenAI
import redis
import firebase_admin
from firebase_admin import credentials
from fastapi.security import OAuth2PasswordBearer

from langchain.cache import InMemoryCache
import langchain
langchain.llm_cache = InMemoryCache()

global llm
global redisdb  # VectorDB
global redis_api_db # FastAPI models
global redis_llm_cache # LLM cache
global redis_api_cache  # FastAPI cache must be decode_response = False
global pp
global pb


pp = pprint.PrettyPrinter(indent=4)

logging.info("Initializing FastAPI")

logging.info("Loading Environment Vars")
try:
#    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    config_file= f'{os.getcwd()}/.env'
    if os.path.isfile(config_file): 
        print(f"EXISTS: {config_file}")
    load_dotenv(config_file)
    print('dotenv: OPENAI_API_KEY: ', os.getenv("OPENAI_API_KEY"))
    print('dotenv: REDIS_OM_URL: ', os.getenv("REDIS_OM_URL"))
except Exception as e:
    logging.error("Exception during load_dotenv (expected inside docker)", e)
    pass

logging.info("Initializing Firebase")
# https://medium.com/plain-simple-software/create-an-api-with-user-management-using-fastapi-and-firebase-dbf1cb4a3876
# The difference between these two Firebase setups is what they do. 
# The firebase_admin app will verify the ID token for the user 
# while the pyrebase app is the one that lets you sign in with your email and password.
# TODO: These need to be secret files
print(f"looking for firebase config files in: {os.getcwd()}")
config_file = f'{os.getcwd()}/azara-ai_service_account_keys.json'
if os.path.isfile(config_file): 
    print(f"EXISTS: {config_file}")
cred = credentials.Certificate(config_file)
firebase = firebase_admin.initialize_app(cred)
#config_file= f'{os.getcwd()}/firebase_config.json'
#if os.path.isfile(config_file): 
#    print(f"EXISTS: {config_file}")
#pb = pyrebase.initialize_app(json.load(open(config_file)))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Setup redis
logging.info("Initializing Redis VectorStore, APIdb, LLM cache, API cache")
REDIS_OM_URL = os.getenv("REDIS_OM_URL")
logging.info("REDIS_OM_URL: ", REDIS_OM_URL)
# VectorStore DB (redis)
redisdb = redis.Redis.from_url(url=REDIS_OM_URL, decode_responses=True) # type: ignore
# TODO: FastAPI models - same as vector store (for now)
redis_api_db = redis.Redis.from_url(url=REDIS_OM_URL, decode_responses=True) # type: ignore
# TODO: llm cache - same as vector store (for now)
redis_llm_cache = redis.Redis.from_url(url=REDIS_OM_URL, decode_responses=True) # type: ignore
# TODO: Make this a separate redis instance 
redis_api_cache = redis.Redis.from_url(url=REDIS_OM_URL, decode_responses=False) # type: ignore


logging.info("Initializing OpenAI")
os.environ["LANGCHAIN_TRACING"] = "true"
openai.api_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(
    temperature=0, 
    cache=True,
    verbose=True,
    model_name="gpt-3.5-turbo-0613"  # "gpt-3.5-turbo",
)  # type: ignore

logging.info("Initialization complete.")


# Return a summary of an expert - for use in populating UI's etc.
async def summarized_expert(expert_id: str) -> SummarizedExpert:
    summarized_expert = None
    try:
        expert = Expert.get(expert_id)
        summarized_expert = SummarizedExpert(
            pk=expert.pk,
            name=expert.name,
            role=expert.role,
            image=expert.image,
            objective=expert.objective,
            prompt=expert.prompt,
            tone=expert.tone,
            docs=[SummarizedDoc(
                filename=doc.filename,
                type=doc.type,
                summary=doc.summary) for doc in expert.docs]
        )
        return summarized_expert
    except Exception as e:
        raise HTTPException(status_code=500, detail={'message': f"Error Creating Summarized Expert.\n{pp.pformat(traceback.format_exception(e))}"})

async def handleError(_: Request, e: Exception) -> JSONResponse:
    """High level exception handler for exceptions
    """
    logging.exception({pp.pformat(e.with_traceback(e.__traceback__))})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'message': f'Unhandled Internal Server Error.\n{pp.pformat(e.with_traceback(e.__traceback__))}'}
    )


async def default_error_handler(_: Request, e: Exception) -> JSONResponse:
    """High level exception handler for all exceptions
    """
    logging.exception({pp.pformat(e.with_traceback(e.__traceback__))})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'message': f'Unhandled Internal Server Error.\n{pp.pformat(e.with_traceback(e.__traceback__))}'}
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Add exception handlers to FastAPI app
    """
    app.add_exception_handler(Exception, default_error_handler)
