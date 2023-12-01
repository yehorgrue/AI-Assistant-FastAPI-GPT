from app.models import User, Expert, ExpertCreate, ExpertUpdate, Chat, UserRecord
from app.utils.userauth import get_current_user
from app.routers.chats import delete_expert_from_chat
from app.dependencies import pp, logging
import yaml
import traceback
from werkzeug.utils import secure_filename
from redis_om import NotFoundError
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request
from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import auth
from fastapi_cache.decorator import cache
from typing import List

router = APIRouter(
    prefix="/experts",
    tags=["Experts"],
#!    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)
# ######################################### EXPERTS


# load experts from file
# we use user_id until we can reinstate current user injection from auth.
# the field contains "shared" or a user_id that this expert belongs to
@router.post('/load')
async def load_experts(request: Request, filename: str, user_id: str):
#!    current_user = request.state.current_user
    # Check if the user has the necessary permissions
#!    if not current_user:
#!        raise HTTPException(status_code=403, detail="Not enough permissions")
    experts = []
    # Delete all experts
    # await delete_all_experts(current_user=current_user)
    # use `secure_filename` to clean the filename, notice it will only keep ascii characters
    fn = secure_filename(filename)
    logging.info(f"secure filename: {fn}")
    # load all the expert profiles
    expert_profiles = []
    try:
        # get the owner of this expert
        user = None
        print("user_id = ", user_id)
        if user_id and user_id != "" and user_id not in ['basic', 'pro', 'enteprise']:
            user = User.get(user_id)
        pp.pprint(user)

        with open(filename, 'r') as file:
            expert_profiles = yaml.safe_load(file)
    except yaml.YAMLError as e:
        logging.info(e)
        return JSONResponse(
            status_code=500,
            content={'YAMLError': str(e)}
        )
    logging.debug(pp.pformat(expert_profiles))
    for expert in expert_profiles:
        expert = Expert(**expert)
        expert.owner = user_id
        # TODO: fix this - NEUR-160
        expert.image = f'/static/experts/{expert.name}.png'
        expert.docs = []
        expert.save()
        logging.debug(expert)
        experts.append(expert)
    return experts


# Get expert
# TODO: check if admin, or if this is expert for your user
@router.get('/{expert_id}', response_model=Expert)
@cache(expire=60)
async def get_expert(request: Request, expert_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        expert = Expert.get(expert_id)
        logging.debug(expert)
        return expert
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Expert not found")


# Get all experts - TODO: admin only function 
# HACK: why doesn't /all resolve? 
@router.get('/all/experts')
#@cache(expire=60)
async def get_all_experts(request: Request):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        print('get all experts')
        experts = []
        for pk in Expert.all_pks():
#            logging.debug(f'retrieving expert: {pk}')
            expert = Expert.get(pk)
            experts.append(expert)
#        print(pp.pformat(f'experts: {experts}'))
        return experts
    except Exception as e:
        raise HTTPException(status_code=500, detail={'message': f"Error while getting all experts.\n{pp.pformat(traceback.format_exception(e))}"})


# Get all experts by owner
@router.get('/all/user', response_model=list[Expert])
@cache(expire=60)
async def get_experts_by_owner(request: Request, user_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        logging.debug('get all experts by owner = ', user_id)
        experts = []
        for pk in Expert.all_pks():
            expert = Expert.get(pk)
            if expert.owner == user_id:  # or 'shared'
                logging.debug('adding: ', str(pk))
                experts.append(expert)
#        logging.debug(pp.pformat(f'experts: {experts}'))
        return experts
    except Exception as e:
        raise HTTPException(status_code=500, detail={'message': f"Error while getting all experts by owner.\n{pp.pformat(traceback.format_exception(e))}"})

# Create expert
@router.post('', response_model=Expert)
async def create_expert(request: Request, expert: ExpertCreate, user_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        # validate whether it's a valid user_id or ['basic', 'pro', 'enteprise']:
        print("user_id = ", user_id)
        if user_id and user_id != "" and user_id not in ['basic', 'pro', 'enteprise']:
            User.get(user_id)

        db_expert = Expert.from_orm(expert)
        db_expert.docs = []
        db_expert.owner = user_id
        result = db_expert.save()
        logging.debug(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail={f'Error while creating expert.\n{traceback.format_exception(e)}'})

# Duplicate expert
@router.post('/duplicate', response_model=Expert)
async def duplicate_expert(request: Request, expert_id: str, user_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        # validate whether it's a valid user_id or ['basic', 'pro', 'enteprise']:
        print("user_id = ", user_id)
        if user_id and user_id != "" and user_id not in ['basic', 'pro', 'enteprise']:
            User.get(user_id)

        expert = Expert.get(expert_id)
        expert.docs = []
        expert.owner = user_id  # 'shared' or user id
        result = expert.save()
        logging.debug(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail={f'Error while duplicating expert.\n{traceback.format_exception(e)}'})

# Duplicate shared experts to a user
# When a new user is created by /signup
# We duplicate the shared users to give them an initial pool of experts
# TODO: This will need to be adjusted according to their plan
@router.post('/duplicate_template_experts', response_model=List[Expert])
async def duplicate_template_experts_to_user(request: Request, user_id: str, plan: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        # validate whether it's a valid user_id
        print("user_id = ", user_id)
        user = User.get(user_id)
        print("plan = ", plan)

        experts = []
        for pk in Expert.all_pks():
            expert = Expert.get(pk)
            if expert.owner == plan:
                db_expert = await duplicate_expert(request=request,
                                                   expert_id=expert.pk,
                                                   user_id=user.pk)
                experts.append(db_expert)
                logging.debug(f'duplicated expert: {db_expert.name}-{db_expert.owner}')
        logging.debug(experts)
        return experts
    except Exception as e:
        raise HTTPException(status_code=400, detail={f'Error while duplicating all shared expert to User.\n{traceback.format_exception(e)}'})


# Update expert
# TODO: either admin or only update your own experts 
@router.patch('/{expert_id}', response_model=Expert)
def update_expert(request: Request, expert_id: str, expert: ExpertUpdate):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        existing_expert = Expert.get(expert_id)
        logging.debug("existing expert: ", existing_expert.dict())
        update_data = expert.dict(exclude_unset=True)
        logging.debug("update data: ", update_data)
        updated_expert = existing_expert.copy(update=update_data)
        logging.debug("updated_expert: ", updated_expert)
        result = updated_expert.save()
        logging.debug("result: ", result)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail={f'Error while patching Expert.\n{traceback.format_exception(e)}'})


# delete an expert
# TODO: This is admin route or can only delete experts for your user_id
@router.delete('/{expert_id}')
async def delete_expert(request: Request, expert_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        # validate whether it's a valid user_id
#        print("user_id = ", user_id)
#        user = User.get(user_id)

        # check that the expert id is valid
        Expert.get(expert_id)
        #logging.log('delete_expert-> expert: ', expert)
        # remove the expert from participants in chat sessions 
        # TODO: what happens if all the experts are removed from a chat session?
#!        for pk in Chat.all_pks():
#!            chat = Chat.get(pk)
            #logging.log('delete_expert-> chat: ', chat)
#!            if expert_id in chat.participants:
#!                await delete_expert_from_chat(chat.pk, expert_id, current_user=current_user)
        result = Expert.delete(expert_id)
        # logging.info(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail={f'Error while deleting expert.\n{traceback.format_exception(e)}'})


# delete all experts
# ADMIN function
@router.post('/deleteall')
async def delete_all_experts(request: Request):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        count = 0
        all_pk = Expert.all_pks()
        for pk in all_pk:
            Expert.delete(pk)
            logging.debug("deleted expert: ", pp.pformat(pk))
            count += 1
        return count
    except Exception as e:
        raise HTTPException(status_code=400, detail={f'Error while deleting all experts.\n{traceback.format_exception(e)}'})

# delete all experts
# ADMIN function
@router.post('/deleteall_for_owner')
async def delete_all_experts_for_owner(request: Request, user_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        # validate whether it's a valid user_id
        print("user_id = ", user_id)
        User.get(user_id)

        count = 0
        all_pk = Expert.all_pks()
        for pk in all_pk:
                db_expert = Expert.get(pk)
                if db_expert.owner == user_id:
                    Expert.delete(pk)
                    logging.debug(f'deleted expert: {db_expert.name}-{db_expert.owner}')
                    count += 1
        return count
    except Exception as e:
        raise HTTPException(status_code=400, detail={f'Error while deleting all experts for User.\n{traceback.format_exception(e)}'})
