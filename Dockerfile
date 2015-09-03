FROM ubuntu:trusty

RUN apt-get update && \
    apt-get install -y \
        build-essential git python3-all python3-all-dev python3-setuptools \
        curl libpq-dev ntp python3-pip python-pip

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 10

WORKDIR /app

ADD ./conf/uwsgi /etc/uwsgi

ADD ./requirements/ /app/requirements/
RUN pip3 install -r requirements/prod.txt

ADD . /app
RUN ./manage.py collectstatic --noinput

EXPOSE 8080
CMD ["/usr/local/bin/uwsgi", "--ini", "/etc/uwsgi/prisoner_location_admin.ini"]
