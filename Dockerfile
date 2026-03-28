# Dockerfile
#
# WHY: A Docker image makes Gauntlet portable — anyone can run it without
# installing Python or managing virtualenvs. We use python:3.12-slim (not
# the full image) to keep the image small (~120MB vs ~900MB).
#
# The API key is intentionally NOT baked into the image. It is passed at
# runtime via `-e ANTHROPIC_API_KEY=sk-...` so secrets never touch the
# image layer (and can't be extracted with `docker history`).

FROM python:3.12-slim

# Set a clean working directory inside the container
WORKDIR /app

# WHY copy requirements first: Docker caches layers. If we copy source code
# first, any code change invalidates the pip install layer. Copying only the
# install config first means `pip install` is re-run only when dependencies
# change — not on every code edit.
COPY pyproject.toml ./

# Install the package and its dependencies.
# --no-cache-dir keeps the image smaller (pip's download cache is useless
# inside a disposable container layer).
RUN pip install --no-cache-dir -e ".[dev]"

# Now copy all source code (this layer re-builds on code changes)
COPY . .

# Expose the FastAPI port
EXPOSE 8000

# Default command: start the REST API.
# Override with `docker run gauntlet gauntlet run --goal "..."` for CLI use.
CMD ["gauntlet", "serve", "--host", "0.0.0.0", "--port", "8000"]
