from app.models import Chat, ChatCreate, User, Expert, UserRecord, SummarizedDoc, SummarizedExpert
from app.routers.users import update_llm_token_history
from app.utils.userauth import get_current_user
from app.dependencies import pp, llm, logging, summarized_expert
import sys
import os.path
import traceback
from fastapi import APIRouter, HTTPException, Depends
from firebase_admin import auth
from redis_om import NotFoundError, JsonModel
from langchain.memory import RedisChatMessageHistory
from langchain.schema import SystemMessage
from fastapi_cache.decorator import cache
from langchain.callbacks import OpenAICallbackHandler, get_openai_callback
from promptwatch import PromptWatch
from starlette.requests import Request

router = APIRouter(
    prefix="/chats",
    tags=["Chats"],
#!    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)


# ######################################### CHAT
REDIS_OM_URL = os.getenv("REDIS_OM_URL")


# Get all the saved histories (for all users)
@router.get('/', response_model=list[Chat])
@cache(expire=60)
async def get_chats(request: Request):
    # Check if the user has the necessary permissions
#!#!    current_user = request.state.current_user
#!    pp.pprint(f"get_chats: current_user: {current_user}")
#!#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")

    memories = []    
    with PromptWatch(api_key=os.getenv("PROMPTWATCH_API_KEY")) as pw:
        with get_openai_callback() as cb:
            for pk in Chat.all_pks():
                try:
                    chat = Chat.get(pk)
                    logging.info("get_chats: ", pp.pformat(chat))
                    chat_history = RedisChatMessageHistory(pk, url=REDIS_OM_URL)
                    logging.info(pp.pformat(chat_history))
                    for msg in chat_history.messages:
                        chat.messages.append(str(msg.json()))
                    logging.info(pp.pformat(chat))
                    memories.append(chat)
                except NotFoundError:
                    logging.error("Chat not found")
            logging.info(pp.pformat(memories))
#!            await update_llm_token_history(
#!                llm_model=llm.model_name,
#!                usage=sys._getframe().f_code.co_name,
#!                cb=cb,
#!                current_user=current_user
#!            ) # type: ignore
        return memories

# Get all the saved histories (for a single user)
@router.get('/user/{user_id}', response_model=list[Chat])
@cache(expire=60)
async def get_chats_for_user(request: Request, user_id: str):
    # Check if the user has the necessary permissions
#!    current_user = request.state.current_user
#!    pp.pprint(f"get_chats_for_user: current_user: {current_user}")
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")

    with PromptWatch(api_key=os.getenv("PROMPTWATCH_API_KEY")) as pw:
        memories = []    
        with get_openai_callback() as cb:
            for pk in Chat.all_pks():
                try:
                    chat = Chat.get(pk)
                    if chat.user_id == user_id:
                        chat_history = RedisChatMessageHistory(pk, url=REDIS_OM_URL)
                        logging.info(pp.pformat(chat_history))
                        for msg in chat_history.messages:
                            chat.messages.append(str(msg.json()))
                        logging.info(pp.pformat(chat))
                        memories.append(chat)
                except NotFoundError:
                    logging.error("Chat not found")
            logging.debug("get_chats_for_user: ", pp.pformat(memories))
#!            await update_llm_token_history(
#!                llm_model=llm.model_name,
#!                usage=sys._getframe().f_code.co_name,
#!                cb=cb,
#!                current_user=current_user
#!            ) # type: ignore
            return memories

# Get a chat history metadata including messages
@router.get('/{chat_id}/messages', response_model=JsonModel)
@cache(expire=60)
async def get_chat_history(request: Request, chat_id: str):
    # Check if the user has the necessary permissions
#!#!    current_user = request.state.current_user
#!    pp.pprint(f"get_chat_history: current_user: {current_user}")
#!#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")

    with PromptWatch(api_key=os.getenv("PROMPTWATCH_API_KEY")) as pw:
        with get_openai_callback() as cb:
            chat = Chat.get(chat_id)
#!            if (chat.user_id != current_user.uid):
#!                raise HTTPException(status_code=401, detail="Not authorized")
            try:
                chat_history = RedisChatMessageHistory(chat_id, url=REDIS_OM_URL)
                logging.info(pp.pformat(chat_history))
                for msg in chat_history.messages:
                    chat.messages.append(str(msg.json()))
                logging.info(pp.pformat(chat))
#!                await update_llm_token_history(
#!                    llm_model=llm.model_name,
#!                    usage=sys._getframe().f_code.co_name,
#!                    cb=cb,
#!                    current_user=current_user
#!                ) # type: ignore
                participants = []
                for ex in chat.participants:
                    try:
                        sex = await summarized_expert(ex)
                        pp.pprint(sex)
                        participants.append(sex)
                    except Exception as e:
                        pp.pprint(f"Error Creating Participant.\n{ex}\n{pp.pformat(traceback.format_exception(e))}")
                        continue
                pp.pprint(f"get_chat_history:\n{chat}\n{participants}")
                return {"chat": chat, "participants": participants}
            except Exception as e:
                raise HTTPException(status_code=500, detail={'message': f"Error during get_chat_history.\n{pp.pformat(traceback.format_exception(e))}"})

# start a new chat session
@router.post('/')  # , response_model=dict(Chat, list[SummarizedExpert]))
async def create_new_chat(request: Request, chatIn: ChatCreate):
    # Check if the user has the necessary permissions
#!#!    current_user = request.state.current_user
#!    pp.pprint(f"create_new_chat: current_user: {current_user}")
#!#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")

    with PromptWatch(api_key=os.getenv("PROMPTWATCH_API_KEY")) as pw:
        with get_openai_callback() as cb:
            try:
                # validating the chat and expert id's
                user = User.get(chatIn.user_id)
                expert = Expert.get(chatIn.expert_id)
                logging.info('user: ', user, 'expert: ', expert)
                memory_id = str(chatIn.pk)
                chat_history = RedisChatMessageHistory(memory_id, url=REDIS_OM_URL)
                chat_history.clear()
                chat_history.add_ai_message(f'Welcome, my name is {expert.name}.\nMy role is to {expert.objective}\nHow can I assist you today?')
                logging.info(pp.pformat(chat_history.messages))
                # Record this as one of the users chat sessions
                user.chat_sessions.append({
                    'memory_id': str(memory_id),
                })
                # update the user 
                user.save()
                logging.info('user: ', pp.pformat(user))
                
                default_name = f"user-{user.pk}-expert-{expert.name}-{memory_id}"
                chat = Chat.from_orm(chatIn)
                if not chatIn.name:
                    chat.name = default_name
                chat.bookmarks = []
                chat.participants = [f"{chatIn.expert_id}"]
                chat.memory_id = memory_id
                chat.messages.clear()
                for msg in chat_history.messages:
                    chat.messages.append(str(msg.json()))
                #chat.messages = [str(chat_history.messages)]
                chat.save()           
                logging.info('chat: ', pp.pformat(chat))
#!                await update_llm_token_history(
#!                    llm_model=llm.model_name,
#!                    usage=sys._getframe().f_code.co_name,
#!                    cb=cb,
#!                    current_user=current_user # type: ignore
#!                )
                participants = []
                for ex in chat.participants:
                    try:
                        sex = await summarized_expert(ex)
                        pp.pprint(sex)
                        participants.append(sex)
                    except Exception as e:
                        pp.pprint(f"Error Creating Participant.\n{ex}\n{pp.pformat(traceback.format_exception(e))}")
                        continue
                pp.pprint(f"create_new_chat:\n{chat}\n{participants}")
                return {"chat": chat, "participants": participants}
            except Exception as e:
                raise HTTPException(status_code=500, detail={'message': f"Error Creating Chat.\n{pp.pformat(traceback.format_exception(e))}"})

# Add an expert to chat session
@router.post('/{chat_id}/experts/{expert_id}')
async def add_expert_to_chat(request: Request, chat_id: str, expert_id: str):
    # Check if the user has the necessary permissions
#!#!    current_user = request.state.current_user
#!    pp.pprint(f"ad_expert_to_chat: current_user: {current_user}")
#!#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")
    try:
        chat = Chat.get(chat_id)
        logging.info(pp.pformat(chat))
#!        if (chat.user_id != current_user.uid):
#!            raise HTTPException(status_code=401, detail="Not authorized")
        # Check to see if the expert exists in the chat participants
        if not expert_id in chat.participants:
            # add the expert to the participants list
            chat.participants.append(expert_id)
            chat.save()
            logging.info('added expert: ', chat)
        participants = []
        for ex in chat.participants:
            try:
                sex = await summarized_expert(ex)
                pp.pprint(sex)
                participants.append(sex)
            except Exception as e:
                pp.pprint(f"Error Creating Participant.\n{ex}\n{pp.pformat(traceback.format_exception(e))}")
                continue
        pp.pprint(f"add_expert_to_chat:\n{chat}\n{participants}")
        return {"chat": chat, "participants": participants}
    except Exception as e:
        raise HTTPException(status_code=500, detail={'message': f"Error adding expert to chat.\n{pp.pformat(traceback.format_exception(e))}"})

# Remove an expert from chat session
@router.delete('/{chat_id}/experts/{expert_id}')
async def delete_expert_from_chat(request: Request, chat_id: str, expert_id: str):
    # Check if the user has the necessary permissions
#!#!    current_user = request.state.current_user
#!    pp.pprint(f"delete_expert_from_chat: current_user: {current_user}")
#!#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")
    try:
        chat = Chat.get(chat_id)
#!        if (chat.user_id != current_user.uid):
#!            raise HTTPException(status_code=401, detail="Not authorized")
        # Check to see if the expert exists in the chat participants
        if expert_id in chat.participants:
            # add the expert to the participants list
            logging.debug('prior to remove expert: ', pp.pformat(chat.participants))
            chat.participants = [p for p in chat.participants if not p in [chat_id]]
            chat.save()
            logging.debug('removed expert: ', pp.pformat(chat))
        participants = []
        for ex in chat.participants:
            try:
                sex = await summarized_expert(ex)
                pp.pprint(sex)
                participants.append(sex)
            except Exception as e:
                pp.pprint(f"Error Creating Participant.\n{ex}\n{pp.pformat(traceback.format_exception(e))}")
                continue
        pp.pprint(f"remove_expert_from_chat:\n{chat}\n{participants}")
        return {"chat": chat, "participants": participants}
    except Exception as e:
        raise HTTPException(status_code=500, detail={'message': f"Error removing expert from chat.\n{pp.pformat(traceback.format_exception(e))}"})

# Update chat name of session
@router.post('/{chat_id}/rename')
async def rename_chat(request: Request, chat_id: str, new_name: str):
    # Check if the user has the necessary permissions
#!#!    current_user = request.state.current_user
#!    pp.pprint(f"rename_chat: current_user: {current_user}")
#!#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")

    try:
        chat = Chat.get(chat_id)
#!        if (chat.user_id != current_user.uid):
#!            raise HTTPException(status_code=401, detail="Not authorized")
        logging.debug('old name: ', chat.name, new_name)
        chat.name = new_name
        chat.save()
        logging.debug('new name: ', chat)
        participants = []
        for ex in chat.participants:
            try:
                sex = await summarized_expert(ex)
                pp.pprint(sex)
                participants.append(sex)
            except Exception as e:
                pp.pprint(f"Error Creating Participant.\n{ex}\n{pp.pformat(traceback.format_exception(e))}")
                continue
        pp.pprint(f"renaming_chat:\n{chat}\n{participants}")
        return {"chat": chat, "participants": participants}
    except Exception as e:
        raise HTTPException(status_code=500, detail={'message': f"Error renaming chat.\n{pp.pformat(traceback.format_exception(e))}"})

@router.post('/{chat_id}/messages')
async def save_message_to_history(request: Request, chat_id: str, message: str):
    # Check if the user has the necessary permissions
#!#!    current_user = request.state.current_user
#!    pp.pprint(f"save_message_to_history: current_user: {current_user}")
#!#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")

    with PromptWatch(api_key=os.getenv("PROMPTWATCH_API_KEY")) as pw:
        with get_openai_callback() as cb:
            try:
                chat = Chat.get(chat_id)
#!                if (chat.user_id != current_user.uid):
#!                    raise HTTPException(status_code=401, detail="Not authorized")
                memory_id = str(chat.pk)
                chat_history = RedisChatMessageHistory(memory_id, url=REDIS_OM_URL)
                chat_history.add_message(SystemMessage(content=message))
                for msg in chat_history.messages:
                    chat.messages.append(str(msg.json()))
                logging.debug(pp.pformat(chat))
#!                await update_llm_token_history(
#!                    llm_model=llm.model_name,
#!                    usage=sys._getframe().f_code.co_name,
#!                    cb=cb,
#!                    current_user=current_user
#!                ) # type: ignore
                participants = []
                for ex in chat.participants:
                    try:
                        sex = await summarized_expert(ex)
                        pp.pprint(sex)
                        participants.append(sex)
                    except Exception as e:
                        pp.pprint(f"Error Creating Participant.\n{ex}\n{pp.pformat(traceback.format_exception(e))}")
                        continue
                pp.pprint(f"save nessage to history:\n{chat}\n{participants}")
                return {"chat": chat, "participants": participants}
            except Exception as e:
                raise HTTPException(status_code=500, detail={'message': f"Error during save message to history.\n{pp.pformat(traceback.format_exception(e))}"})

'''        
# Load a chat message from history
# TODO: This is broken because we haven't altered the langchain memory to include message_id
@router.get('/{chat_id}/messages/{message_id}', response_model=JsonModel)
async def get_chat_message_from_history(request: Request, chat_id: str, message_id: str):
    # Check if the user has the necessary permissions
#!    current_user = request.state.current_user
#!    pp.pprint(f"get_chat_message_from_history: current_user: {current_user}")
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")
    with PromptWatch(api_key=os.getenv("PROMPTWATCH_API_KEY")) as pw:
        with get_openai_callback() as cb:
            try:
                chat = Chat.get(chat_id)
                if (chat.user_id != current_user.uid):
                    raise HTTPException(status_code=401, detail="Not authorized")
                # Fetch the existing chat history
                #redis_memory = RedisChatMessageHistory(
                #    session_id = chat.name,
                #    url = REDIS_OM_URL,
                #)
                #result = redis_memory.messages
                chat.messages.append(f"{message_id}: some message")
                # TODO: do a search of some sort here - once we fix the message_id issue
                logging.debug(pp.pformat(chat))
                await update_llm_token_history(
                    llm_model=llm.model_name,
                    usage=sys._getframe().f_code.co_name,
                    cb=cb,
                    current_user=current_user
                )
                participants = []
                for ex in chat.participants:
                    participants.append(summarized_expert(ex))
                return {"chat": chat, "participants": participants}
            except NotFoundError:
                raise HTTPException(status_code=404, detail="Chat not found")
'''

# delete a chat history
@router.delete('/{chat_id}')
async def delete_chat_history(request: Request, chat_id: str):
    # Check if the user has the necessary permissions
#!#!    current_user = request.state.current_user
#!    pp.pprint(f"delete_chat_history: current_user: {current_user}")
#!#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")
    try:
        logging.debug('delete_chat_history: chat_id: ', chat_id)
        chat = Chat.get(chat_id)
        logging.debug('chat: ', pp.pformat(chat))
#!        if (chat.user_id != current_user.uid):
#!            raise HTTPException(status_code=401, detail="Not authorized")

        user = User.get(chat.user_id)
        logging.debug('user: ', pp.pformat(user))
        # Remove this as one of the users chat sessions
        user.chat_sessions = [c for c in user.chat_sessions if c not in [chat_id]]
        # update the user 
        user.save()
        logging.debug(user)
        # TODO: No idea what this does :)
        # Fetch the existing chat history
        #redis_memory = RedisChatMessageHistory(
        #    session_id = chat.name,
        #    url = REDIS_OM_URL,
        #)
        #result = redis_memory.messages.remove(chat_id)
        result = chat.delete(chat_id)
        return result
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Chat not found")

# delete all chat histories
@router.post('/deleteall')
async def delete_all_chats(request: Request):
    # Check if the user has the necessary permissions
#!#!    current_user = request.state.current_user
#!    pp.pprint(f"get_chats: current_user: {current_user}")
#!#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")

    count = 0
    all_pk = Chat.all_pks()
    for pk in all_pk:
        # result = delete_chat_history(pk)
        Chat.delete(pk)
        logging.debug("deleted: ", pp.pformat(pk))
        count += 1
    return count
