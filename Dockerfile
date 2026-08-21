# Build using the base Tethys Platform image (latest build)
FROM tethysplatform/tethys-core:latest

# Define some environment variables
ENV DEBUG="False"
ENV ALLOWED_HOSTS="\"[0.0.0.0]\""
ENV CSRF_TRUSDTED_ORIGINS="\"[http://0.0.0.0]\""
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
ENV BLURB_TEXT="EcoCAT is dedicated to making accurate ecosystem risk assessment as accessible as possible."
ENV HERO_TEXT="Welcome to EcoCAT!"
ENV FEATURE_1_HEADING="Map your ecosystem through time!"
ENV FEATURE_1_IMAGE=""
ENV FEATURE_1_BODY="With your expert knowledge, the EcoCAT Mapping Tool maps ecosystems through time by training machine learning models on satellite data available through Google Earth Engine."
ENV FEATURE_2_HEADING="Assess its risk of collapse!"
ENV FEATURE_2_IMAGE=""
ENV FEATURE_2_BODY="Ecosystem maps produced by the Mapping Tool can then be inputted into the EcoCAT Assessment Tool to determine the ecosystem's status and its risk of collapse."
ENV FEATURE_3_HEADING="Help conserve global ecosystems!"
ENV FEATURE_3_IMAGE=""
ENV FEATURE_3_BODY="EcoCAT closely follows the IUCN Red List of Ecosystems (RLE) guidelines to enable accurate and scalable assessments of the state of the world's ecosystems."
ENV ENABLE_OPEN_SIGNUP="True"
ENV MULTIPLE_APP_MODE="True"
ENV TETHYS_PORT=8080
ENV NGINX_PORT=8080

# Copy all app files
COPY tethysapp-ecocat ${TETHYS_HOME}/apps/tethysapp-ecocat

# Activate the Conda environment 'tethys'
ARG MAMBA_DOCKERFILE_ACTIVATE=1

# Change to the app directory and install it to the Tethys Portal
RUN cd ${TETHYS_HOME}/apps/tethysapp-ecocat && tethys install --no-db-sync

# Expose port 8080
EXPOSE 8080

# Set the work directory to the Tethys home directory
WORKDIR ${TETHYS_HOME}

# Set the default command that is executed when the container starts
CMD bash run.sh