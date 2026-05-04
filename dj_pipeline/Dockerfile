FROM deeplabcut/deeplabcut:2.3.5-core-cuda11.7.1-cudnn8-runtime-ubuntu20.04-latest 
#mysql:debian

WORKDIR /
RUN apt-get -o Acquire::Retries=10 -o Acquire::http::Timeout=30 update -y \
    && apt-get install -yy --no-install-recommends \
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

RUN pip install --no-cache-dir datajoint==0.14 \
    # Note: this version of seaborn, as otherwise it installs 0.12.2 and updates numpy to 1.26,
    # and then Numba stops to work: err "Numba needs NumPy 1.24 or less" 
    seaborn==0.13.0 \
    pandas==1.4.3 \
    numpy==1.22.4 \
    jupyter \
    umap-learn \
    black==22.6
    # TODO: make pip via req
    # with newer 2.0.3, tom's code fails 

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

