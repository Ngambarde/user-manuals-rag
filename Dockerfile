# --- Build Stage ---
# his stage is used to install our dependencies. This ensures that
# build tools like pip, and any system libraries, needed for installation
# are not included in the final, lean production image.
FROM python:3.11-slim as builder

# Installs build-time system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Creating a virtual environment inside the builder allows for a cleanway to
# manage dependencies. It encapsulates all the packages and makes it easier
# to copy to the final stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copying requirements.txt first leverages Docker's layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# --- Final Stage ---
# This is the image that will actually deploy. Starting from a fresh, clean
# base image to ensure it's as small as possible and contains nothing but
# what is essential for running the application.
FROM python:3.11-slim

# Installs runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends libgl1-mesa-glx && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Creating a dedicated, non-root user to run the application.
RUN addgroup --system appgroup && adduser --system --group --no-create-home appuser

# This is the benefit of the multi-stage build approach. By copying ONLY the installed
# virtual environment from the "builder" stage gives all the
# dependencies without any of the build-time bloat.
COPY --from=builder /opt/venv /opt/venv

# Copies the application source code into the final image.
COPY . .

# Sets the PATH to include the virtual environment's bin directory, so that
# when "python" is ran, it uses the one from the venv. Then, the
# ownership of the application directory is set to the new user.
ENV PATH="/opt/venv/bin:$PATH"
RUN chown -R appuser:appgroup /app

# Switches from the default 'root' user to the
# unprivileged 'appuser'. Any subsequent commands will thus run as this user.
USER appuser

# This is the command that will be executed when the container starts
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"] 