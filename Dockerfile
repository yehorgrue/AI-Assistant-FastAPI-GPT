# syntax=docker/dockerfile:1

FROM python:3.11.2-slim-buster

WORKDIR /code

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV HNSWLIB_NO_NATIVE 1 

# install system dependencies
RUN apt-get update \
  && apt-get -y install build-essential \
  && apt-get -y install netcat gcc \
  && apt-get clean

# install python dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app
COPY /.env /code/.env
COPY /azara-ai_service_account_keys.json /code/azara-ai_service_account_keys.json

EXPOSE 9000

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "9000", "--reload", "--log-level=debug"]