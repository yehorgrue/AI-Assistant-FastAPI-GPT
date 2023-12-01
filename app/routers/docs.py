from app.models import Doc, Expert, UserRecord
from app.utils.userauth import get_current_user
from app.routers.users import update_llm_token_history
from app.dependencies import pp, llm, logging
import sys
import os
import os.path
import traceback
from pathlib import Path
import urllib.request
from werkzeug.utils import secure_filename
import pandas as pd
import shutil
from typing import List
import tempfile
import zipfile
import io
from starlette.requests import Request
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores.redis import Redis
from langchain.document_loaders import PyPDFLoader, CSVLoader
from fastapi import APIRouter, HTTPException, UploadFile, Depends
from fastapi_cache.decorator import cache
from langchain.callbacks import OpenAICallbackHandler, get_openai_callback
from promptwatch import PromptWatch
from firebase_admin import auth
from redis_om import NotFoundError


router = APIRouter(
    prefix="/docs",
    tags=["Docs"],
#!    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)
########################################## DOCUMENTS

# Get all the current docs - TODO: admin only 
# BUG: The GET /docs was never being called ?! so changed to /docs/all for now
@router.get('/all', response_model=List[Doc])
@cache(expire=60)
async def get_all_docs(request: Request):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    logging.debug('get all docs')
    docs = []
    for pk in Doc.all_pks():
        logging.debug('adding: ', str(pk))
        docs.append(Doc.get(pk).dict())
    logging.debug(pp.pformat(f"docs: {docs}"))
    return docs

# Get all the current docs by owner (shared or expert_id)
# BUG: The GET /docs was never being called ?! so changed to /docs/all for now
@router.get('/all/expert', response_model=List[Doc])
@cache(expire=60)
async def get_docs_by_owner(request: Request, expert_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    logging.debug('get all docs for owner = ', expert_id)
    docs = []
    for pk in Doc.all_pks():
        doc = Doc.get(pk)
        if doc.owner == expert_id:  # or 'shared'
            logging.debug('adding: ', str(pk))
            docs.append(doc.dict())
    logging.debug(pp.pformat(f"docs: {docs}"))
    return docs

@router.post('/url_upload', response_model=Doc)
async def url_upload(request: Request, expert_id: str, url: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    with PromptWatch(api_key=os.getenv("PROMPTWATCH_API_KEY")) as pw:
        with get_openai_callback() as cb:
            try:
                expert = None
                print("expert_id = ", expert_id)
                if expert_id and expert_id != "" and expert_id != "shared":
                    expert = Expert.get(expert_id)
                print('upload file from url: ', url)
                total_tokens = 0
                extension = Path(url).suffix
                if extension in ["xls", "xlsx"]:
                    response = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(url)))
                    print('testzip: ', response.testzip())
                else:
                    response = urllib.request.urlopen(url)
                with response:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=extension, mode='w+b') as temp:
                        try:
                            # temp.write(f.read())
                            shutil.copyfileobj(response, temp)
                            path = Path(temp.name)
                        finally:
                            temp.close()
                    print('content type = ', response.info().get_content_type())
                    if extension in ['xls', 'xlsx']:
                        response.info().set_content_type('application/vnd.ms-excel')
                    # if response.info().get_content_type() in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
                    if response.info().get_content_type() not in ["text/csv", "application/pdf"]:
                        # Read the file as Excel and save as CSV
                        df = pd.read_excel(io=temp.name, engine='openpyxl')
                        path = temp.name.replace(".xlsx", ".csv")
                        extension = '.csv'
                        df.to_csv(path, index=False)
                    logging.info(f"temp file: {pp.pformat(path)}\nextension: {extension}")

                    loader = CSVLoader(str(path))
                    if extension == '.pdf':
                        loader = PyPDFLoader(str(path))
                    pages = loader.load_and_split()

                    doc = Doc(
                        filename=url,
                        summary="",
                        type="url",
                        keys=[],
                        owner=expert_id
                    )
                    # create an index name
                    doc.index_name = f"{secure_filename(Path(url).stem + extension)}-({doc.pk})"
                    logging.info(f"index name: {doc.index_name}")
                    embeddings = OpenAIEmbeddings()  # type: ignore
                    texts = [d.page_content for d in pages]
                    # metadatas = [d.metadata for d in pages]
                    # We want the keys so we can delete the embedded docs later
                    rds, keys = Redis.from_texts_return_keys(
                        texts,
                        embeddings,
                        redis_url=os.getenv("REDIS_OM_URL"),
                        index_name=doc.index_name
                    )
                    for k in keys:
                        doc.keys.append(k)
                    logging.info("keys: ", pp.pformat(k))
                    if not doc.summary or doc.summary == "":
                        doc.summary = url

                    total_tokens += cb.total_tokens
                    logging.info("tokens: ", str(total_tokens))   
                    result = doc.save()
                    logging.debug(result.json())

                    # link to the expert
                    if expert and expert_id != "" and expert_id != "shared":
                        expert.docs.append(doc)
                        expert.save()                

    #!                await update_llm_token_history(
    #!                    llm_model=llm.model_name,
    #!                    usage=sys._getframe().f_code.co_name,
    #!                    cb=cb,
    #!                    current_user=current_user
    #!                )
                    return doc
            except NotFoundError as e:
                raise HTTPException(status_code=400, detail={f'Expert not found to attach document to.\n{traceback.format_exception(e)}'})


# upload new document(s)
@router.post('/upload', response_model=List[Doc])
async def upload_files(request: Request, expert_id: str, files: List[UploadFile]):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    print('upload file from: ', pp.pformat(files))
    total_tokens = 0
    docs = []
    with PromptWatch(api_key=os.getenv("PROMPTWATCH_API_KEY")) as pw:
        with get_openai_callback() as cb:
            try:
                expert = None
                print("expert_id = ", expert_id)
                if expert_id and expert_id != "" and expert_id != "shared":
                    expert = Expert.get(expert_id)
                pp.pprint(expert)
                for file in files:
                    print('upload file: ', file.filename)
                    extension = Path(str(file.filename)).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp:
                        try:
                            shutil.copyfileobj(file.file, temp)
                            path = Path(temp.name)
                        finally:
                            temp.close()

                    if file.content_type not in ["text/csv", "application/pdf"]:
                        # Read the file as Excel and save as CSV
                        df = pd.read_excel(temp.name, engine='openpyxl')
                        path = temp.name.replace(".xlsx", ".csv")
                        extension = '.csv'
                        df.to_csv(path, index=False)
                    print(f"temp file: {pp.pformat(path)}")

                    if extension == '.pdf':
                        loader = PyPDFLoader(path)
                    elif extension == '.csv':
                        loader = CSVLoader(path)
                    pages = loader.load_and_split()
                    
                    doc = Doc(
                        filename=str(file.filename),
                        summary="",
                        owner=expert_id,
                        type="file",
                        keys=[],
                    )
                    # create an index name
                    doc.index_name = f"{secure_filename(Path(path).stem + extension)}-({doc.pk})"
                    logging.info(f"index name: {doc.index_name}")
                    embeddings = OpenAIEmbeddings()
                    texts = [d.page_content for d in pages]
                    # metadatas = [d.metadata for d in pages]
                    # We want the keys so we can delete the embedded docs later
                    rds, keys = Redis.from_texts_return_keys(
                        texts,
                        embeddings,
                        redis_url=os.getenv("REDIS_OM_URL"),
                        index_name=doc.index_name
                    )
                    for k in keys:
                        doc.keys.append(k)

                    if not doc.summary or doc.summary == "":
                        doc.summary = str(path)

                    total_tokens += cb.total_tokens
                    # logging.info("tokens: ", str(total_tokens))
                    doc.save()
                    # link to the expert
                    if expert and expert_id != "" and expert_id != "shared":
                        expert.docs.append(doc)
                        expert.save()
                    # logging.debug(result.json())
    #!                await update_llm_token_history(
    #!                    llm_model=llm.model_name,
    #!                    usage=sys._getframe().f_code.co_name,
    #!                    cb=cb,
    #!                    current_user=current_user
    #!                )
                    docs.append(doc)
            except NotFoundError as e:
                raise HTTPException(status_code=400, detail={'Expert not found to attach document to'})
    return docs


# Get a doc
@router.get('/{doc_id}', response_model=Doc)
@cache(expire=60)
async def get_a_doc(request: Request, doc_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        logging.debug("get doc: ", doc_id)
        result = Doc.get(doc_id)
        logging.debug(result)
        return result
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Doc not found")


# delete a document
@router.delete('/{doc_id}')
async def delete_doc(request: Request, doc_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        doc = Doc.get(doc_id)
        # remove this doc from its owner
        if doc.owner != "" and doc.owner != "shared":
            expert = Expert.get(doc.owner)
            if expert and doc_id in expert.docs:
                expert.docs = [doc for doc in expert.docs if doc.pk != doc_id]
                expert.save()
        # remove the embedding and index for this doc
        #Redis.delete(doc.keys, redis_url=os.getenv("REDIS_OM_URL"))
        Redis.drop_index(doc.index_name, delete_documents=True, redis_url=os.getenv("REDIS_OM_URL"))
        result = Doc.delete(doc_id)
        return result
    except NotFoundError as e:
        logging.error("Exception: ", pp.pformat(e), '\n', pp.pformat(e.with_traceback(e.__traceback__)))
        raise HTTPException(status_code=404, detail=f"Doc not found: {doc_id}")
    except Exception as e:
        logging.error("Exception: ", pp.pformat(e), '\n', pp.pformat(e.with_traceback(e.__traceback__)))
        raise HTTPException(status_code=404, detail=f"Error while deleting doc. {pp.pformat(e.with_traceback(e.__traceback__))}")
    
# delete all docs
# BUG: if this was also a DELETE it always routes to the singular case above :-/
@router.post('/deleteall')
async def delete_all_docs(request: Request):
#!    current_user = request.state.current_user
    # Check if the user has the necessary permissions
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not enough permissions")
    count = 0
    try:
        for pk in Doc.all_pks():
            try:
                doc = Doc.get(pk)
                # remove this doc from its owner
                if doc.owner != "" and doc.owner != "shared":
                    expert = Expert.get(doc.owner)
                    if doc_id in expert.docs:
                        expert.docs = [doc for doc in expert.docs if doc.pk != doc_id]
                        expert.save()
                logging.info("deleting: ", doc.index_name)
                try:
                    # Delete the index for this doc, and the embedding keys/docs
                    Redis.drop_index(doc.index_name, delete_documents=True, redis_url=os.getenv("REDIS_OM_URL"))
                except Exception as e:
                    logging.error("Exception while drop index: ", doc.index_name, '\n', pp.pformat(doc.keys), '\n', pp.pformat(e.with_traceback(e.__traceback__)))
                try:
                    Doc.delete(pk)
                    count += 1
                except Exception as e:
                    logging.error("Exception while Doc.delete: ", pp.pformat(doc), '\n', pp.pformat(e.with_traceback(e.__traceback__)))
            except NotFoundError as e:
                logging.error("NotFoundError while deleting doc: ", '\n', pp.pformat(e.with_traceback(e.__traceback__)))
    except Exception as e:
        logging.error(f"Exception while deleting all docs:\n, {pp.pformat(e.with_traceback(e.__traceback__))}")
    return count