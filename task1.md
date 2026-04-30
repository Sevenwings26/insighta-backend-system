Deadline
4/17/2026
11:59pm
Task Name
Stage 1 (BACKEND) TASK: Data Persistence & API Design Assessment
Requirements / Task Brief
Overview

At this stage, you are expected to:
- Work with multiple external APIs
- Process and structure data
- Persist data in a database
- Design clean and usable APIs

<!-- This stage is partially automated and partially reviewed. Only candidates who meet the required quality threshold will move to Stage 2. -->



Objective

By completing this stage, you must demonstrate that you can:

 Integrate multiple third-party APIs
 Design and implement a database schema
 Store and retrieve structured data
 Build multiple RESTful endpoints
 Handle duplicate data intelligently (idempotency)
 Return clean, consistent JSON responses


Core Concept

You are building a Profile Intelligence Service.

Your system will:

 Accept a name
 Enrich it using external APIs
 Store the result
 Allow retrieval and management of stored data


External APIs

You must integrate with (free, no key required):

Genderize: https://api.genderize.io?name={name}
Agify: https://api.agify.io?name={name}
Nationalize: https://api.nationalize.io?name={name}


Functional Requirements



Processing rules:
Call all three APIs using the provided name and aggregate the responses
Extract gender, gender_probability, and count from Genderize. Rename count to sample_size
Extract age from Agify. Classify age_group: 0–12 → child, 13–19 → teenager, 20–59 → adult, 60+ → senior
Extract country list from Nationalize. Pick the country with the highest probability as country_id
Store the processed result with a UUID v7 id and UTC created_at timestamp


1. POST /api/profiles

Request body: { "name": "ella" }



Success response (201):



{

  "status": "success",

  "data": {

    "id": "b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12",

    "name": "ella",

    "gender": "female",

    "gender_probability": 0.99,

    "sample_size": 1234,

    "age": 46,

    "age_group": "adult",

    "country_id": "DRC",

    "country_probability": 0.85,

    "created_at": "2026-04-01T12:00:00Z"

  }

}



Idempotency: If the same name is submitted again, do not create a new record. Return the existing one:



{

  "status": "success",

  "message": "Profile already exists",

  "data": { "...existing profile..." }

}



2. GET /api/profiles/{id}

Success response (200):



{

  "status": "success",

  "data": {

    "id": "b3f9c1e2-7d4a-4c91-9c2a-1f0a8e5b6d12",

    "name": "emmanuel",

    "gender": "male",

    "gender_probability": 0.99,

    "sample_size": 1234,

    "age": 25,

    "age_group": "adult",

    "country_id": "NG",

    "country_probability": 0.85,

    "created_at": "2026-04-01T12:00:00Z"

  }

}



3. GET /api/profiles

Optional case-insensitive query params: gender, country_id, age_group

Example: /api/profiles?gender=male&country_id=NG

Success response (200):



{

  "status": "success",

  "count": 2,

  "data": [

    {

      "id": "id-1",

      "name": "emmanuel",

      "gender": "male",

      "age": 25,

      "age_group": "adult",

      "country_id": "NG"

    },

    {

      "id": "id-2",

      "name": "sarah",

      "gender": "female",

      "age": 28,

      "age_group": "adult",

      "country_id": "US"

    }

  ]

}



4. DELETE /api/profiles/{id}

Returns 204 No Content on success.



Edge Case Handling

Genderize returns gender: null or count: 0 → return 502, do not store
Agify returns age: null → return 502, do not store
Nationalize returns no country data → return 502, do not store


Error Handling (External APIs)

{ "status": "502", "message": "${externalApi} returned an invalid response" }

externalApi = Genderize | Agify | Nationalize



All errors follow this structure:

{ "status": "error", "message": "<error message>" }



400 Bad Request: Missing or empty name
422 Unprocessable Entity: Invalid type
404 Not Found: Profile not found
500/502: Upstream or server failure


Additional Requirements

CORS header: Access-Control-Allow-Origin: *. Without this, the grading script cannot reach your server
All timestamps in UTC ISO 8601
All IDs in UUID v7
Response structure must match exactly. Grading is partially automated
Evaluation Criteria / Acceptance Criteria
API Design (Endpoints):  ======  15 points
Multi-API Integration:   ======  15 points
Data Persistence:    ======      20 points
Idempotency Handling:   ======   15 points
Filtering Logic:     ======      10 points
Data Modeling:      ======       10 points
Error Handling:      ======      10 points
Response Structure:   ======      5 points
Submission Format
Three things:



1. GitHub repository link with a clear README (repo must be public)

2. Public API base URL (https://yourapp.domain.app)

3. All endpoints must be live when testing runs



Note: Render is not accepted. Vercel, Railway, Heroku, AWS, PXXL App, and similar platforms are fine.

Submission Link
Run /submit in #track-backend.
Points
100
Format: Integer
Pass Mark
75