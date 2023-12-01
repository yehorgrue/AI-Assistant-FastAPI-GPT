from app.dependencies import pp, logging
from .api import app
from .models import User, Expert, Chat, Doc
import pytest
import json
from fastapi.testclient import TestClient
import random
from faker import Faker
import os
import time


fake = Faker()

# NOTE: we need REDIS_OM_URL to be set else the redis defaults to looking at localhost silently

@pytest.fixture(scope="module")
def client():
    token: str
    user: User
    expert: Expert
    chat: Chat
    doc: Doc
    # Set up a test client using the FastAPI app
    with TestClient(app) as client:
        yield client

# #########################################################################
# Setup some experts in plans


@pytest.mark.dependency()
def test_delete_all_experts(client):
    token = "dummy"
#!    print("del all experts: token=", token)
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.post("/experts/deleteall", headers=headers)
    logging.debug(pp.pformat(response.json()))
    assert response.status_code == 200


@pytest.mark.dependency(depends=["test_delete_all_experts"])
def test_create_template_experts(client):
    token = "dummy"
    headers = {
        'authorization': 'Bearer ' + token
    }
    # Create 3 basic experts
    for _ in range(3):
        expert_data = {
            "name": fake.name(),
            "role": fake.job(),
            "image": "http://placekitten.com/g/100/100",
            "objective": "Provide basic expert advice",
            "prompt": fake.paragraph(nb_sentences=5),
            "docs": []
        }
        params = {"user_id": "basic"}
        response = client.post("/experts", json=expert_data, params=params, headers=headers)
    # Create 2 pro experts
    for _ in range(2):
        expert_data = {
            "name": fake.name(),
            "role": fake.job(),
            "image": "http://placekitten.com/g/100/100",
            "objective": "Provide PRO expert advice",
            "prompt": fake.paragraph(nb_sentences=5),
            "docs": []
        }
        params = {"user_id": "pro"}
        response = client.post("/experts", json=expert_data, params=params, headers=headers)
    


'''
# Attempt to create existing signup - this should fail
@pytest.mark.dependency()
def test_signup_existing_user(client):
    fake.random.seed(12345)
    name = fake.name()
    email = fake.email() 
    body = {
        "name": name,
        "email": email,
        "role": "user"  
    }
    pp.pprint(f"body: {body}")
    response = client.post("/register_user", json=body)
    json_response = json.loads(response.text)
    if response.status_code == 400:
        print(json_response['message'])
        client.token = ""
    else:
        pp.pprint(f"signup response: {json_response}")
        client.token = json_response["access_token"]
    logging.info(f"signup: {pp.pformat(json_response)}")
    assert json_response != ""
    assert response.status_code != 200
'''
        
# register a new user 
@pytest.mark.dependency(depends=["test_create_template_experts"])
def test_signup_new_admin(client):
    fake.random.seed(random.randint(1, 10000))
    name = fake.name()
    email = fake.email() 
    password = fake.password()
    body = {
        "name": name,
        "email": email,
        "password": password,
        "role": "admin",
        "subscription": {
            "stripe_price_id": "testing 123",
            "balance": 100.0,
            "plan": "pro"
        }
    }
    pp.pprint(body)
    response = client.post("/register_user", json=body)
    json_response = json.loads(response.text)
    print("register_user: response = ")
    pp.pprint(json_response)
    if response.status_code == 400:
        print(json_response['message'])
        client.token = ""
        client.user = ""
    else:
        print("register_user: response: ")
        pp.pprint(json_response)
        # HACK
        client.token = "dummy"  # json_response["access_token"]
        # fetch the user to validate they have been created
        client.user = User.get(json_response['pk'])
#!        pp.pprint(client.user)
    # HACK: due to firebase auth bug of clock skew (token used too early) - https://stackoverflow.com/questions/71915309/token-used-too-early-error-thrown-by-firebase-admin-auths-verify-id-token-metho
    #!time.sleep(10)
#!    pp.pprint(f"signup: {pp.pformat(json_response)}")
    assert json_response != ""
    assert response.status_code == 200


@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_ping(client):
    token = client.token
#!    print("ping: token=", token)
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.post("/ping", headers=headers)
    logging.info(f"ping: {pp.pformat(response.text)}")
    assert response.text != ""

 
def setup_module(module):
    pass


@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_delete_all_chats(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.post("/chats/deleteall", headers=headers)
    logging.debug(pp.pformat(response.json()))
    assert response.status_code == 200

@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_delete_all_docs(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.post("/docs/deleteall", headers=headers)
    logging.debug(pp.pformat(response.json()))
    assert response.status_code == 200

@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_delete_all_skills(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.post("/skills/deleteall", headers=headers)
    logging.debug(pp.pformat(response.json()))
    assert response.status_code == 200



##########################################################################
# Skill-related tests

'''
@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_load_skills(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    data = {"filename": f"{os.getcwd()}/uploads/skills.yml"}
    response = client.post("/skills/load", params=data, headers=headers)
    client.skill = response.json()
    logging.debug(f"load_skills: ", response.json())
    logging.info(f"skills: {len(response.json())}")
    assert response.status_code == 200
    assert len(response.json()) > 0


@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_create_skill(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    skill_data = {
        "name": "search",
        "description": "useful when you want to search the internet.",
        "image": "http://placekitten.com/g/100/100",
        "filename": f"{os.getcwd()}/skills/search.py",
        "module": "search",
    }
    response = client.post("/skills", json=skill_data, headers=headers)
    client.skill = response.json()
    assert response.status_code == 200
    assert skill_data.items() <= response.json().items()


@pytest.mark.dependency(depends=["test_create_skill", "test_signup_new_admin"])
def test_get_skill(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    skill_id = client.skill['pk']
    response = client.get(f"/skills/{skill_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["pk"] == skill_id


@pytest.mark.dependency(depends=["test_create_skill", "test_signup_new_admin"])
def test_get_all_skills(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.get("/skills", headers=headers)
    logging.debug(pp.pformat(response.json()))
    assert response.status_code == 200
'''

##########################################################################
# User-related tests  

@pytest.mark.dependency(depends=[ "test_signup_new_admin"])
def test_get_user(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    print("get_user: ", client.user)
    user_id = client.user.pk
    logging.debug('user_id:', user_id)
    response = client.get(f"/users/{user_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["pk"] == user_id

@pytest.mark.dependency(depends=[ "test_signup_new_admin"])
def test_update_user(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    user_id = client.user.pk
    logging.debug('user_id:', user_id)
    user_data = {
        "email": "steve@messina.com",
    }
    response = client.patch(f"/users/{user_id}", json=user_data, headers=headers)
    logging.debug(pp.pformat(user_data))
    logging.debug(pp.pformat(response.json()))
    client.user = response.json()
    assert response.status_code == 200
    assert user_data.items() <= response.json().items()
    
@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_get_all_users(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.get(f"/users", headers=headers)
    logging.debug(pp.pformat(response.json()))
    assert response.status_code == 200
    # assert response.json()["pk"] == user_id


##########################################################################
# Expert-related tests 

@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_load_experts(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    data = {"filename": f"{os.getcwd()}/uploads/experts.yml", "user_id": 'basic'}
    response = client.post("/experts/load", params=data, headers=headers)
#    pp.pprint(response.json())
    expert = response.json()[0]
#    pp.pprint(expert)
    client.expert = expert
    logging.debug("load_experts: ", response.json())
    logging.info("experts: {len(response.json())}")
    assert response.status_code == 200
    assert len(response.json()) > 0


@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_create_expert(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    expert_data = {
        "name": "Expert User",
        "role": "expert",
        "image": "http://placekitten.com/g/100/100",
        "objective": "Provide expert advice",
        "prompt": "Ask me anything",
        "docs": []
    }
    params = {"user_id": client.user['pk']}
    response = client.post("/experts", json=expert_data, params=params, headers=headers)
    pp.pprint(response.json())
    # client.expert = response.json()
    assert response.status_code == 200
    assert expert_data.items() <= response.json().items()


@pytest.mark.dependency(depends=["test_create_expert", "test_signup_new_admin"])
def test_update_expert(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    expert_id = client.expert['pk']
    logging.debug('expert_id:', expert_id)
    expert_data = {
        "name": "Jane Brain",
    }
    response = client.patch(f"/experts/{expert_id}", json=expert_data, headers=headers)
    logging.debug(pp.pformat(expert_data))
    logging.debug(pp.pformat(response.json()))
    client.expert = response.json()
    assert response.status_code == 200
    assert expert_data.items() <= response.json().items()


@pytest.mark.dependency(depends=["test_update_expert", "test_signup_new_admin"])
def test_get_expert(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    expert_id = client.expert['pk']
    response = client.get(f"/experts/{expert_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["pk"] == expert_id


@pytest.mark.dependency(depends=["test_create_expert", "test_signup_new_admin"])
def test_get_all_experts(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
#    params = {"user_id": client.user['pk']}    
    response = client.get("/experts/all/experts", headers=headers)
#    logging.debug(pp.pformat(response.json()))
    assert response.status_code == 200


@pytest.mark.dependency(depends=["test_create_expert", "test_signup_new_admin"])
def test_get_all_experts_for_user(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    params = {"user_id": client.user['pk']}    
    response = client.get("/experts/all/user", params=params, headers=headers)
    experts = json.loads(response.text)
    for expert in experts:
        print(expert['name'], ' ', expert['owner'])
    print(pp.pformat(response.json()))
    assert response.status_code == 200
    assert len(experts) == 3  # should be 2 pro experts + 1 created user
    
    
##########################################################################
# Chat-related tests
@pytest.mark.dependency(depends=["test_create_expert", "test_signup_new_admin"])
def test_create_chat(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    user_id = client.user['pk']
    expert_id = client.expert['pk']
    chat_data = {
        "name": "Chat Room",
        "user_id": user_id,
        "expert_id": expert_id,
    }
    params = {"user_id": user_id}
    response = client.post("/chats", json=chat_data, params=params, headers=headers)
    print('response: ', pp.pformat(response.json()))
    client.chat = response.json()['chat']
    print('client.chat = ', pp.pformat(client.chat))
    print('participants = ', pp.pformat(response.json()['participants']))
    assert response.status_code == 200
#    assert chat_data.items() <= response.json().items()

@pytest.mark.dependency(depends=["test_create_chat", "test_signup_new_admin"])
def test_get_chat_for_user(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    user_id = client.user['pk']
    params = {"user_id": client.user['pk']}    
    response = client.get(f"/chats/user/{user_id}", params=params, headers=headers)
    print('chats for user: ', pp.pformat(response.json()))
    assert response.status_code == 200
#    assert (any(user_id == d["user_id"] for d in response.json()))    

@pytest.mark.dependency(depends=["test_create_chat","test_signup_new_admin"])
def test_get_messages(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    chat_id = client.chat['pk']
    print('get_messages for: ', chat_id)
    response = client.get(f"/chats/{chat_id}/messages", headers=headers)
    print('messages: ', pp.pformat(response.json()))
    assert response.status_code == 200
#    assert response.json()["pk"] == chat_id

@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_get_all_chats(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.get(f"/chats", headers=headers)
    logging.info(pp.pformat(response.json()))
    assert response.status_code == 200


@pytest.mark.dependency(depends=["test_create_chat","test_signup_new_admin"])
def test_save_message_to_history(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    chat_id = client.chat['pk']
    message_data = "All your base are belong to us"
    response = client.post(f"/chats/{chat_id}/messages", params={"message": message_data}, headers=headers)
    print("save_message response: ", pp.pformat(response.json()))
    assert response.status_code == 200
#    assert (any(message_data in d for d in client.chat['messages']))


@pytest.mark.dependency(depends=["test_create_chat", "test_signup_new_admin"])
def test_add_expert_to_chat(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    chat_id = client.chat['pk']
    expert_id = client.expert['pk']
    response = client.post(f"/chats/{chat_id}/experts/{expert_id}", headers=headers)
    print(pp.pformat(response.json()))
    assert response.status_code == 200

@pytest.mark.dependency(depends=["test_create_chat", "test_signup_new_admin"])
def test_remove_expert_from_chat(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    chat_id = client.chat['pk']
    expert_id = client.expert['pk']
    response = client.delete(f"/chats/{chat_id}/experts/{expert_id}", headers=headers)
    print(pp.pformat(response.json()))
    assert response.status_code == 200

@pytest.mark.dependency(depends=["test_create_chat", "test_signup_new_admin"])
def test_rename_chat(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    chat_id = client.chat['pk']
    new_name = "My shiny new name"
    response = client.post(f"/chats/{chat_id}/rename", params={"new_name": new_name}, headers=headers)
    print(pp.pformat(response.json()))
    assert response.status_code == 200

    
##########################################################################
# Docs-related tests
@pytest.mark.dependency(depends=["test_update_expert", "test_signup_new_admin"])
def test_upload_documents(client):
    token = client.token
    expert = client.expert
    headers = {
        'authorization': 'Bearer ' + token
    }
    file1 = f"{os.getcwd()}/uploads/budget.csv"
    file2 = f"{os.getcwd()}/uploads/budget.xlsx"
    files = [
        ('files', open(file1, 'rb')),
        ('files', open(file2, 'rb')),
    ]
    route = "/docs/upload"
    print(f"uploading: \n{pp.pformat(files)}\nto {route}")
    response = client.post(route, params={'expert_id': expert['pk']}, files=files, headers=headers)
    print("upload doc: = ", response.json())
    client.doc = response.json()[0]
    logging.info(f"uploaded: \n{pp.pformat(response.json())}")
    assert response.status_code == 200
#    assert len( response.json()["keys"] ) > 0

@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_upload_documents_to_shared(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    file2 = f"{os.getcwd()}/uploads/budget.xlsx"
    files = [
        ('files', open(file2, 'rb')),
    ]
    print(f"uploading: \n{pp.pformat(files)}\nto /docs/upload")
    response = client.post("/docs/upload", params={'expert_id': 'shared'}, files=files, headers=headers)
    print("upload doc: = ", response.json())
    client.doc = response.json()[0]
    logging.info(f"uploaded: \n{pp.pformat(response.json())}")
    assert response.status_code == 200
#    assert len( response.json()["keys"] ) > 0


@pytest.mark.dependency(depends=["test_update_expert", "test_signup_new_admin"])
def test_upload_pdf_document_from_url(client):
    token = client.token
    expert = client.expert
    headers = {
        'authorization': 'Bearer ' + token
    }
    doc = {"filename": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"}
    response = client.post("/docs/url_upload", params={'expert_id': expert['pk'], 'url': doc['filename']}, json=doc, headers=headers)
    pp.pprint(response.json())
    logging.debug(f"uploaded: \n{doc['filename']}: ", pp.pformat(response.json()))
    assert response.status_code == 200
    # assert doc.items() <= response.json().items()


@pytest.mark.dependency(depends=["test_update_expert", "test_signup_new_admin"])
def test_upload_excel_document_from_url(client):
    token = client.token
    expert = client.expert
    headers = {
        'authorization': 'Bearer ' + token
    }
    doc = {"filename": "https://go.microsoft.com/fwlink/?LinkID=521962"}
    # doc = {"filename": "https://file-examples.com/wp-content/storage/2017/02/file_example_XLS_10.xlsx"}
    response = client.post("/docs/url_upload", params={'expert_id': expert['pk'], 'url': doc['filename']}, json=doc, headers=headers)
    client.doc = response.json()
    logging.debug(f"uploaded: \n{doc['filename']}: ", pp.pformat(response.json()))
    assert response.status_code == 200
    # assert doc.items() <= response.json().items()

@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_upload_excel_document_from_url_to_shared(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    doc = {"filename": "https://go.microsoft.com/fwlink/?LinkID=521962"}
    # doc = {"filename": "https://file-examples.com/wp-content/storage/2017/02/file_example_XLS_10.xlsx"}
    response = client.post("/docs/url_upload", params={'expert_id': 'shared', 'url': doc['filename']}, json=doc, headers=headers)
    client.doc = response.json()
    logging.debug(f"uploaded: \n{doc['filename']}: ", pp.pformat(response.json()))
    assert response.status_code == 200
    # assert doc.items() <= response.json().items()


@pytest.mark.dependency(depends=["test_update_expert", "test_signup_new_admin"])
def test_upload_pdf_document_from_url_to_shared(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    doc = {"filename": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"}
    response = client.post("/docs/url_upload", params={'expert_id': 'shared', 'url': doc['filename']}, json=doc, headers=headers)
    client.doc = response.json()
    logging.debug(f"uploaded: \n{doc['filename']}: ", pp.pformat(response.json()))
    assert response.status_code == 200
    # assert doc.items() <= response.json().items()

       
@pytest.mark.dependency(depends=["test_upload_documents", "test_signup_new_admin"])
def test_get_document(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    document_id = client.doc['pk']
    logging.debug('doc id: ', document_id)
    response = client.get(f"/docs/{document_id}", headers=headers)
    logging.debug('response: ', response.json())
    assert response.status_code == 200
    assert response.json()["pk"] == document_id


@pytest.mark.dependency(depends=["test_upload_documents", "test_signup_new_admin"])
def test_get_all_documents(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.get("/docs/all", headers=headers)
    logging.debug(len(response.json()), response.json())
    assert response.status_code == 200
    assert len(response.json()) >= 1 


@pytest.mark.dependency(depends=["test_update_expert", "test_upload_documents", "test_signup_new_admin"])
def test_get_all_documents_for_expert(client):
    token = client.token
    expert = client.expert
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.get("/docs/all/expert", params={'expert_id': expert['pk']}, headers=headers)
    logging.debug(len(response.json()), response.json())
    assert response.status_code == 200
    assert len(response.json()) >= 1 


@pytest.mark.dependency(depends=["test_upload_documents", "test_signup_new_admin"])
def test_get_all_documents_for_shared(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.get("/docs/all/expert", params={'expert_id': 'shared'}, headers=headers)
    logging.debug(len(response.json()), response.json())
    assert response.status_code == 200
    assert len(response.json()) >= 1 

# ######################################## CLEAN UP
'''
@pytest.mark.dependency(depends=["test_upload_documents", "test_signup_new_admin"])
def test_delete_document(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    print("delete doc: ", client.doc)
    doc_id = client.doc['pk']
    logging.debug('doc_id:', doc_id)
    response = client.delete(f"/docs/{doc_id}", headers=headers)
    logging.debug(response, pp.pformat(response.text))
    client.doc = None 
    assert response.status_code == 200
    assert response.json() == 1
        
@pytest.mark.dependency(depends=["test_create_expert", "test_signup_new_admin"])
def test_delete_expert(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    expert_id = client.expert['pk']
    logging.debug('expert_id:', expert_id)
    response = client.delete(f"/experts/{expert_id}", headers=headers)
    logging.debug(pp.pformat(response.json()))
    client.expert = None 
    assert response.status_code == 200
    assert response.json() == 1
    
@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_delete_user(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    user_id = client.user['pk']
    logging.debug('user_id:', user_id)
    response = client.delete(f"/users/{user_id}", headers=headers)
    logging.debug(pp.pformat(response.json()))
    client.user = None
    assert response.status_code == 200
    assert response.json() == 1

@pytest.mark.dependency(depends=["test_create_chat", "test_signup_new_admin"])
def test_delete_chat(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    chat_id = client.chat['pk']
    logging.debug('chat_id:', chat_id)
    response = client.delete(f"/chats/{chat_id}", headers=headers)
    logging.debug(pp.pformat(response.json()))
    client.chat = None
    # TODO: This returns 404 because all chats were deleted as part of the above user deletion etc.
    #assert response.status_code == 200
    #assert response.json() == 1


@pytest.mark.dependency(depends=["test_signup_new_admin"])
def test_delete_all_users(client):
    token = client.token
    headers = {
        'authorization': 'Bearer ' + token
    }
    response = client.post("/users/deleteall", headers=headers)
    print(response, response.text)
    logging.debug(response, pp.pformat(response))
    assert response.status_code == 200
'''

##########################################################################
# Run all the tests
if __name__ == "__main__":
    pytest.main([__file__])
