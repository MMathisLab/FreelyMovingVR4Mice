FROM nvidia/cuda:12.0.0-cudnn8-runtime-ubuntu22.04

WORKDIR /

RUN apt-get update -yy \
	&& apt-get install -yy --no-install-recommends python3.10 python3-pip python3.10-venv python3-opencv python3-tk ffmpeg libsm6 libxext6 \
	&& apt-get install -yy --no-install-recommends build-essential make cmake gcc g++ nvidia-modprobe \
	&& apt-get install -yy --no-install-recommends libgl1-mesa-glx libglib2.0-0 libxrender-dev libxrandr2 libxcursor1 libxinerama1 libxi6 \
	&& apt-get install -yy --no-install-recommends xvfb wget curl git unzip \
	&& apt-get clean \
	&& rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1

COPY ./requirements.txt .
COPY --from=mlagents . /ml-agents/
# COPY --from=vr4mice . /vr4mice/
# RUN pip3 install --upgrade pip 
RUN pip3 install --no-cache-dir -r requirements.txt \
	&& pip uninstall -y tensorflow keras tensorflow-io-gcs-filesystem \
	&& pip install /ml-agents/ml-agents-envs/ \
	# && pip install -e /vr4mice/ \
	&& rm -rf /ml-agents

ARG user_name
ARG uid
ARG gid

RUN mkdir /app /logs
RUN groupadd -g ${gid} ${user_name} \
	&& useradd -m -u ${uid} -g ${gid} ${user_name}

COPY AR_build/ /app/environments/
COPY .env /app/.env
RUN find /app/environments/ -type f -name "*.x86_64" -exec chmod +x {} \;

RUN chown -R ${uid}:${gid} /home /app /logs

WORKDIR /app
USER ${user_name}

ENV PYTHONPATH="${PYTHONPATH}:/app"

ENTRYPOINT ["bash"]