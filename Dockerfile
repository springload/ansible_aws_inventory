FROM python:3

WORKDIR /app

COPY requirements.txt ./

RUN pip install -r requirements.txt --no-cache

ARG USER_ID=1000
ARG USER_GROUP_ID=1000

RUN groupadd -g ${USER_GROUP_ID} appuser && useradd -r -u ${USER_ID} -g appuser -m -d /home/appuser appuser
USER appuser

COPY *.py ./
