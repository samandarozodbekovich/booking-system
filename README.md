# Booking System API

A backend for appointment-based businesses (barbershops, clinics, consultations): customers pick a service and a provider, see free time slots, and book one. The business manages services, providers, working hours and time off.

The main focus is **correctness under concurrency**: two customers can never book the same slot, even when their requests arrive at the same millisecond.

## Features

- JWT authentication with roles: `customer`, `provider`, `admin`
- Services, providers, weekly working hours and time off
- Availability calculation (working hours − time off − active bookings)
- Booking with double-booking protection enforced by PostgreSQL
- Status flow: `pending → confirmed → completed`, or `cancelled`
- Pending bookings expire after 15 minutes (Celery periodic task)
- Cancellation policy: customers can't cancel less than 2 hours before start
- Full status history for every booking
- Filtering, search, ordering and pagination
- Swagger / ReDoc documentation
- 63 automated tests, including real concurrency tests

## Tech stack

Python 3.12 · Django 5.2 · Django REST Framework · PostgreSQL · SimpleJWT · drf-spectacular · Celery + Redis · pytest

PostgreSQL is required: the double-booking protection uses range types and exclusion constraints that SQLite doesn't have.

## Getting started

### Prerequisites

- Python 3.12+
- PostgreSQL 13+
- Redis (optional, only for the background expiry task)

### Setup

```bash
git clone <repository-url>
cd booking-system

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a database and a user (in `psql` or pgAdmin, as the `postgres` superuser):

```sql
CREATE USER booking_user WITH PASSWORD 'booking_pass';
CREATE DATABASE booking_db OWNER booking_user;
ALTER USER booking_user CREATEDB;  -- needed to create the test database
```

Copy `.env.example` to `.env` and adjust the values:

```
DEBUG=True
SECRET_KEY=change-me
DB_NAME=booking_db
DB_USER=booking_user
DB_PASSWORD=booking_pass
DB_HOST=localhost
DB_PORT=5432
CELERY_BROKER_URL=redis://localhost:6379/0
```

Run migrations and start the server:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Swagger UI: http://127.0.0.1:8000/api/swagger/
- ReDoc: http://127.0.0.1:8000/api/redoc/
- Django admin: http://127.0.0.1:8000/api/admin/

### Background tasks (optional)

With Redis running, start a worker and the scheduler in two terminals:

```bash
celery -A config worker -l info --pool=solo   # --pool=solo is required on Windows
celery -A config beat -l info
```

The system works correctly without Celery (see [Pending bookings](#pending-bookings)); Celery only keeps stored statuses up to date.

### Tests

```bash
pytest
```

The race-condition tests use real threads and real transactions. Redis is not needed for tests.

## Architecture

The project is split into four Django apps, each answering one question:

| App | Question | Contents |
|---|---|---|
| `accounts` | Who? | Custom `User` with roles, JWT auth, permissions |
| `catalog` | What? | `Service`: name, duration, price |
| `scheduling` | When free? | `Provider`, `WorkingHours`, `TimeOff`, availability algorithm |
| `bookings` | When taken? | `Booking`, `BookingStatusLog`, booking business logic |

Views are thin. Business logic lives in plain modules (`scheduling/availability.py`, `bookings/services.py`), so it can be tested without HTTP and reused: the same availability function feeds the API and validates new bookings, and the same expiry function runs inside requests and in the Celery task.

### Data model

```
User ──1:1── Provider ──M:N── Service
  │             ├──1:N── WorkingHours   (weekly, provider's local time)
  │             ├──1:N── TimeOff        (absolute period, UTC)
  │             └──1:N── Booking
  └──1:N── Booking (as customer)
                 └──1:N── BookingStatusLog
```

Key decisions:

- **`Booking.period` is a `tstzrange` `[start, end)`.** Back-to-back bookings (10:00–11:00, 11:00–12:00) don't overlap.
- **End time and price are snapshots.** They are computed on the server when the booking is created, so later changes to the service don't affect existing bookings. The client never sends `end`, `price` or `status`.
- **Free slots are not stored.** They are computed on each request (3 SQL queries per day), so they can never go out of sync with working hours or bookings.
- **Time zones.** Everything is stored in UTC. Working hours are stored in the provider's local time (so "09:00" stays 09:00 across DST changes) and converted to UTC for a specific date. Slot arithmetic is done in UTC.
- **Soft delete** for services and providers: existing bookings keep their references.
- **Self-registration always creates a customer.** Providers are created by an admin.

## Booking flow

```
GET  /api/services/                                          choose a service
GET  /api/providers/?services={id}                           choose a provider
GET  /api/providers/{id}/availability/?service={id}&date=... see free slots
POST /api/bookings/                                          book a slot
     → 201 Created (pending) | 400 invalid input | 409 slot not available
```

Main endpoints:

| Endpoint | Who |
|---|---|
| `POST /api/auth/register/`, `login/`, `refresh/`, `logout/` | anyone / authenticated |
| `GET/PATCH /api/auth/profile/` | authenticated |
| `/api/services/` | read: authenticated, write: admin |
| `/api/providers/` | read: authenticated, write: admin |
| `/api/providers/{id}/working-hours/`, `/time-offs/` | admin or the provider |
| `GET /api/providers/{id}/availability/` | authenticated |
| `POST /api/bookings/` | customer |
| `GET /api/bookings/`, `/api/bookings/{id}/` | own bookings (admin: all) |
| `POST /api/bookings/{id}/confirm/`, `complete/` | the provider or admin |
| `POST /api/bookings/{id}/cancel/` | the customer, the provider or admin |
| `GET /api/bookings/{id}/history/` | anyone who can see the booking |

## Double booking and race conditions

**The problem.** Checking "is the slot free?" in Python and then inserting is not safe. Two requests can both check, both see a free slot, and both insert.

**The solution: the database is the final authority.** `Booking` has an exclusion constraint:

```sql
EXCLUDE USING gist (provider_id WITH =, period WITH &&)
WHERE (status IN ('pending', 'confirmed'))
```

PostgreSQL rejects any second active booking for the same provider whose period overlaps. When two inserts race, the second one waits for the first transaction and then fails. The service layer catches the `IntegrityError` and the API returns `409 Conflict`. A second constraint does the same for customers, so one person can't be booked in two places at once. Cancelled and completed bookings don't hold slots.

The Python check (`is_slot_available`) still runs first. It gives clear errors in the common case (outside working hours, off the 15-minute grid, in the past), but it is not what prevents double booking.

**Proof.** `tests/test_race_condition.py` fires 10 parallel requests at one slot:

- with the constraint: exactly 1 booking is created, 9 requests get a conflict;
- with the constraint removed: all 10 bookings are created.

Status changes use `select_for_update()`, so parallel actions on one booking (e.g. two "confirm" clicks, or "confirm" and "cancel") are serialized and history stays consistent.

## Pending bookings

A new booking is `pending` and holds its slot for 15 minutes until the provider confirms it. Expiry is handled in three layers:

1. Availability treats expired pending bookings as free (on every request).
2. Creating a booking or changing a status first cancels expired pending bookings in the same transaction, so the exclusion constraint never blocks on a stale booking.
3. A Celery task runs every minute to keep stored statuses accurate.

If Redis or the worker is down, customers still see and book the right slots.

## Edge cases handled

- Two customers book the same or an overlapping slot at the same time → one wins, the rest get `409`
- A customer books two providers at the same time → `409`
- Booking outside working hours, in a lunch break, during time off, in the past, or off the slot grid → `409`
- A service that doesn't fit before the end of a working interval → no slot offered
- A provider who doesn't offer the chosen service → `400`
- Inactive services or providers → not bookable
- Service price or duration changes after booking → booking keeps its snapshot
- Invalid status changes (e.g. `cancelled → confirmed`, `completed → cancelled`) → `409`
- Completing a booking before it starts → `409`
- Customer cancels less than 2 hours before start → `409` (providers and admins can still cancel)
- Time off that overlaps active bookings → rejected with the number of conflicts
- Overlapping or reversed working hours → `400`
- Registering with `"role": "admin"` → ignored, user is a customer
- Same email in different letter case → rejected
- A user accessing someone else's booking → `404`

## Known limitations

- Editing working hours doesn't check existing bookings; a booking can end up outside the new hours.
- Working hours can't cross midnight (e.g. 22:00–02:00).
- An access token stays valid until it expires (30 min) after logout; the refresh token is blacklisted.
- Capacity-based booking (restaurant tables, group classes) is out of scope: one provider serves one customer at a time.

## AI usage

An AI assistant (Claude) was used as a pair-programming partner:

- discussing the architecture and data model, and comparing alternatives;
- brainstorming edge cases;
- generating initial code for models, serializers, views and tests;
- explaining errors during development.

Every piece of code was typed into the project manually, read and understood, and tested against a real PostgreSQL database. Many integration bugs were found and fixed during this process (field name mismatches, missing imports, wrong URL paths, context and transaction issues). The test suite also caught two real bugs that manual testing missed: business admins couldn't see all bookings, and the availability function ignored its `now` parameter.

Key decisions — the exclusion constraint, the UTC strategy, computing slots instead of storing them, pending expiry — were discussed and chosen deliberately, and are explained above.
