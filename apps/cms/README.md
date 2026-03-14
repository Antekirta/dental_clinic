# Directus CMS

This folder contains the local Directus setup for the clinic CMS. The `directus`
container is defined in the root `docker-compose.yml` and connects to the same
PostgreSQL database used by the API.

## Files

- `.env` - local Directus secrets and database connection settings
- `extensions/` - custom Directus extensions
- `uploads/` - uploaded files persisted outside the container

## First-time setup

1. Copy the example environment file:

   ```powershell
   Copy-Item apps/cms/.env.example apps/cms/.env
   ```

2. Update `KEY`, `SECRET`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`.
   Use a real email format such as `admin@example.com`; Directus rejects
   placeholder addresses like `.local` during bootstrap.

3. Start PostgreSQL and Directus:

   ```powershell
   docker compose up -d db directus
   ```

4. Open Directus at [http://localhost:8055](http://localhost:8055).

On first start, Directus will create its own `directus_*` system tables in the
`dental_clinic` database. Your existing clinic tables remain available in the
same database and can be registered in Directus as SQL collections.

## Notes

- The API currently connects to PostgreSQL on `localhost:5434`, while the
  Directus container connects to the Compose service host `db:5432`.
- Uploaded files are stored in `apps/cms/uploads`.
- Add custom hooks, interfaces, or endpoints under `apps/cms/extensions`.
