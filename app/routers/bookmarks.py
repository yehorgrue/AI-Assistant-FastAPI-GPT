from app.models import UserRecord
from app.routers.users import update_llm_token_history
from app.utils.userauth import get_current_user
from app.dependencies import pp, llm, logging
from fastapi import APIRouter, HTTPException, Depends
from firebase_admin import auth
from redis_om import NotFoundError
from fastapi_cache.decorator import cache
from langchain.callbacks import OpenAICallbackHandler, get_openai_callback
from promptwatch import PromptWatch

router = APIRouter(
    prefix="/bookmarks",
    tags=["Bookmarks"],
#!    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)
########################################## BOOKMARKS

'''
# return all bookmarks for a user
# TODO: This is broken because we haven't altered the langchain memory to include Message_id
# Also - naive version could just copy the text to user bookmarks, doesn't record the origin
@router.get('/{user_id}/bookmark')
@cache(expire=60)
def get_user_bookmarks(user_id:str, current_user: UserRecord):
    # Check if the user is trying to access their own record or if they are an admin
    if not current_user or (current_user.uid != user_id and current_user.role != "admin"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    bookmarks = []
    try:
        chats = get_chats_for_user()
        for chat in chats:
            if user_id == chat.user_id:
                for bookmark in chat.bookmarks:
                    bookmarks.append({
                        'chat_id': chat.pk,
                        'chat_name': chat.name,
                        'message_id': bookmark['message_id'],
                        'text': bookmark['text']
                    })
        return bookmarks
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Chat not found")


# mark a message as bookmarked
# TODO: This is broken because we haven't altered the langchain memory to include Message_id
@router.post('/{chat_id}/messages/{message_id}')
def add_bookmark(chat_id:str, message_id:str, text: str, current_user: UserRecord):
#!    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        chat = Chat.get(chat_id)
        if (chat.user_id != current_user.uid) or (current_user.role != "admin"):
            raise HTTPException(status_code=401, detail="Not authorized")
        # if not found, then add it
        if not next((bookmark for bookmark in chat.bookmarks if bookmark["message_id"] == message_id), None):
            chat.bookmarks.append({
                'chat_id': chat_id,
                'chat_name': chat.name,
                'message_id': message_id,
                'text': text
            })
            chat.save()
        return chat
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Chat not found")


# remove a message as bookmarked
# TODO: This is broken because we haven't altered the langchain memory to include Message_id
@router.delete('/{chat_id}/messages/{message_id}')
def remove_bookmark(chat_id: str, message_id: str, current_user: UserRecord):
#!    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        chat = Chat.get(chat_id)
        if (chat.user_id != current_user.uid) or (current_user.role != "admin"):
            raise HTTPException(status_code=401, detail="Not authorized")
        # remove the old the bookmark
        # if  found, then remove it
        index = next((bookmark for bookmark in chat.bookmarks if bookmark["message_id"] == message_id), None)
        if index:
            chat.bookmarks.delete(index)
            # or chat.bookmarks = [b for b in chat.bookmarks if not b['message_id'] in [message_id]]
            chat.save()
        logging.info(chat)
        return chat
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Chat not found")
'''

