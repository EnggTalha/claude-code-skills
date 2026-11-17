---
name: fastapi-endpoint
description: Add a production-ready FastAPI endpoint with Pydantic v2 request and response models, dependency-injected services, proper status codes and error handling, auth hook, and pytest tests using TestClient. Use when the user asks to add, scaffold or fix an API route in a FastAPI project, or when an existing endpoint lacks validation, tests or consistent errors.
metadata:
  category: backend-devops
  added: "2026-11-18"
---

# FastAPI endpoint

The aim is to add an endpoint that matches the project's existing conventions and ships with tests. Avoid one-off code that bypasses the project's own patterns.

## When to use

- "Add an endpoint to create/list/update X", "my route returns 500 on bad input"
- Converting a Flask route or a script into a FastAPI API
- **Not for:** async background workers or WebSocket streaming (separate skills)

## Steps

1. **Learn the project's conventions first.** Find the app factory and routers (`grep -rn "APIRouter\|FastAPI(" --include=*.py`), check how the DB is accessed (Motor/PyMongo, SQLAlchemy), how auth works (`Depends(get_current_user)`), and where the tests live. Reuse all of these.

2. **Define the schemas** in the project's schemas module, keeping input and output separate:
   ```python
   from pydantic import BaseModel, Field, EmailStr, ConfigDict

   class LeadCreate(BaseModel):
       name: str = Field(min_length=1, max_length=120)
       email: EmailStr
       phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()-]{7,20}$")

   class LeadOut(BaseModel):
       model_config = ConfigDict(from_attributes=True)
       id: str
       name: str
       email: EmailStr
   ```

3. **Put the logic in a service**, not in the route function, so it can be tested and reused:
   ```python
   class LeadService:
       def __init__(self, db): self.col = db["leads"]
       async def create(self, data: LeadCreate) -> LeadOut:
           if await self.col.find_one({"email": data.email}):
               raise LeadExists(data.email)
           res = await self.col.insert_one(data.model_dump())
           return LeadOut(id=str(res.inserted_id), **data.model_dump())
   ```

4. **Write a thin route** with explicit status codes, `response_model` and auth:
   ```python
   router = APIRouter(prefix="/leads", tags=["leads"])

   def get_service(db=Depends(get_db)) -> LeadService:
       return LeadService(db)

   @router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
   async def create_lead(body: LeadCreate, svc: LeadService = Depends(get_service),
                         user=Depends(get_current_user)):
       try:
           return await svc.create(body)
       except LeadExists:
           raise HTTPException(status.HTTP_409_CONFLICT, "Lead with this email already exists")
   ```
   Register it with `app.include_router(router)` if the project doesn't auto-discover routers.

5. **Write tests** that override dependencies, so no real DB or auth is needed:
   ```python
   from fastapi.testclient import TestClient

   class FakeService:
       async def create(self, data):
           if data.email == "dup@x.com": raise LeadExists(data.email)
           return LeadOut(id="1", name=data.name, email=data.email)

   app.dependency_overrides[get_service] = lambda: FakeService()
   app.dependency_overrides[get_current_user] = lambda: {"id": "u1"}
   client = TestClient(app)

   def test_create_ok():
       r = client.post("/leads", json={"name": "A", "email": "a@x.com"})
       assert r.status_code == 201 and r.json()["email"] == "a@x.com"

   def test_validation_error():
       assert client.post("/leads", json={"name": "", "email": "bad"}).status_code == 422

   def test_conflict():
       assert client.post("/leads", json={"name": "A", "email": "dup@x.com"}).status_code == 409
   ```

6. **Run** `pytest -q` and start the app (`uvicorn app.main:app --reload`) to check `/docs` shows the new route with its schemas.

## Examples

### Example 1: CRM "create lead" for a voice-agent backend

Follow Steps 2–5 exactly: Mongo via Motor, JWT auth dependency, 201/409/422 covered by tests.

### Example 2: list endpoint with pagination

Add `limit: int = Query(20, ge=1, le=100)` and `cursor: str | None = None`, return `{"items": [...], "next_cursor": ...}`, and test the boundaries (`limit=0` → 422, `limit=101` → 422).

## Pitfalls

- Don't return raw Mongo documents. `_id` is an `ObjectId` and breaks JSON. Map it to `id: str`.
- Don't catch every `Exception` and return 500 with the error text, because that leaks internals. Map known errors to 4xx and let the global handler log the rest.
- Don't call blocking drivers (PyMongo, `requests`) inside `async def`. Use async drivers or a plain `def` route.
- Remember to clear `app.dependency_overrides` between test modules.
- Never hardcode secrets or DB URIs. Read them from settings (`pydantic-settings`) and `.env`, which stays git-ignored.

## Verification

- `pytest -q` passes, including the success, validation (422) and domain-error (409/404) cases.
- `/docs` shows the route with the request and response models.
- `curl -X POST localhost:8000/leads -H 'Content-Type: application/json' -d '{"name":"A","email":"a@x.com"}'` returns 201 with the expected body.
