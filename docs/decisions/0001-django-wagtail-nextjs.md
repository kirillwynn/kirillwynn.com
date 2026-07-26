# ADR 0001: Django/Wagtail backend with a Next.js frontend

Status: accepted

Date: 2026-07-26

## Context

The legacy application uses Flask for public pages and APIs plus a separate React
editor. The intended product now requires:

- structured desktop authoring;
- drafts, previews, revisions, rollback, and scheduling;
- a searchable public feed;
- Google and GitHub login;
- comments, Slack-style threads, and emoji reactions;
- email subscriptions;
- a highly adaptable mobile and desktop public interface;
- self-hosting on the existing server.

Continuing with Flask would require building and maintaining substantial CMS
functionality. A fully server-rendered Wagtail site would be operationally
simpler, but would place the interactive public product UI and CMS presentation
in the same frontend boundary.

## Decision

Use:

- Django 5.2 LTS as the application framework;
- Wagtail 7.4 LTS as the content management system;
- Django REST Framework for public and interactive APIs;
- PostgreSQL as the primary database;
- Next.js App Router with React and TypeScript for the public frontend;
- Nginx to expose Next.js and Django under one origin;
- Docker Compose on the existing server.

Wagtail owns authored content and editorial lifecycle. Django owns users,
sessions, discussions, reactions, subscriptions, and authorization. Next.js owns
public presentation and browser interaction.

The application uses REST, not GraphQL.

## Rationale

Wagtail provides mature editorial capabilities that would otherwise be custom
work:

- StreamField content;
- media management;
- revisions;
- preview;
- scheduling;
- permissions.

Next.js provides:

- server-rendered public content;
- a component model suitable for responsive UI;
- isolated client-side interaction for comments and reactions;
- metadata and caching controls;
- a clear boundary from the CMS administration interface.

The same-origin Nginx topology avoids unnecessary CORS complexity and supports
standard Django sessions, OAuth callbacks, and CSRF protection.

## Consequences

Positive:

- less custom CMS code;
- flexible mobile and desktop presentation;
- clear data ownership;
- future support for additional authors;
- testable REST contracts;
- independent frontend and backend evolution.

Negative:

- two application runtimes must be built and operated;
- headless preview requires explicit integration;
- cache invalidation must follow Wagtail publication events;
- StreamField blocks need stable API serializers and matching React renderers;
- deployment is more complex than a Django-template monolith.

## Alternatives considered

### Continue with Flask and React

Rejected because revisions, scheduling, preview, media workflows, and editorial
permissions would remain custom application code.

### Django/Wagtail with Django templates

Viable and simpler operationally. Not selected because the public product
requires a highly interactive, independently adaptable mobile/desktop UI and the
owner prefers Next.js.

### Next.js with a JavaScript-native CMS

Rejected because Django/Wagtail provides the preferred Python backend,
editorial model, permissions, and self-hosted ownership.

### Hosted CMS

Rejected because the project should remain self-hosted and under the owner's
control.

## Revisit conditions

Reconsider this decision only if:

- headless preview proves unreliable after a bounded prototype;
- the server cannot operate the additional Next.js runtime;
- Wagtail StreamField cannot support the required authoring experience;
- operational complexity materially exceeds the value of the separate frontend.

Any change requires a superseding ADR.
