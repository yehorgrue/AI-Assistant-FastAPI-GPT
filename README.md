## to build and run on docker

### build 
docker-compose build

### run
docker-compose up

### test
pytest -rA --verbose

### load test
locust -f app/load_test.py

## to run:
create env vars (in .env file or in cloud container console):
    OPENAI_API_KEY

    REDIS_OM_URL


Call API            http://localhost:9000/

For API docs        http://localhost:9000/docs

## Important Models
User        User model for typing together frontend and backend (role, auth, config, tokens, payments, etc)

Docs        Embedded Docs and metadata (Docs are embedded into Chroma and the embeddings persisted to the db/ folder)

Experts     The available AI experts and prompts

Chats       The api for chat management (chat to expert, add/remove expert from chat, get all chats for a user, ...)

Query       Refactoring of the POC to query an expert via chat (/chats/chat_id/query) - WIP refactoring to fit API backend



## Important Files
app/

    api.py       This contains the fastAPI

    config.py    env vars / settings

    models.py    FastAPI ORM models (Users, Chats, Experts, Docs)

    experts_chat.py     POC code for querying experts /chats/{chat_id}/query (Refactoring WIP)

Dockerfile            For fastapi

docker-compose.yml    prod version


.vscode/

    launch.json    VSCode launch configurations for FastAPI, and for single python file

    settings.json    Configuration for automated testing 

tests/

    test_api.py    tests for the api (not this only works when running from the vscode extension, 
                    it fails to pick up the REDIS_OM_URL env var when run from CLI)

