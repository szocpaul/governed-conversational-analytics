---
type: C4 Container
title: Reset database
status: stable
groma:
  id: script-reset-database
  parent: governed-conversational-analytics
description: Clean local reset of the database to a known state.
---

Drops and recreates the itsm database, schema, tables, indexes, and roles from the SQL files in database/. Provides a clean local reset path for development and testing. Does not touch the immutable raw source files.
