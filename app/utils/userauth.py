from app.models import User, UserRecord
from app.dependencies import logging, pp, oauth2_scheme
from fastapi import APIRouter, HTTPException, Depends
from firebase_admin import auth
from starlette.requests import Request
from redis_om import NotFoundError
import traceback
import jwt
import requests
from cryptography.hazmat.backends import default_backend
from cryptography import x509
import os
import json


json_config = {}
config_file = f'{os.getcwd()}/azara-ai_service_account_keys.json'   
if os.path.isfile(config_file): 
    print(f"EXISTS: {config_file}")
try:
    with open(config_file, 'r') as f:
        json_config = json.loads(f.read())
        #pp.pprint(f'json: {json_config}')
except Exception as e:
    pp.pprint(e)



# Extract the ID Token from the custom token
# reference: https://firebase.google.com/docs/auth/admin/verify-id-tokens#python
def check_token(token: str):
    n_decoded = jwt.get_unverified_header(token)
    kid_claim = n_decoded["kid"]
#    response = requests.get('https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com')
    response = requests.get(json_config['client_x509_cert_url'])
#    print("x509 cert: ", response.json())
    x509_key = response.json()[kid_claim]
#    print("x509 key: ", x509_key)
    key = x509.load_pem_x509_certificate(x509_key.encode('utf-8'))
    public_key = key.public_key()
#    print("public key: ", public_key)
#    decoded_token = jwt.decode(token, public_key, ["RS256"], audience=json_config['project_id'], issuer=json_config['client_email'])
    decoded_token = jwt.decode(token, public_key, ["RS256"], audience='https://identitytoolkit.googleapis.com/google.identity.identitytoolkit.v1.IdentityToolkit', issuer=json_config['client_email'])
#    print(f"Decoded token : {decoded_token}")
    return decoded_token

# Authentication
# Function to get Firebase user
#  = Depends(oauth2_scheme)
def get_firebase_user(token: str) -> UserRecord:
    try:
        # we don't need to unpack a custom_token
        # id_token = check_token(token)
        # user_record = id_token
#        pp.pprint(f"get firebase user: token = {token}")
        # Verify the ID token first
        user_record = auth.verify_id_token(id_token=token, check_revoked=True)
#!        pp.pprint("get firebase user: user_record = ")
#!        pp.pprint(f'{user_record}')
        # Then get the user info
        firebase_user = UserRecord(
            uid=user_record['uid'],
            name=user_record['email'],
            email=user_record['email'],
            role='user'
        )
        return firebase_user
    except ValueError:
        # Token is invalid
        raise HTTPException(status_code=403, detail='Invalid token')
    except Exception as e:
        # Firebase Auth error
        raise HTTPException(status_code=403, detail=f'{e}\n{traceback.format_exc()}')


# Function to get app user
def get_app_user(user_id: str) -> User:
    try:
#!        print("looking up app_user: ", user_id)
#!        user = User.get(user_id)
        return user  # type: ignore
    except NotFoundError:
        print("-------- EXISTING USERS -------------")
        for pk in User.all_pks():
            print(pk)
        print(f"-------- {user_id} not found -------------")
        raise HTTPException(status_code=404, detail='User not found')


# Return the current logged in user 
async def get_current_user(request: Request) -> User:
    """Get the user details from Firebase, based on TokenID in the request

    :param request: The HTTP request
    """
    try:
        id_token = request.headers.get('Authorization')
        print("get_current_user: token = ", id_token)
#!        if not id_token:
#!            raise HTTPException(status_code=400, detail='TokenID must be provided')

        # Strip 'Bearer ' from the token
        if id_token[:7].startswith('Bearer '):
            id_token = id_token[7:]
        
        # Then get the user info
        firebase_user = get_firebase_user(id_token)
#!        pp.pprint('firebase_user: ')
#!        pp.pprint(firebase_user)  # type: ignore
        # Get app user
        user = get_app_user(firebase_user.uid)
        request.state.current_user = user
#!        pp.pprint('current app user: ')
#!        pp.pprint(user)
        return user
    except Exception as e:
        logging.exception(f'{pp.pformat(e.with_traceback(e.__traceback__))}')
        raise HTTPException(status_code=401, detail=f'Unauthorized.\n{pp.pformat(e.with_traceback(e.__traceback__))}')

