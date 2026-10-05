# Build using the base Tethys Platform image (latest build)
FROM tethysplatform/tethys-core:4.3.8-py3.12-dj5.2

# Define some environment variables to configure the Tethys Portal
ENV DEBUG="False"
ENV ALLOWED_HOSTS="\"[localhost, 34.89.123.66, 34.39.95.217, map.ecocatproject.org]\""
ENV CRSF_TRUST_ORIGINS="\"[http://localhost, http://34.89.123.66, https://34.39.95.217, https://map.ecocatproject.org]\""

# Copy all app files
COPY tethysapp-ecocat-gcp ${TETHYS_HOME}/apps/tethysapp-ecocat

# Activate the Conda environment 'tethys'
ARG MAMBA_DOCKERFILE_ACTIVATE=1

# Change to the app directory and install it to the Tethys Portal
RUN cd ${TETHYS_HOME}/apps/tethysapp-ecocat && tethys install

# Configure the Tethys Portal
RUN tethys settings --set TETHYS_PORTAL_CONFIG.BYPASS_TETHYS_HOME_PAGE true \
                    TETHYS_PORTAL_CONFIG.ENABLE_OPEN_SIGNUP false \
                    TETHYS_PORTAL_CONFIG.ENABLE_OPEN_PORTAL false \
                    TETHYS_PORTAL_CONFIG.MULTIPLE_APP_MODE false \
                    TETHYS_PORTAL_CONFIG.STANDALONE_APP ecocat \
                    DATABASES.DATA_UPLOAD_MAX_MEMORY_SIZE 10000000

# Configure the Tethys Portal site settings
RUN tethys site --site-title "EcoCAT" \
                --brand-text "EcoCAT (Ecosystem Conservation Assessment Tools)" \
                --brand-image "tethys_portal/images/EcoCAT_RGB_W.png" \
                --favicon "tethys_portal/images/EcoCAT_RGB_W_favicon.png" \
                --brand-image-padding 0 \
                --apps-library-title "Tools" \
                --primary-color "#669900" \
                --secondary-color "#CDDC00" \
                --primary-text-color "#ffffff" \
                --primary-text-hover-color "#ffffff" \
                --secondary-text-color "#000000" \
                --secondary-text-hover-color "#000000" \
                --background-color "#ffffff" \
                --copyright "Copyright © 2026 Daniel Le Corre, Rob Critchlow, Tarciso Leão"

# Copy the app images to the static directory
RUN cp ${TETHYS_HOME}/apps/tethysapp-ecocat/tethysapp/ecocat/public/images/*png /var/lib/tethys_persist/static/tethys_portal/images/

# Expose port 8080
EXPOSE 8080/tcp

# Set the work directory to the Tethys home directory
WORKDIR ${TETHYS_HOME}

# Set the default command that is executed when the container starts
CMD bash run.sh
