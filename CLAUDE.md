# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Commands

#### Docker (Primary Development Environment)
This project uses Docker for local development with Just as a task runner:

```bash
# Build Docker containers
just build

# Start development environment
just up

# Stop containers
just down

# Remove containers and volumes
just prune

# View logs
just logs [service]

# Run Django management commands
just manage <command>
```

#### Python/Django Commands
```bash
# Run tests
pytest

# Type checking
mypy xamu

# Code formatting and linting
ruff check .
ruff format .

# Django template linting
djlint --check .

# Test coverage
coverage run -m pytest
coverage html

# Create superuser (via Docker)
just manage createsuperuser

# Database migrations
just manage makemigrations
just manage migrate
```

#### Frontend Commands
```bash
# Development server with hot reload
npm run dev

# Production build
npm run build
```

#### Celery Commands (via Docker)
```bash
# Run Celery worker
just manage shell -c "celery -A config.celery_app worker -l info"

# Run Celery beat scheduler
just manage shell -c "celery -A config.celery_app beat"
```

### Testing Commands
```bash
# Run all tests
pytest

# Run specific test file
pytest xamu/users/tests/test_models.py

# Run tests with coverage
coverage run -m pytest

# Generate coverage report
coverage html
```

## Architecture

### Project Structure
- **Django Backend**: Main application framework with custom User model using email authentication
- **Docker-based Development**: Complete containerized environment with docker-compose
- **Webpack Frontend**: Modern JavaScript/CSS build pipeline with Bootstrap 5
- **Celery Integration**: Asynchronous task processing with Redis/database broker
- **API Layer**: Django REST Framework with automatic OpenAPI documentation

### Key Components

#### User Management (`xamu/users/`)
- Custom User model with email-based authentication (no username)
- Django Allauth integration for social authentication
- REST API endpoints for user operations
- Comprehensive test coverage

#### Settings Architecture (`config/settings/`)
- Base settings with environment-specific overrides
- Local, production, and test configurations
- Environment variable management with django-environ

#### API Structure (`config/api_router.py`)
- Centralized API routing with DRF
- Automatic API documentation via drf-spectacular
- Token-based authentication support

#### Frontend Pipeline
- Webpack configuration for JS/CSS bundling
- Bootstrap 5 with custom SCSS variables
- Separate vendor and project bundles
- Hot reload support in development

### Database
- PostgreSQL (configured via DATABASE_URL environment variable)
- Atomic transactions enabled by default
- Migration files in standard Django locations

### Static Assets
- Webpack bundles in `xamu/static/webpack_bundles/`
- SCSS compilation with Bootstrap customization
- Static file serving configured for both development and production

### Internationalization
- Multi-language support configured (English, French, Portuguese)
- Translation files in `locale/` directory
- UTC timezone with i18n enabled

## Development Workflow

### Local Development Setup
1. Use `just up` to start the Docker environment
2. Use `just manage migrate` to apply database migrations
3. Use `just manage createsuperuser` to create an admin user
4. Frontend assets are built automatically via webpack

### Code Quality
- Ruff for Python linting and formatting (configured in pyproject.toml)
- MyPy for type checking
- djLint for Django template linting
- Pre-configured with extensive rule sets

### Testing Strategy
- pytest with Django integration
- Coverage reporting with django-coverage-plugin
- Factory-based test data generation
- API testing with DRF test client

### Email Development
- Mailpit container for local email testing
- Access web interface at http://127.0.0.1:8025

## Key Configuration Files
- `pyproject.toml`: Python tooling configuration (pytest, mypy, ruff, djlint)
- `justfile`: Docker-based development commands
- `docker-compose.local.yml`: Local development environment
- `webpack/`: Frontend build configuration
- `config/settings/`: Django settings modules