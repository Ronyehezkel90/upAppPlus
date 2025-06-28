# Use Android emulator base image that supports arm64
FROM budtmo/docker-android:emulator_11.0

# Set environment variables
ENV ANDROID_SDK_ROOT=/opt/android
ENV ANDROID_HOME=/opt/android
ENV PATH=${PATH}:${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools:${ANDROID_SDK_ROOT}/emulator

# Install Python and required packages
USER root
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create android user directories
RUN mkdir -p /opt/android/avd

# Switch to android user
USER android

# Copy AVD configuration
COPY docker/avd/config.ini /opt/android/avd/maccabi_scraper_avd.avd/config.ini
COPY docker/avd/maccabi_scraper_avd.ini /opt/android/avd/maccabi_scraper_avd.ini

# Create userdata-qemu.img for the AVD
RUN mkdir -p /opt/android/avd/maccabi_scraper_avd.avd

# Copy Python application
COPY --chown=android:android . /app
WORKDIR /app

# Install Python dependencies
RUN python3 -m pip install --user --no-cache-dir \
    requests \
    beautifulsoup4 \
    selenium

# Set AVD environment
ENV DEVICE="Samsung Galaxy S10e"
ENV API_LEVEL=30
ENV TARGET=google_apis
ENV ABI=arm64-v8a
ENV TAG=google_apis

# Expose ADB port
EXPOSE 5037 5554 5555

# Default command
CMD ["bash"]
