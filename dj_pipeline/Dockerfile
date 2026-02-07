FROM deeplabcut/deeplabcut:latest-jupyter 
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

RUN pip install -U pip setuptools wheel packaging

# Install packages - base image already has numpy/pandas/jupyter from conda
# Only override what's necessary, add test dependencies
RUN pip install --no-deps datajoint==2.0.1 && \
    pip install pymysql cryptography minio pydantic-settings deepdiff && \
    pip install seaborn umap-learn black==22.6 && \
    pip install pytest pytest-cov scipy tables 

# Default values for CI workflow, will be overridden by build args
ARG user_name=user
ARG uid=1000
ARG gid=1000
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

