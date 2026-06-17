FROM python:3.13-slim

# Uncomment the following lines to enable GPU support.
# See https://***REMOVED***/gpu.html for more details.
#
# ENV LD_LIBRARY_PATH /usr/local/nvidia/lib:/usr/local/nvidia/lib64
# ENV NVIDIA_VISIBLE_DEVICES all
# ENV NVIDIA_DRIVER_CAPABILITIES compute,utility

WORKDIR /api

# Copy and install autodiscovery_jobs package
COPY packages/autodiscovery_jobs /tmp/autodiscovery_jobs
RUN pip install /tmp/autodiscovery_jobs

# Install Python dependencies
COPY api/requirements.txt .
RUN pip install -r requirements.txt

# Copy over the source code
COPY api/ .

# Kick things off. Default to the production entrypoint (start.sh: no --reload,
# structured JSON access logs). Under Skiff1 the prod command was overridden to
# /api/start.sh in webapp.jsonnet; Skiff2 (Cloud Run) cannot override the image
# command, so the prod entrypoint must be the image default. Local dev gets
# /api/dev.sh (hot reload) via the docker-compose `entrypoint` override.
ENTRYPOINT [ "/api/start.sh" ]
