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
description: Browser client of the demo UI that posts a question and renders the answer.
---

The demo UI client (app/web/app.js) posts the question to /query and renders the answer or refusal, the sanitized trace, and the observational latency. It ships with the static UI assets served by the web application: app/web/index.html and app/web/styles.css are the page and its styling, and app/web/examples.json is the curated example gallery served from /static. The gallery, the rotating placeholder, and the typing suggestions come from that static asset; if the fetch fails, the page still accepts free-text questions.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [app/web/app.js](../../../../../../app/web/app.js) | [app/api/routes.py](../../../../../../app/api/routes.py) | Posts questions to /query | JavaScript (fetch) |

## Derived relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [app/web/app.js](../../../../../../app/web/app.js) | [app/api/routes.py](../../../../../../app/api/routes.py) | Calls HTTP endpoint: POST /query | javascript, python |
