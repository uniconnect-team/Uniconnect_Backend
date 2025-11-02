# Dorm Owner "Your Properties" Frontend Requirements

This guide summarises how the frontend should behave now that the backend exposes
full CRUD APIs for dorm owners to manage their properties, rooms, and media.

## Entry Point and Navigation

- Rename the owner navigation item that previously pointed to the chat/favourites
  placeholder so that it now reads **"Your Properties"**.
- Ensure the owner dashboard redirects to this page after authentication. The
  authenticated user payload already ships a `default_home_path` of
  `/owners/properties` for owners, so client-side routing should respect it.
- The page is owner-only; fetch the authenticated user context first (via
  `GET /api/v1/auth/me/`) to confirm role and pre-load their existing properties.

## Page Layout Overview

Break the page into two primary regions:

1. **Property Catalogue Panel** – grid/list of the owner’s current properties,
   each rendered as a card that displays:
   - Cover image (fall back to a placeholder if `cover_image` is empty)
   - Property name and location
   - Badges for electricity / cleaning services when `true`
   - Count of published rooms
   - Quick actions: "Edit", "Manage Rooms", "Manage Gallery"
2. **Property Editor Drawer / Modal** – a multi-step form for creating or editing
   a property. The form should collect:
   - Basic info: name, location, long-form description
   - Services: multi-select chips sourced from the `amenities` JSON array, plus
     toggles for `electricity_included` and `cleaning_included`
   - Cover image upload (single file field bound to `cover_image`)
   - Optional gallery images (handled separately through the gallery manager)

When the owner presses **"Add Property"** show the editor in create mode. When
pressing **"Edit"** populate the form using the selected property’s data.

## Backend Resources Recap

All endpoints live under `/api/v1/auth/` and require the owner’s JWT.

### Properties

- `GET /owner/properties/` – list the owner’s properties (includes nested rooms
  and gallery metadata).
- `POST /owner/properties/` – create a property. Payload mirrors the
  `PropertySerializer` (see below). Send form-data when uploading images.
- `PATCH /owner/properties/{id}/` – update an existing property. Include only the
  fields that changed; when `rooms` or `images` arrays are present the backend
  replaces the previous set with the new one.
- `DELETE /owner/properties/{id}/` – remove a property owned by the user.

**Serializer fields:**

```jsonc
{
  "name": "Dorm Alpha",
  "location": "Hamra, Beirut",
  "description": "Walking distance to campus...",
  "cover_image": File | null,
  "amenities": ["Wi-Fi", "Laundry"],
  "electricity_included": true,
  "cleaning_included": false,
  "rooms": [
    {
      "name": "Single Room A",
      "room_type": "SINGLE",
      "description": "Cozy single room",
      "price_per_month": "450.00",
      "capacity": 1,
      "available_quantity": 3,
      "amenities": ["Balcony"],
      "electricity_included": true,
      "cleaning_included": true,
      "is_active": true,
      "images": []
    }
  ],
  "images": [
    {"image": File, "caption": "Street view"}
  ]
}
```

> Rooms and gallery images can be sent inline during create/update, but the UI
> will likely manage them through the dedicated room & media sections described
> below.

### Rooms

Rooms belong to a property and can also be managed via standalone endpoints.

- `GET /owner/rooms/?property={propertyId}` – list rooms, optionally filtered by
  property.
- `POST /owner/rooms/` – create a room. Required fields: `property`, `name`,
  `room_type`, `price_per_month`, `capacity`, `available_quantity`.
- `PATCH /owner/rooms/{id}/` – update room details (amenities, quantities,
  service toggles, etc.).
- `DELETE /owner/rooms/{id}/` – delete a room.

The response includes an `images` array that should feed the room gallery UI.

### Property Gallery Images

- `GET /owner/property-images/?property={propertyId}` – fetch gallery assets.
- `POST /owner/property-images/` – upload a new image (`property`, `image`,
  optional `caption`). Use multipart form-data.
- `DELETE /owner/property-images/{id}/` – remove a gallery image.

### Room Gallery Images

- `GET /owner/room-images/?room={roomId}` – fetch images tied to a room.
- `POST /owner/room-images/` – upload room photos (`room`, `image`, optional
  `caption`).
- `DELETE /owner/room-images/{id}/` – delete an image.

## Frontend Workflow Suggestions

1. **Initial Load**
   - Call `GET /api/v1/auth/me/` to confirm the user is an owner and capture the
     lightweight property summary for badges/counters.
   - Fetch the detailed property list via `GET /api/v1/auth/owner/properties/`.

2. **Creating a Property**
   - Open the editor modal with empty fields.
   - Submit via `POST /api/v1/auth/owner/properties/`.
   - After success, refresh the list or optimistically append the returned
     property.

3. **Editing a Property**
   - Populate the form with the selected property’s data.
   - Submit via `PATCH /api/v1/auth/owner/properties/{id}/`.
   - Because the backend replaces `rooms` and `images` when they’re present, send
     only the fields being changed to avoid wiping nested data.

4. **Managing Rooms**
   - Present a dedicated panel/drawer after clicking "Manage Rooms".
   - List rooms with their availability counters and service badges.
   - Allow add/edit/delete using the room endpoints. Each room card can include a
     "Manage Photos" button that opens the room gallery manager.

5. **Gallery Management**
   - For property-level galleries, show existing thumbnails with delete icons and
     an upload dropzone tied to the property image endpoints.
   - For room-level galleries, reuse the same pattern but point to the room image
     endpoints. Support multiple uploads per room so the UI can render a carousel
     (with arrow controls) in previews.

6. **Status Messaging**
   - Display success/error toasts for create/update/delete actions.
   - Surface validation errors returned by the API (e.g., missing required fields
     or trying to manipulate another owner’s data) near the relevant form fields.

## Additional Notes

- `amenities` fields are free-form arrays of strings; provide an autocomplete or
  tag input so owners can type services like "Breakfast" or "24/7 electricity".
- Monetary values (`price_per_month`) are decimal strings. Validate format before
  submission.
- When owners delete a property, remove it from the list immediately and handle
  the empty-state UI (e.g., illustration + "Add your first property" CTA).
- Respect pagination once implemented. The current API returns all results, but
  design the UI so pagination or infinite scroll can be added later without major
  rework.
