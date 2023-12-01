from app.models import User, UserCreate, Expert, Token, UserRecord, Subscription, Plan
from app.utils.userauth import get_current_user, get_app_user, get_firebase_user
from app.routers.users import create_user
from app.routers.experts import duplicate_template_experts_to_user
from app.dependencies import logging, pp
from fastapi import APIRouter, HTTPException, Depends
from firebase_admin import auth
from starlette.requests import Request
from starlette.responses import JSONResponse
import requests
import os
import jwt
import traceback
import json

router = APIRouter(
    prefix="",
    tags=["Session"],
#!    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

unprotected_router = APIRouter(
    prefix="",
    tags=["Default"],
    responses={404: {"description": "Not found"}},
)

# ######################################### UNPROTECTED API ROUTES
# Heartbeat 
@unprotected_router.get("/health")
async def health(request: Request):
    return JSONResponse(status_code=200, content={"detail": "server ok"})


# Basic ping - return environment and testing details 
@router.get("/ping")
async def pong(request: Request):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")  
#!    user = current_user
    return {
        "ping": "pong!",
        "azara env": os.getenv("AZARA_ENV"),
        "azara api version": os.getenv("AZARA_API_VERSION"),
#!        "current_user": user["uid"],
        "redis om server": os.getenv('REDIS_OM_URL')
    }


# ######################################### AUTH


# signup endpoint - create a DB user to match the equivalent firebase user
@unprotected_router.post("/register_user", response_model=User)
async def register_user(request: Request, register_user: UserCreate) -> User:
    email = register_user.email
    name = register_user.name  # Default to empty string if name is not provided
    role = register_user.role  # Default to empty string if role is not provided
    image = register_user.image 
    subscription = register_user.subscription
    try:           
        # No need to check for email duplicates as this was done by the UI when creating 
        # Create an app user to match the firebase
        new_user = User(
            uid='dummy',
            email=email,
            name=name,
            role=role,
            image=image,
            business_profile="",
            disabled=False,
            subscription=subscription
        )
        new_user.uid = new_user.pk
        new_user.save()
#!        print("new user: ", new_user.dict())

        # we need to duplicate the experts in the user's plan, into his ownership
        user_experts = await duplicate_template_experts_to_user(
            request=request,
            user_id=new_user.pk,
            plan=new_user.subscription.plan
        )
        pp.pprint(user_experts)
            
        return new_user
    except Exception as e:
        return JSONResponse(status_code=400, content={'message': f"Error Creating User.\n{pp.pformat(traceback.format_exception(e))}"})
    
'''
        # HACK: create a dummy access_token - This is a temp measure for testing only
        url = "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=" + os.getenv("FIREBASE_WEB_API_KEY")
        payload = {
            "uid": new_user.uid,
            "email": register_user.email,
            "password": register_user.password
        }
        response = requests.post(url, json=payload)
        print("response: ", response, response.text)
        if response.status_code == 200:
            access_token = json.loads(response.text)
            print("access_token: ", access_token['idToken'])
            return JSONResponse(status_code=200, content={"access_token": access_token['idToken'], "user": new_user.dict()})
        else: 
            raise Exception('Access code creation error.')

        return new_user
    except Exception as e:
        return JSONResponse(status_code=400, content={'message': f"Error Creating User.\n{pp.pformat(traceback.format_exception(e))}"})
'''

"""
original signup for reference purponses only
# signup endpoint
@default_router.post("/signup", response_model=User)
async def signup(user: UserCreate):
    email = user.email
    password = user.password
    name = user.name  # Default to empty string if name is not provided
    role = user.role  # Default to empty string if role is not provided
    try:
        url = "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=" + os.getenv("FIREBASE_WEB_API_KEY")
        payload = {
            "email": email,
            "password": password
        }
        response = requests.post(url, json=payload)
        print(response)
        auth.set_custom_user_claims(response['localId'], {'role': role})

        # Create an app user
        new_user = UserCreate(
            email=email,
            name=name,
            role=role
        )
        user = await create_user(new_user)  # type: ignore
        return user
    except Exception as e:
        return HTTPException(detail={'message': f'Error Creating User.\n{pp.pformat(e.with_traceback(e.__traceback__))}'}, status_code=400)

"""
