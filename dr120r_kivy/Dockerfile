# ════════════════════════════════════════════════════════
# DR-120R Kivy Android APK Builder
# ════════════════════════════════════════════════════════
# Build:  docker build -t dr120r-builder .
# Run:    docker run --rm -v $(pwd)/output:/output dr120r-builder
# APK จะอยู่ที่: ./output/DR-120R-1.0.0-arm64-v8a-debug.apk
# ════════════════════════════════════════════════════════

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH=$PATH:$JAVA_HOME/bin:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools

# ── 1. System dependencies ──
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    git zip unzip curl wget \
    openjdk-17-jdk \
    build-essential \
    libssl-dev libffi-dev \
    libltdl-dev \
    autoconf automake libtool \
    pkg-config \
    zlib1g-dev \
    libncurses5-dev libncursesw5-dev \
    libreadline-dev \
    libsqlite3-dev \
    libbz2-dev \
    libexpat1-dev \
    liblzma-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── 2. Python packages ──
RUN pip3 install --upgrade pip && \
    pip3 install \
        buildozer==1.5.0 \
        cython==3.0.11 \
        kivy==2.3.0 \
        pillow

# ── 3. Android SDK command-line tools ──
RUN mkdir -p $ANDROID_HOME/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip \
         -O /tmp/cmdtools.zip && \
    unzip -q /tmp/cmdtools.zip -d /tmp/cmdtools && \
    mv /tmp/cmdtools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest && \
    rm /tmp/cmdtools.zip

ENV PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin

# ── 4. Accept licenses ──
RUN yes | sdkmanager --licenses >/dev/null 2>&1 || true && \
    sdkmanager \
        "platform-tools" \
        "platforms;android-33" \
        "build-tools;33.0.2" \
        "ndk;25.2.9519653"

ENV ANDROID_NDK_HOME=$ANDROID_HOME/ndk/25.2.9519653

# ── 5. Copy app source ──
WORKDIR /app
COPY app/ .

# ── 6. Build APK ──
RUN buildozer android debug 2>&1 | tee /build.log

# ── 7. Copy APK to output ──
CMD ["/bin/bash", "-c", "\
    mkdir -p /output && \
    find /app/bin -name '*.apk' -exec cp {} /output/ \\; && \
    echo '' && \
    echo '════════════════════════════════════' && \
    echo '✅  BUILD SUCCESS' && \
    echo '════════════════════════════════════' && \
    ls -lh /output/*.apk && \
    echo '' \
"]
