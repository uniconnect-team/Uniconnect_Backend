# UniConnect Backend

This repository now exposes the existing functionality through dedicated microservices so you can deploy each vertical independently with Docker, Kubernetes, and Minikube. The Django project and database schema remain unchanged, ensuring all current features continue to operate exactly as before.

## Microservice layout

Each microservice reuses the shared Django project while exposing only the routes it requires through a dedicated URL configuration and settings module:

| Service | Settings module | Dockerfile | Description |
|---------|-----------------|------------|-------------|
| Authentication | `uniconnect.settings_auth` | `services/auth_service/Dockerfile` | Registration and login flows for seekers and owners. |
| Profile | `uniconnect.settings_profile` | `services/profile_service/Dockerfile` | Profile completion, editing, and "me" endpoint. |
| Dorms | `uniconnect.settings_dorm` | `services/dorm_service/Dockerfile` | Owner dorm CRUD and seeker dorm discovery. |
| Booking | `uniconnect.settings_booking` | `services/booking_service/Dockerfile` | Booking submission plus owner approval / rejection. |
| Notification | `uniconnect.settings_notification` | `services/notification_service/Dockerfile` | Derived booking notifications for seekers and owners. |

All services share the same `apps` code and database models. The media directory remains at `media/` so existing uploads work without relocation.

## Building Docker images

From the repository root you can build each image. Example commands:

### Windows PowerShell

PowerShell does not support the `VAR=value command` syntax that shells like Bash use. Set the
`DOCKER_BUILDKIT` environment variable with `$Env:` before running each build:

```powershell
# Authentication service
$Env:DOCKER_BUILDKIT = "1"
docker build -f services/auth_service/Dockerfile -t auth-service:v1 .

# Profile service
$Env:DOCKER_BUILDKIT = "1"
docker build -f services/profile_service/Dockerfile -t profile-service:v1 .

# Dorm management service
$Env:DOCKER_BUILDKIT = "1"
docker build -f services/dorm_service/Dockerfile -t dorm-service:v1 .

# Booking service
$Env:DOCKER_BUILDKIT = "1"
docker build -f services/booking_service/Dockerfile -t booking-service:v1 .

# Notification service
$Env:DOCKER_BUILDKIT = "1"
docker build -f services/notification_service/Dockerfile -t notification-service:v1 .
```

If you prefer to avoid persisting the variable for the entire session, remove it afterwards with
`Remove-Item Env:DOCKER_BUILDKIT`.

### macOS / Linux (Bash, Zsh, etc.)

On Unix-like shells you can continue using the inline assignment form:

```bash
# Authentication service
DOCKER_BUILDKIT=1 docker build -f services/auth_service/Dockerfile -t auth-service:v1 .

# Profile service
DOCKER_BUILDKIT=1 docker build -f services/profile_service/Dockerfile -t profile-service:v1 .

# Dorm management service
DOCKER_BUILDKIT=1 docker build -f services/dorm_service/Dockerfile -t dorm-service:v1 .

# Booking service
DOCKER_BUILDKIT=1 docker build -f services/booking_service/Dockerfile -t booking-service:v1 .

# Notification service
DOCKER_BUILDKIT=1 docker build -f services/notification_service/Dockerfile -t notification-service:v1 .
```

Each container starts with `gunicorn` and runs migrations automatically via the shared `docker/entrypoint.sh` script. You can override the command or additional environment variables as needed when deploying.

## Deploying to Minikube / Kubernetes

The `k8s/` directory provides manifests for each service. After building and loading the images into Minikube (for example with `minikube image load auth-service:v1`), apply the manifests:

```bash
kubectl apply -f k8s/auth-service.yaml
kubectl apply -f k8s/profile-service.yaml
kubectl apply -f k8s/dorm-service.yaml
kubectl apply -f k8s/booking-service.yaml
kubectl apply -f k8s/notification-service.yaml
```

Each manifest provisions a deployment and ClusterIP service listening on port 80 (proxying to container port 8000). Media storage is mounted at `/app/media` via an `emptyDir` volume by default; replace that section with a PersistentVolumeClaim for production.

When using Minikube you can expose any service with:

```bash
minikube service auth-service --url
```

Follow the same pattern for the other services (`profile-service`, `dorm-service`, `booking-service`, `notification-service`).

## Ingress routing with NGINX

To avoid reaching each microservice through a unique NodePort, enable the NGINX Ingress controller and apply the shared ingress
resource:

```bash
minikube addons enable ingress
kubectl apply -f k8s/ingress.yaml
```

Add `uniconnect.local` to your `/etc/hosts` so traffic resolves to Minikube (the IP from `minikube ip`). All requests from the
frontend can then target a single base URL (for example, `http://uniconnect.local`) and the ingress will forward paths to the
correct service:

- `/api/v1/auth/` → `auth-service`
- `/api/v1/carpooling/` → `carpooling-service`
- `/api/users/owner/booking-requests/` and `/api/users/seeker/booking-requests/` → `booking-service`
- `/api/users/owner/dorms/`, `/api/users/owner/dorm-rooms/`, `/api/users/owner/dorm-images/`, `/api/users/owner/dorm-room-images/`, `/api/users/seeker/dorms/` → `dorm-service`
- `/api/users/notifications/` → `notification-service`
- `/api/users/me/` and `/api/users/complete-profile/` → `profile-service`
- `/api/roommate/` → `roommate-service`
- `/api/v1/home/` (and other `/api/v1/` core endpoints) → `auth-service`

After the controller provisions a load balancer (or Minikube sets up the ingress tunnel), the frontend only needs to call these
paths without knowing the individual pod ports.

## Requirements

Dependencies for all services live in `requirements.txt`. Install them locally with:

```bash
pip install -r requirements.txt
```

`gunicorn` was added so that each microservice can run a production-ready WSGI server inside its container.
