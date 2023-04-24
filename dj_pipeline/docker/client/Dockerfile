FROM python:3.8

ARG user
ARG usern

RUN mkdir -p /home /app /app/data /storage

RUN useradd -d /home -s /bin/bash -u $user $usern
RUN chown -R $user /home
RUN chown -R $usern /app /storage /app/data /home/

RUN pip3 install --upgrade --no-cache-dir notebook pytest tqdm joblib datajoint seaborn scipy

USER $usern
ENV PYTHONPATH="/home/vr4mice/:/home/.local/bin:${PYTHONPATH}"

