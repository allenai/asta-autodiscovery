FROM python:3.12-alpine

WORKDIR /sonar

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY ping.py .

ENV PYTHONUNBUFFERED=1

ENTRYPOINT [ "python" ]
CMD [ "ping.py" ]
