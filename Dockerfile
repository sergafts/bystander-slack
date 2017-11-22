FROM python:3.6.3
MAINTAINER Konstantinos Bairaktaris "ikijob@gmail.com"
# RUN apt-get update -y
# RUN apt-get install -y python-pip python-dev build-essential
COPY ./web/requirements.txt /
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
WORKDIR /app
COPY . /app
ENTRYPOINT ["python"]
CMD ["web/app.py"]
