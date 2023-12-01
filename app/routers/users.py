from app.models import User, UserCreate, UserUpdate, LLMToken, UserRecord, Subscription, Plan
from app.dependencies import pp, logging
from app.utils.userauth import get_current_user
import traceback
from fastapi import APIRouter, HTTPException, Depends
from redis_om import NotFoundError
from fastapi_cache.decorator import cache
from starlette.responses import JSONResponse
from starlette.requests import Request
# debugging
from langchain.callbacks import OpenAICallbackHandler


router = APIRouter(
    prefix="/users",
    tags=["Users"],
#!    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

# ######################################### USERS


# Update the token usage for the current user
async def update_llm_token_history(request: Request, llm_model: str, usage: str, cb: OpenAICallbackHandler):
    # Check if the user has the necessary permissions
#!    current_user = request.state.current_user
#!    pp.pprint(f"update_llm_token_history: current_user: {current_user}")
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="User needs to be logged in.")
    print('LLMTokens callback: ', pp.pformat(cb))
    user_id = current_user
    if user_id != "unknown":
        user = User.get(user_id)
        token = LLMToken.from_orm({
            "llm_model": llm_model,
            "usage": usage,
            "total_tokens": cb.total_tokens,
            "prompt_tokens": cb.prompt_tokens,
            "completion_tokens": cb.completion_tokens,
            "total_usd_cost": cb.total_cost
        })
        user.llm_token_usage.append(token)
        user.save()
        print('Tokens used: ', user.pk, pp.pformat(token))


# Get current users
@router.get('/me', response_model=User)
@cache(expire=60)
async def get_current_user(request: Request):
    # Check if the user has the necessary permissions
    current_user = request.state.current_user
    pp.pprint(f"get_current_user: current_user: {current_user}")
    if not current_user:
        raise HTTPException(status_code=403, detail="Not authenticated")
    return current_user


# Get all users
@router.get('', response_model=list[User])
@cache(expire=60)
async def get_users(request: Request):
    # Check if the user has the necessary permissions
#!    current_user = request.state.current_user
#!    pp.pprint(f"get_users: current_user: {current_user}")
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")
    users = []
    for pk in User.all_pks():
        users.append(User.get(pk).dict())
    logging.info(pp.pformat(f"user: {users}"))
    return users


# Create/Register a user - THIS WILL BE DONE DURING SIGNUP OR GOOGLE SIGNIN
async def create_user(request: Request, user: UserCreate):
    # Check if the user has the necessary permissions
#!    current_user = request.state.current_user
#!    pp.pprint(f"create_user: current_user: {current_user}")
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")
    db_user = User.from_orm(user)
    # BUG FIXED: This appears necessary to ensure the Enum is carried over (doesn't work with .from_orm)
    db_user.role = user.role
    db_user.subscription = user.subscription
    logging.info('created db_user:', db_user)
    result = None
    try:
        result = db_user.save()
    except Exception as e:
        logging.exception("Error while saving user: ", pp.pformat(e), '\n', pp.pformat(traceback.format_exc()))
    logging.info(f'created user: {pp.pformat(result)}')
    return result


# Get a  user
@router.get('/{user_id}', response_model=User)
@cache(expire=60)
async def get_user(request: Request, user_id: str):
    # Check if the user has the necessary permissions
#!    current_user = request.state.current_user
#!    pp.pprint(f"get_user: current_user: {current_user}")
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")
    result = None
    try:
        result = User.get(user_id)
        # logging.info(pp.pformat(result))
        return result
    except NotFoundError:
        raise HTTPException(status_code=404, detail="User not found")


# Update a user
@router.patch('/{user_id}', response_model=User)
async def update_user(request: Request, user_id: str, user: UserUpdate):
    # Check if the user has the necessary permissions
#!    current_user = request.state.current_user
#!    pp.pprint(f"update_user: current_user: {current_user}")
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")

    try:
        existing_user = User.get(user_id)
        # logging.info("existing user: ", existing_user.dict())
        update_data = user.dict(exclude_unset=True)
        # logging.info("update data: ", update_data)
        updated_user = existing_user.copy(update=update_data) 
        # logging.info("updated_user: ", updated_user)
        result = updated_user.save()
        # logging.info("result: ", result)
        return result
    except NotFoundError:
        raise HTTPException(status_code=404, detail="User not found")


# delete a user
@router.delete('/{user_id}')
async def delete_user(request: Request, user_id: str):
    # Check if the user has the necessary permissions
#!    current_user = request.state.current_user
#!    pp.pprint(f"delete_user: current_user: {current_user}")
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")

    try:
        # check that the user id is valid
        user = User.get(user_id)
        result = User.delete(user_id)
        # logging.info(pp.pformat(result))
        return result
    except NotFoundError:
        raise HTTPException(status_code=404, detail="User not found")


# delete all users
@router.post('/deleteall')
async def delete_all_users(request: Request):
    # Check if the user has the necessary permissions
#!    current_user = request.state.current_user
#!    pp.pprint(f"deleteall: current_user: {current_user}")
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not authenticated")

    count = 0
    # TODO: Note here we are deleting the db entry for the current user too
    # and we aren't deleting any of the firebase users, so this is mostly going to be used at testing time.
    all_pk = User.all_pks()
    for pk in all_pk:
        await delete_user(request, user_id=pk)
        # logging.info("deleted: ", pp.pformat(pk))
        count += 1
    return JSONResponse(content={'count': count})