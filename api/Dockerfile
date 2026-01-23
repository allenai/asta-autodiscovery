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

# Copy and install devtools package (for replay functionality)
COPY packages/devtools /tmp/devtools
RUN pip install /tmp/devtools

# Install Python dependencies
COPY api/requirements.txt .
RUN pip install -r requirements.txt

# Copy over the source code
COPY api/ .

# Kick things off
ENTRYPOINT [ "/api/dev.sh" ]
