export interface ServiceListItem {
  id: number | string;
  name: string;
  description: string | null;
  duration_min: number;
  base_price: number | string;
  category_name: string | null;
}

export interface ServicesResult {
  directusBaseUrl: string;
  error: string | null;
  services: ServiceListItem[];
}

function normalizeBaseUrl(baseUrl: string) {
  return baseUrl.replace(/\/+$/, "");
}

interface DirectusServiceItem {
  id: number | string;
  name?: string | null;
  description?: string | null;
  duration_min?: number | null;
  base_price?: number | string | null;
  category_id?: {
    id?: number | string;
    name?: string | null;
  } | number | string | null;
}

interface DirectusItemsResponse<T> {
  data: T[];
}

export async function fetchServices(): Promise<ServicesResult> {
  const directusBaseUrl = normalizeBaseUrl(
    import.meta.env.DIRECTUS_URL ??
      import.meta.env.PUBLIC_DIRECTUS_URL ??
      "http://127.0.0.1:8055"
  );
  const directusToken = import.meta.env.DIRECTUS_STATIC_TOKEN;
  const query = new URLSearchParams();
  query.set("filter[is_active][_eq]", "true");
  query.append("fields[]", "id");
  query.append("fields[]", "name");
  query.append("fields[]", "description");
  query.append("fields[]", "duration_min");
  query.append("fields[]", "base_price");
  query.append("fields[]", "category_id.name");
  query.set("sort", "name");

  try {
    const response = await fetch(`${directusBaseUrl}/items/services?${query.toString()}`, {
      headers: {
        Accept: "application/json",
        ...(directusToken ? { Authorization: `Bearer ${directusToken}` } : {})
      }
    });

    if (!response.ok) {
      return {
        directusBaseUrl,
        error: `API responded with ${response.status} ${response.statusText}.`,
        services: []
      };
    }

    const payload = (await response.json()) as DirectusItemsResponse<DirectusServiceItem>;
    const services = payload.data.map((service) => ({
      id: service.id,
      name: service.name ?? "Unnamed service",
      description: service.description ?? null,
      duration_min: service.duration_min ?? 0,
      base_price: service.base_price ?? 0,
      category_name:
        typeof service.category_id === "object" && service.category_id !== null
          ? service.category_id.name ?? null
          : null
    }));

    return {
      directusBaseUrl,
      error: null,
      services
    };
  } catch (error) {
    return {
      directusBaseUrl,
      error: error instanceof Error ? error.message : "Unknown fetch error.",
      services: []
    };
  }
}
