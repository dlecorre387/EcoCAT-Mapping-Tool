# Build using the base Tethys Platform image (latest build)
FROM tethysplatform/tethys-core:latest

# Copy all app files
COPY tethysapp-ecocat ${TETHYS_HOME}/apps/tethysapp-ecocat

# Activate the Conda environment 'tethys'
ARG MAMBA_DOCKERFILE_ACTIVATE=1

# Change to the app directory and install it to the Tethys Portal
RUN cd ${TETHYS_HOME}/apps/tethysapp-ecocat && tethys install --no-db-sync

# Expose port 80
EXPOSE 80

# Set the work directory to the Tethys home directory
WORKDIR ${TETHYS_HOME}

# Set the default command that is executed when the container starts
CMD bash run.sh