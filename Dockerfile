# Build using the base Tethys Platform image (latest build)
FROM tethysplatform/tethys-core:4.3.8-py3.12-dj5.2

# Define some environment variables to configure the Tethys Portal
ENV DEBUG="False"
ENV ALLOWED_HOSTS="\"[localhost, 34.89.123.66, 34.39.95.217, map.ecocatproject.org]\""
ENV CRSF_TRUST_ORIGINS="\"[http://localhost, http://34.89.123.66, https://34.39.95.217, https://map.ecocatproject.org]\""

# Copy all app files
COPY tethysapp-ecocat-gcp ${TETHYS_HOME}/apps/tethysapp-ecocat
COPY portal_images/ /tmp/custom_theme/images/

# Activate the Conda environment 'tethys'
ARG MAMBA_DOCKERFILE_ACTIVATE=1

# Change to the app directory and install it to the Tethys Portal
RUN cd ${TETHYS_HOME}/apps/tethysapp-ecocat && tethys install

# Add salt files
COPY salt/ /srv/salt/

# Configure the Tethys Portal
RUN tethys settings --set TETHYS_PORTAL_CONFIG.BYPASS_TETHYS_HOME_PAGE true 
RUN tethys settings --set TETHYS_PORTAL_CONFIG.ENABLE_OPEN_SIGNUP false
RUN tethys settings --set TETHYS_PORTAL_CONFIG.ENABLE_OPEN_PORTAL false
RUN tethys settings --set TETHYS_PORTAL_CONFIG.MULTIPLE_APP_MODE false
RUN tethys settings --set TETHYS_PORTAL_CONFIG.STANDALONE_APP ecocat
RUN tethys settings --set DATABASES.DATA_UPLOAD_MAX_MEMORY_SIZE 10000000

# Expose port 8080
EXPOSE 8080/tcp

# Set the work directory to the Tethys home directory
WORKDIR ${TETHYS_HOME}

# Set the default command that is executed when the container starts
CMD bash run.sh
