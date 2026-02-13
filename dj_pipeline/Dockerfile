FROM deeplabcut/deeplabcut:3.0.0-jupyter-cuda12.4-cudnn9
#mysql:debian

WORKDIR /
RUN apt-get update -y && apt-get install -yy --no-install-recommends \
    libgl1 \
    build-essential make \
    perl libnet-ssleay-perl libio-socket-ssl-perl \
    sendemail msmtp ca-certificates \
    mysql-client \
    graphviz \
    gosu \
    vim \
    && apt-get -y autoclean \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN pip install -U pip setuptools wheel packaging

# Install packages - base image already has numpy/pandas/jupyter from conda
# Only override what's necessary, add test dependencies
RUN pip install --no-cache-dir --no-deps datajoint==2.0.1 && \
    pip install pymysql cryptography minio pydantic-settings deepdiff && \
    pip install seaborn umap-learn black==22.6 && \
    pip install pytest pytest-cov scipy tables 

ARG user_name=user
ARG uid=1000
ARG gid=1000

RUN mkdir /app /logs
RUN groupadd -g ${gid} ${user_name} \
    && useradd -m -u ${uid} -g ${gid} ${user_name}

RUN chown -R ${uid}:${gid} /home /app /logs

WORKDIR /app
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 3306

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]

