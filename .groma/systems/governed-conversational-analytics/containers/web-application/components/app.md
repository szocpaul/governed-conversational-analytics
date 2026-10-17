---
type: C4 Component
title: Demo UI client
status: stable
groma:
  id: app
  parent: web-application
  code:
    - scanner: javascript
      file: app/web/app.js
  group: API & UI
description: Browser JavaScript that posts questions to the /query API and renders the answer, trace, and latency.
---

The demo UI client (app/web/app.js). Posts the question to /query and renders the answer or refusal, the sanitized trace, and the observational latency. The example gallery, placeholder rotation, and typing suggestions come from the curated static asset /static/examples.json; if that fetch fails, the page still accepts free-text questions (graceful degradation).

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [app/web/app.js](../../../../../../app/web/app.js) | [app/api/routes.py](../../../../../../app/api/routes.py) | Posts questions to /query | JavaScript (fetch) |

## Derived relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [app/web/app.js](../../../../../../app/web/app.js) | [app/api/routes.py](../../../../../../app/api/routes.py) | Calls HTTP endpoint: POST /query | javascript, python |
