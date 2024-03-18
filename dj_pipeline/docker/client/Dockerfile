FROM python:3.8

ARG user
ARG usern

RUN mkdir -p /home /app /app/data /storage

RUN useradd -d /home -s /bin/bash -u $user $usern
RUN chown -R $user /home
RUN chown -R $usern /app /storage /app/data /home/

# currently need numpy pinned to deal with np.float deprecation in datajoint 0.12.9
# also have to escape the < in numpy<=1.23
RUN pip3 install --upgrade --no-cache-dir notebook pytest tqdm joblib datajoint seaborn scipy \
    git+https://github.com/atlab/datajoint-python.git \
    pydantic>=2.6 h5py moviepy numpy\<=1.23

USER $usern
ENV PYTHONPATH="/home/vr4mice/:/home/.local/bin:${PYTHONPATH}"

