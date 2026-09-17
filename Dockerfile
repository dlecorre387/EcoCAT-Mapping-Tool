# Build using the base Tethys Platform image (latest build)
FROM tethysplatform/tethys-core:4.3.8-py3.12-dj5.2

# Define some environment variables
ENV DEBUG="False"
ENV ENABLE_OPEN_SIGNUP="False"
ENV ALLOWED_HOSTS="\"[localhost, 34.89.123.66, 34.39.95.217, map.ecocatproject.org]\""
ENV CRSF_TRUST_ORIGINS="\"[http://localhost, http://34.89.123.66, http://34.39.95.217, https://map.ecocatproject.org]\""
ENV SITE_TITLE="EcoCAT"
ENV APPS_LIBRARY_TITLE="Tools"
ENV FAVICON="tethys_portal/images/kew_logo_square_black.png"
ENV BRAND_IMAGE="tethys_portal/images/kew_logo_square_white.png"
ENV BRAND_IMAGE_PADDING="0"
ENV BRAND_TEXT="EcoCAT (Ecosystem Conservation Assessment Tools)"
ENV PRIMARY_COLOR='#669900'
ENV SECONDARY_COLOR='#CDDC00'
ENV BACKGROUND_COLOR='#ffffff'
ENV PRIMARY_TEXT_COLOR='#ffffff'
ENV PRIMARY_TEXT_HOVER_COLOR='#ffffff'
ENV SECONDARY_TEXT_COLOR='#000000'
ENV SECONDARY_TEXT_HOVER_COLOR='#000000'
ENV FOOTER_COPYRIGHT="Copyright © 2026 Royal Botanic Gardens, Kew"
ENV NGINX_PORT=8080
ENV BYPASS_TETHYS_HOME_PAGE="True"
ENV STANDALONE_APP="ecocat"
ENV MULTIPLE_APP_MODE="False"
ENV DATA_UPLOAD_MAX_MEMORY_SIZE=10000000

# Copy all app files
COPY tethysapp-ecocat-gcp ${TETHYS_HOME}/apps/tethysapp-ecocat

# Activate the Conda environment 'tethys'
ARG MAMBA_DOCKERFILE_ACTIVATE=1

# Change to the app directory and install it to the Tethys Portal
RUN cd ${TETHYS_HOME}/apps/tethysapp-ecocat && tethys install

# Expose port 8080
EXPOSE 8080/tcp

# Set the work directory to the Tethys home directory
WORKDIR ${TETHYS_HOME}

# Set the default command that is executed when the container starts
CMD bash run.sh
