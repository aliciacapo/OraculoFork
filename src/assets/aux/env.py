from os import environ

# Load environment variables from .env file only if not in Docker
# Docker containers should use environment variables passed by Docker Compose
if not environ.get('DOCKER_CONTAINER'):
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("[ENV] Loaded .env file for local development")
    except ImportError:
        # dotenv not available, skip loading
        print("[ENV] dotenv not available, using system environment variables")
        pass
else:
    print("[ENV] Running in Docker container, using Docker environment variables")

env = environ