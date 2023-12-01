from app.models import Skill, UserRecord
from app.dependencies import pp, logging
from app.utils.userauth import get_current_user
from typing import List
import yaml
from fastapi import APIRouter, HTTPException, Depends
from fastapi_cache.decorator import cache
from langchain.callbacks import OpenAICallbackHandler, get_openai_callback
from promptwatch import PromptWatch
from redis_om import NotFoundError
from starlette.requests import Request
import importlib
from jinja2 import Environment, FileSystemLoader

router = APIRouter(
    prefix="/skills",
    tags=["Skills"],
#!    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

async def load_and_create_skill(request: Request, skill: Skill):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    print(f'output skill:\n{pp.pformat(skill)}')
    
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('app/skills/skill_template.j2')
    print("template: \n", template)
    
    output = template.render(
        name=skill.name,
        description=skill.description,
        modules=skill.modules,
        args_schema=skill.args_schema,
        code=skill.code
    )

    # with open("output.py", "w") as python_f:
    #     python_f.write(output)
    print(f'output code:\n{pp.pformat(output)}')
    return output

router = APIRouter(
    prefix="/skills",
    tags=["Skills"],
    responses={404: {"description": "Not found"}},
)

# ######################################### DOCUMENTS

# Get all the current skills
# BUG: The GET /skills was never being called ?! so changed to /skills/all for now
@router.get('/load')
async def load_skills(request: Request, filename: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    logging.info('load skill: ', filename)
    yaml_skill = yaml.safe_load_all(filename)
    print(f'yaml skills: ', pp.pformat(yaml_skill))
    skill = Skill(**yaml_skill)
    print(f'skills: ', pp.pformat(skill))
    agent = await load_and_create_skill(skill)
    print("agent: ", pp.pformat(agent))
    return agent


# Get all the current skills
# BUG: The GET /skills was never being called ?! so changed to /skills/all for now
@router.get('/all', response_model=List[Skill])
@cache(expire=60)
async def get_skills(request: Request):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    logging.debug('get all skills')
    skills = []
    for pk in Skill.all_pks():
        logging.debug('adding: ', str(pk))
        skills.append(Skill.get(pk).dict())
    logging.info(pp.pformat(f"skills: {skills}"))
    return skills


# Get a skill
@router.get('/{skill_id}', response_model=Skill)
@cache(expire=60)
async def get_a_skill(request: Request, skill_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        logging.debug("get skill: ", skill_id)
        result = Skill.get(skill_id)
        logging.debug(result)
        return result
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Skill not found")


# delete a skill
@router.delete('/{skill_id}')
async def delete_skill(request: Request, skill_id: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        result = Skill.delete(skill_id)
        return result
    except NotFoundError as e:
        logging.error("Exception: ", pp.pformat(e), '\n', pp.pformat(e.with_traceback(e.__traceback__)))
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    except Exception as e:
        logging.error("Exception: ", pp.pformat(e), '\n', pp.pformat(e.with_traceback(e.__traceback__)))
        raise HTTPException(status_code=404, detail=f"Error while deleting skill. {pp.pformat(e.with_traceback(e.__traceback__))}")


# delete all skills
# BUG: if this was also a DELETE it always routes to the singular case above :-/
@router.post('/deleteall')
async def delete_all_skills(request: Request):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    count = 0
    try:
        for pk in Skill.all_pks():
            try:
                skill = Skill.get(pk)
                logging.info("deleting: ", skill.name)  # type: ignore
                Skill.delete(pk)
                count += 1
            except NotFoundError as e:
                logging.error("NotFoundError while deleting skill: ", '\n', pp.pformat(e.with_traceback(e.__traceback__)))
    except Exception as e:
        logging.error(f"Exception while deleting all skills:\n, {pp.pformat(e.with_traceback(e.__traceback__))}")
    return count