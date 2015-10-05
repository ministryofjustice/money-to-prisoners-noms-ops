FROM ubuntu:trusty

RUN locale-gen "en_US.UTF-8"
ENV LC_CTYPE=en_US.UTF-8

RUN apt-get update && \
    apt-get install -y software-properties-common python-software-properties

RUN add-apt-repository -y ppa:chris-lea/node.js

RUN apt-get update && \
    apt-get install -y \
        build-essential git python3-all python3-all-dev python3-setuptools \
        curl libpq-dev ntp python3-pip python-pip nodejs

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 10

WORKDIR /app

RUN npm install npm -g
RUN npm config set python python2.7
RUN npm install -g bower gulp

ADD ./conf/uwsgi /etc/uwsgi

ADD ./requirements/ /app/requirements/
RUN pip3 install -r requirements/prod.txt

ADD .bowerrc bower.json package.json README.md /app/
RUN npm install --unsafe-perm

ADD . /app
RUN gulp
RUN ./manage.py collectstatic --noinput

EXPOSE 8080
CMD ["/usr/local/bin/uwsgi", "--ini", "/etc/uwsgi/prisoner_location_admin.ini"]
