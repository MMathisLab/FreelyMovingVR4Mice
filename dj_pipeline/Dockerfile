FROM deeplabcut/deeplabcut:2.3.5-core-cuda11.7.1-cudnn8-runtime-ubuntu20.04-latest 
#mysql:debian

WORKDIR /
RUN apt-get update -y && apt-get install -yy --no-install-recommends \
    libgl1 \
    build-essential make \
    perl libnet-ssleay-perl libio-socket-ssl-perl \
    sendemail msmtp ca-certificates \
    mysql-client \ 
    graphviz \
    vim \ 
    && apt-get -y autoclean \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN pip install datajoint==0.12.5b1 \
    # Note: this version of seaborn, as otherwise it installs 0.12.2 and updates numpy to 1.26,
    # and then Numby stops to work: err "Numba needs NumPy 1.24 or less" 
    seaborn==0.13.0 \
    pandas==1.4.3 \
    numpy==1.22.4 \
    jupyter \
    umap \ 
    black==22.6
    # TODO: make pip via req
    # with newer 2.0.3, tom's code fails 

ARG user_name
ARG uid
ARG gid
#ARG base_schemas_path
#ARG base_actions_path

RUN mkdir /app /logs
RUN groupadd -g ${gid} ${user_name} \
    && useradd -m -u ${uid} -g ${gid} ${user_name}

#COPY ${mysql_config_path} /home/${user_name}
RUN chown -R ${uid}:${gid} /home /app /logs

#COPY ${base_schemas_path} . 
#COPY ${base_actions_path} . 
#RUN pip3 install ./base_schemas 
#RUN pip3 install ./base_actions

WORKDIR /app
USER ${user_name}
#RUN pip3 install -e .

EXPOSE 3306

ENTRYPOINT ["bash"]

