# Semantic Data Pipeline

This is a small system that takes messy, raw telemetry (metrics, logs, alerts) from several
different sources, cleans it up, figures out which real-world thing each event is actually
about, adds useful context to it, and then lets a simple decision-making agent act on the
result. The point of this project is the middle part: turning raw noise into something an
automated system can actually trust and query.

## Why this is harder than it sounds

If you've worked with telemetry from more than one system, you already know the problem:
every source names things a little differently. Your metrics agent might call a server
`use1-web-01`. Your log shipper might call the exact same server `USE1-WEB-01`. Your alerting
tool might call it `web01.use1.internal`. Three strings, one real machine.

If you build anything on top of that raw data without fixing this first - a dashboard, an
alert, or worse, an automated agent that decides to restart something - you end up with three
different "entities" that are actually one, and nothing lines up. You can't answer a simple
question like "is this host currently healthy?" because the answer is scattered across three
different names.

A **semantic layer** is the fix: one place that holds a single, current, trustworthy answer
for "what do we know about this entity right now", built by constantly reconciling whatever
comes in from all your raw sources. That's what this project builds, end to end, including an
example of something actually using it to make a decision.

## How it works, step by step

```
 ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
 │ metrics feed│   │  log feed   │   │ alert feed  │   <- 3 simulated raw sources,
 └──────┬──────┘   └──────┬──────┘   └──────┬──────┘      each naming entities differently
        └─────────────────┼─────────────────┘
                           v
                     [ normalize ]   <- same field names/units regardless of source
                           v
                    [ entity_link ]  <- resolves the raw name to one canonical entity id
                           v
                      [ enrich ]     <- attaches dependency info + recent deploys
                           v
                      [ publish ]    <- updates the semantic layer + pushes to the dashboard
                           v
                  ┌─────────────────┐
                  │  semantic layer │   <- "what do we know about entity X right now"
                  └────────┬────────┘
                           v
                   [ decision engine ] <- polls the semantic layer, decides what to do
                           v
                    rollback / investigate / restart, with a reasoning trace
```

Each arrow above is an `asyncio.Queue` in this project (see `backend/app/pipeline/event_bus.py`).
That's a deliberate, documented simplification: the four stages only know about a small
`EventBus` interface, not about queues specifically, so a real deployment could swap the
in-process queue for Kafka or Kinesis without touching any of the stage logic.

### The stages

1. **Ingest** (`backend/app/pipeline/ingest.py`) - three fake-but-realistic source feeds
   running at the same time: a metrics agent, a log shipper, and an alerting system. They
   describe the same small fleet of hosts and services, but under different aliases, on
   purpose.
2. **Normalize** (`normalize.py`) - puts every event into one consistent shape per event
   type, so nothing downstream has to know which source it came from.
3. **Entity link** (`entity_link.py`) - looks up the raw, messy name in a small registry
   (`backend/app/registry.py`) that knows every alias for every real entity, and resolves it
   to one canonical id. If nothing matches, the event is marked "unresolved" instead of being
   silently thrown away - you can see this happen live in the Event Stream view.
4. **Enrich** (`enrich.py`) - attaches what this entity depends on, what depends on it, and
   whether it was deployed recently. A single event in isolation ("latency is high") doesn't
   tell you much. The same event with context ("latency is high, and this was deployed 90
   seconds ago") tells you what to do about it.
5. **Publish** (`publish.py`) - writes the result into the semantic layer
   (`backend/app/semantic_layer/store.py`) and pushes it to any connected dashboard over a
   WebSocket.

### The semantic layer

`SemanticLayerStore` (in `backend/app/semantic_layer/store.py`) keeps one record per entity:
its current health, its last metric reading, who it depends on, who depends on it, its recent
deploys, and a short rolling history of recent events. "Health" isn't a flag someone has to
remember to clear - it's computed from "how long ago was the last bad signal", so an entity
automatically goes back to healthy a short while after things stop looking wrong.

### The agent

`backend/app/agent/decision_engine.py` polls the semantic layer every few seconds and checks
each unhealthy entity against three plain rules, in this order:

1. **Was it deployed recently?** If yes, recommend a rollback - a brand-new deploy is the most
   likely and most directly fixable cause.
2. **Does it depend on something that's also unhealthy?** If yes, recommend investigating that
   dependency first instead of touching the entity itself.
3. **Otherwise**, recommend a restart - this looks like an isolated problem.

To be upfront: this is a rule-based engine, not a machine-learning model or an LLM. That's on
purpose. The point of this project is proving the data underneath an agent is reliable and
explainable - and a rule-based engine makes every single decision traceable back to the exact
facts it read and the exact rule that fired. You'd want that same traceability even if you
swapped the rules for a model later (see "What a real production version would add" below).

Every decision records which facts it used and which rule fired, and the dashboard's **Agent
Decisions** tab shows that reasoning trace for every decision, not just the final action.

## Running it yourself

You'll need Python 3.11+ and Node 18+.

**Backend:**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

This starts the API on `http://127.0.0.1:8000` and immediately starts generating simulated
traffic - you don't need to load any data yourself.

**Frontend** (in a second terminal):

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). The dev server proxies `/api` and
`/ws` to the backend automatically.

**Tests:**

```bash
cd backend
pytest
```

## A concrete walkthrough

Shortly after you start the backend, watch the **Agent Decisions** tab. Within about a minute
you should see something like this:

> **Rollback** · `service:checkout`
> service:checkout is unhealthy and version v2.14.0 was deployed 93s ago, inside the 600s
> rollback window. The most likely cause is the new code, so rolling back is safer than
> restarting into the same build.

Behind that one line, here's what actually happened:

1. The metrics feed emitted a high-latency reading for `use1-web-01`.
2. The alert feed, at nearly the same time, raised a critical alert tagged `USE1-WEB-01` - a
   different spelling of the same host.
3. `entity_link` resolved both to the same canonical id, `host:use1-web-01`, using the alias
   table in `registry.py`.
4. The semantic layer marked that host unhealthy, which also marked `service:checkout`
   unhealthy (it runs on that host).
5. `enrich` had already attached `service:checkout`'s most recent deploy (seeded 90 seconds
   before the app started, specifically so you can watch this happen quickly).
6. The agent's next poll saw "unhealthy + recent deploy" and applied rule #1.

You can see the raw -> normalized -> linked -> enriched version of any individual event by
clicking it in the **Event Stream** tab.

## What's simplified here, and what a real production version would add

This project is built to actually run end to end, not to be a toy - but a few things are
intentionally kept simple so the whole system stays easy to read and run on one machine:

- **In-process queues instead of Kafka/Kinesis.** The `EventBus` interface
  (`pipeline/event_bus.py`) is designed so a real message broker could be dropped in behind
  the same interface without changing any stage's logic.
- **In-memory state instead of a real database.** `SemanticLayerStore` and the deploy/registry
  data live in process memory. A production version would back the semantic layer with
  something like Redis or Postgres so multiple pipeline workers could share state and survive
  a restart.
- **A static entity registry instead of a live one.** Real alias tables drift as infrastructure
  changes; a production version would sync this from a CMDB or service catalog instead of a
  hard-coded Python dict.
- **A rule-based agent instead of a trained or LLM-based one.** The rules here are simple and
  fully explainable on purpose. A production agent might use a model instead, but it would
  still need exactly this kind of traceable, reconciled data underneath it to be trustworthy -
  that's the actual point this project is making.
- **No authentication and wide-open CORS.** Fine for running locally, not fine for a real
  deployment.
- **Single process, no horizontal scaling.** A production pipeline would run multiple workers
  per stage behind the message broker mentioned above.
