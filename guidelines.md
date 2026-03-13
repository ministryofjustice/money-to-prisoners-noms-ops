# Prisoner Money Intelligence (NOMS Ops) Development Guidelines

## Project Overview and Core Functions

The Prisoner Money Intelligence (NOMS Ops) application is the operational oversight site for HMPPS staff. It provides tools for security teams to monitor and manage prisoner money activities, conduct security checks, and ensure the integrity of the system.

### Core Functionalities
- **Security Dashboard**: Provides high-level visibility into transactional data and security-related alerts.
- **Security Checks**: Facilitates the manual review and actioning of credits that trigger security alerts.
- **Review and Monitoring**: Allows staff to monitor sender and prisoner profiles for suspicious behavior.
- **Prisoner Location Administration**: Manages and uploads prisoner location data to ensure accurate fund distribution.
- **Intelligence Reports**: Provides data for operational oversight and investigation.

## Application Architecture

The project is built with **Django** and relies on the `money-to-prisoners-api` for its data and core business logic. It also integrates with HMPPS external services for real-time prisoner data.

### HMPPS API Integrations

The application interacts with HMPPS APIs using **HMPPS Auth** (OAuth2 client credentials). Key integrations include:

- **HMPPS Prison API (NOMIS)**:
  - `GET /api/v1/offenders/{prisoner_number}/image`: Fetches prisoner photographs for security profiles.
  - `GET /api/v1/offenders/{prisoner_number}/location`: Retrieves real-time housing location within a prison.
- **HMPPS Offender Search API**:
  - `GET /prison/{prison_id}/prisoners`: Used by management commands to bulk-load prisoner location data for accurate fund matching.

### Key Project Apps
- **`security` (`mtp_noms_ops.apps.security`)**: The primary application containing most of the business logic for intelligence and oversight.
- **`prisoner_location_admin` (`mtp_noms_ops.apps.prisoner_location_admin`)**: Handles prisoner location updates.
- **`mtp_auth` (`mtp_noms_ops.apps.mtp_auth`)**: Manages authentication and user permissions.
- **`mtp_common`**: A shared library used across all MTP projects for consistent styling, utilities, and common logic.

## Build and Configuration

- **Environment**: Requires Python 3.12+ and Node.js 24+.
- **Virtual Environment**: Use a Python virtual environment to isolate dependencies.
  ```shell
  python3 -m venv venv
  source venv/bin/activate
  ```
- **Dependencies**: Managed via `run.py`. To update all dependencies:
  ```shell
  ./run.py dependencies
  ```
- **Configuration**:
  - The application connects to the API (default `http://localhost:8000`).
  - Local settings can be overridden in `mtp_noms_ops/settings/local.py` (copy from `local.py.sample`).
- **Management Script**: `run.py` is the primary interface for development tasks.
  - `./run.py serve`: Start development server with live-reload (BrowserSync on `:3003`, Django on `:8003`).
  - `./run.py start`: Start development server without live-reload.
  - `./run.py --verbosity 2 help`: List all available build tasks.

## Testing

### Running Tests
- **Full Suite**: Use `./run.py test`. This includes building assets and running Django tests.
- **Django Tests Only**: For faster feedback during development, run `manage.py test` directly:
  ```shell
  ./manage.py test security
  ./manage.py test mtp_noms_ops.apps.<app>.tests.<test_module>
  ```

### Adding New Tests
- Tests are located in `mtp_noms_ops/apps/<app_name>/tests/`.
- Use standard Django `TestCase` or `SimpleTestCase`.
- Functional tests are located in `test_functional.py` or within the `test_views` package.

## Additional Development Information

- **Frontend Assets**:
  - Assets are located in `assets-src/`.
  - Built assets are placed in `assets/`.
  - Use `./run.py build` to compile assets (SASS and JavaScript).
- **Translations**:
  - Update messages with `./run.py make_messages`.
  - Sync with Transifex via `./run.py translations --pull` or `--push`.
- **Code Style**:
  - Follow PEP8 and Django coding conventions.
  - Linting can be checked via `./run.py lint`.
- **Docker**:
  - A Docker environment is available for local testing that mirrors production: `./run.py local_docker`.
