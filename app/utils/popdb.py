import sys
sys.path.append('')

from app.dependencies import pp, logging
from app.api import app
from app.models import User, Expert, Chat, Doc
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
    




# Run all the tests
if __name__ == "__main__":
    pytest.main([__file__])
