# Directus CMS

This folder contains the local Directus setup for the clinic CMS. The `directus`
container is defined in the root `docker-compose.yml` and connects to the same
PostgreSQL database used by the API.

## Files

- root `.env` - shared environment file for API, Directus, and automation services
- `extensions/` - custom Directus extensions
- `uploads/` - uploaded files persisted outside the container

## First-time setup

1. Update the root environment file:

   ```powershell
   code .env
   ```

2. Set the `DIRECTUS_*` variables in the root `.env`.
   Use a real email format such as `admin@example.com`; Directus rejects
   placeholder addresses like `.local` during bootstrap.

3. Make sure the host PostgreSQL service is running and reachable at
   `host.docker.internal:5432` from Docker.

4. Start Directus:

   ```powershell
   docker compose up -d directus
   ```

5. Open Directus at [http://localhost:8055](http://localhost:8055).

On first start, Directus will create its own `directus_*` system tables in the
`dental_clinic` database. Your existing clinic tables remain available in the
same database and can be registered in Directus as SQL collections.

## Notes

- The API connects to PostgreSQL on `localhost:5432`.
- The Directus container connects to the host PostgreSQL instance through
  `host.docker.internal:5432`.
- Uploaded files are stored in `apps/cms/uploads`.
- Add custom hooks, interfaces, or endpoints under `apps/cms/extensions`.
