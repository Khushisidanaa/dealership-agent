# Nova Act workflow output schema

The backend reads the workflow result from S3 as JSON. It accepts **either**:

- **Option A:** A JSON **array** of listing objects.
- **Option B:** A JSON **object** with a key `"listings"` whose value is an array of listing objects.

---

## Top-level shape

**Option A (array):**
```json
[
  { ... listing ... },
  { ... listing ... }
]
```

**Option B (object with `listings`):**
```json
{
  "listings": [
    { ... listing ... },
    { ... listing ... }
  ]
}
```

---

## Listing object schema

Each element in the array is an object with these keys (all optional except you should provide at least `title` or `heading` for display).

| Key | Type | Description |
|-----|------|-------------|
| `title` | string | Display title (e.g. "2022 Honda Civic EX"). Fallback: `heading`. |
| `heading` | string | Used if `title` is missing. |
| `price` | number | Listing price. |
| `mileage` | number | Odometer miles. |
| `year` | number | Model year. |
| `make` | string | Make (e.g. "Honda"). |
| `model` | string | Model (e.g. "Civic"). |
| `listing_url` | string | URL to the listing page. |
| `image_url` | string | Main vehicle photo URL (single). |
| `image_urls` | string[] | Array of vehicle photo URLs (exterior, interior, etc.). If omitted, `image_url` is used as the only image. |
| `dealer_name` | string | Dealer name. |
| `dealer_phone` | string | Dealer phone. |
| `dealer_address` | string | Dealer full address. |
| `vehicle_id` | string | Optional unique id; default becomes `nova-1`, `nova-2`, … |

---

## Minimal example (array form)

```json
[
  {
    "title": "2022 Honda Civic EX",
    "price": 26500,
    "mileage": 12000,
    "year": 2022,
    "make": "Honda",
    "model": "Civic",
    "listing_url": "https://example-dealer.com/listing/123",
    "image_url": "https://example-dealer.com/photos/123/main.jpg",
    "image_urls": [
      "https://example-dealer.com/photos/123/main.jpg",
      "https://example-dealer.com/photos/123/interior.jpg"
    ],
    "dealer_name": "Example Honda",
    "dealer_phone": "+1-555-0100",
    "dealer_address": "123 Main St, City, ST 12345"
  }
]
```

---

## Wrapper form example

```json
{
  "listings": [
    {
      "vehicle_id": "ext-001",
      "title": "2022 Honda Civic EX",
      "price": 26500,
      "mileage": 12000,
      "year": 2022,
      "make": "Honda",
      "model": "Civic",
      "listing_url": "https://example-dealer.com/listing/123",
      "image_urls": ["https://example-dealer.com/photos/123/main.jpg"],
      "dealer_name": "Example Honda",
      "dealer_phone": "+1-555-0100",
      "dealer_address": "123 Main St, City, ST 12345"
    }
  ]
}
```

---

## Where the file goes

- **S3:** The workflow must write the JSON file to the bucket and prefix configured in `.env`:
  - `NOVA_ACT_RESULT_S3_BUCKET`
  - `NOVA_ACT_RESULT_S3_PREFIX`
- **Key pattern:** Backend looks for objects under `{prefix}/{workflowRunId}/*.json` (any key ending in `.json` in that prefix).
