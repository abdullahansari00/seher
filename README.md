<p align="center">
  <img src="static/images/seher-wordmark.svg" alt="Seher — tulip and sunflower logo. A little space to feel heard." width="640" />
</p>

<p align="center">
  <strong>Your AI companion for supportive conversations and reflection.</strong>
</p>

<p align="center">
  <a href="#why-seher">Why Seher</a> &nbsp;·&nbsp;
  <a href="#local-setup">Get started</a> &nbsp;·&nbsp;
  <a href="MESSAGE_FLOW.md">Message flow</a> &nbsp;·&nbsp;
  <a href="#deployment-data">Deployment</a> &nbsp;·&nbsp;
  <a href="#future-scope">What's next</a>
</p>

---

Seher is a Django application for supportive conversations, reflection, and access to
reference material. It uses Gemini, LangGraph, Pydantic, SQLite, and ChromaDB, with a
Django-template frontend.

## Why Seher

Seher is for someone who wants a focused place to talk through difficult feelings,
relationships, and everyday stress. Its intended advantage over a plain general-purpose
LLM chat is the complete support experience: the user does not have to assemble prompts,
reference material, and conversation history themselves.

| A space for… | What Seher brings |
| :--- | :--- |
| **Being heard** | A supportive conversational style that emphasizes listening and manageable replies. In our small manual comparison, responses were often shorter and closer to what the user actually said. |
| **Picking up the thread** | Recent messages and a rolling summary provide continuity for follow-ups, corrections, and preferences within a conversation. |
| **Understanding a little more** | A knowledge path draws on selected, indexed educational material when useful. Its value depends on the collection and retrieval quality. |
| **Finding support in difficult moments** | A dedicated crisis path receives configured support resources rather than being asked to invent contact details. |
| **A considered response** | An additional model review can allow, revise, or block a draft before delivery. |

For the team operating Seher, saved execution traces and evaluation tools make it possible
to inspect decisions and test improvements. This supports a more accountable development
process; it does not by itself establish better answers.

Seher still uses an underlying LLM. General-purpose assistants can offer overlapping
features, and we have not established that Seher is consistently more accurate or safer.
Our manual comparison showed strengths in brevity and listening, alongside weaknesses in
unsupported assumptions and how specifically crisis replies addressed the latest message.

> **A companion, with limits.** Seher is not a therapist, an emergency service, or an
> overnight monitoring system.

Choose Seher if this focused support experience fits your needs. Its development goal is
to make that experience consistently useful, grounded, and responsive to preferences;
that goal needs continued evaluation rather than a blanket claim of superiority.

For a step-by-step technical walkthrough, see [How a message moves through Seher](MESSAGE_FLOW.md).

## At a glance

| Application | Models & workflow | Knowledge & storage | Interface |
| :--- | :--- | :--- | :--- |
| Python · Django | Gemini · LangGraph · Pydantic | ChromaDB · SQLite | Django templates · JavaScript |

### The path to a reply

```mermaid
flowchart LR
    A[Your message] --> B[Safety gate]
    B --> C[Support, knowledge, or crisis path]
    C --> D[Output review]
    D --> E[Your reply]
```


Messages pass through a safety gate, then either a crisis agent or a supervisor that
chooses direct support or knowledge retrieval. Every generated response passes through
output safety review. Agents and model settings are configured in Django admin.
Conversation memory combines recent messages with a rolling summary.

Knowledge responses include conversation context once. Admin lists use descending IDs
(newest first), and all application models have explicit plural labels.

The application timezone is `Asia/Kolkata` (IST). Templates, chat timestamps, and
application logs use IST; logs include `+05:30`. With `USE_TZ=True`, database timestamps
remain UTC-aware, preserving existing records and unambiguous time comparisons.

## Local setup

### 1. Prepare your environment

Use Python 3.11 or newer and activate a virtual environment. The existing local
workspace uses `../venv`. `requirements.txt` pins the packages installed in that environment,
including development tools and transitive dependencies.

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure your model key

Edit `.env` to set `GEMINI_API_KEY` and a unique `DJANGO_SECRET_KEY`.
Generate the Django key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
 Existing environment variables take precedence over
`.env`. During `populate_db`, keys are copied into `AIModelConfig.api_key_plaintext`.
For separate keys, set `AI_MODEL_API_KEY_<id>`; this overrides the shared Gemini key for
that model ID. Chat, embedding, and evaluation clients read the database field at runtime.
Keys can also be edited in Django admin. `.env` is excluded from version control.
Retry mode (`--skip-load`) fills empty keys only, preserving existing database credentials.

### 3. Bring Seher to life

```bash
python manage.py migrate
python manage.py populate_db
python manage.py createsuperuser
python manage.py runserver
```

`populate_db` loads `fixtures/deployment.json`, then embeds its documents plus any other
pending/failed documents using the configured embedding model. Set a valid API key first.
Documents are marked ready only after successful indexing. Chroma data lives in `data/chroma`.
The command does not run migrations; run `migrate` first.

<details>
<summary><strong>Custom fixtures and retrying document indexing</strong></summary>

To load a different JSON dump:

```bash
python manage.py populate_db --fixture /path/to/deployment.json
```

If embedding fails, the loaded database records are retained. Retry without reloading
or overwriting configuration, and skip documents that already finished indexing:

```bash
python manage.py populate_db --skip-load
```

Running without `--skip-load` reloads the fixture and reindexes its documents.

</details>

## Deployment data

`fixtures/deployment.json` contains `SafetyPolicy`, `AgentConfig`, `AIModelConfig`, and
`Document` records, preserving their IDs and model relationships. It contains no API keys,
users, chat history, evaluation runs, document chunks, or vector data. Supply credentials
separately through `.env` or deployment environment variables.

Load the fixture into an empty migrated database. On an existing database, matching IDs
may be overwritten or unique names may conflict. Documents in the fixture are pending
because their embeddings must be built on the destination.

The fixture retains the existing documents and adds three short, attributed summaries:

- [WHO: Stress](https://www.who.int/news-room/questions-and-answers/item/stress)
- [NIMH: Caring for Your Mental Health](https://www.nimh.nih.gov/health/topics/caring-for-your-mental-health)
- [NHS: Grief after bereavement or loss](https://www.nhs.uk/mental-health/feelings-symptoms-behaviours/feelings-and-symptoms/grief-bereavement-loss/)

These are paraphrased educational summaries, not full reproductions or clinical protocols.
Source URLs, publishers, and access dates are stored with the documents. They were accessed
on 28 September 2026. Review source material periodically for updates.

To regenerate the fixture after editing configuration or documents:

```bash
python manage.py dump_deployment
```

The population command resets imported documents to `pending` before indexing because
chunks and vectors are not included. Before distributing a regenerated fixture, review
free-text prompts and metadata for accidentally entered secrets. `dump_deployment` excludes
`api_key_plaintext`; plain Django `dumpdata` includes it and should not be used to create
a shareable deployment fixture.

## Development checks

```bash
python manage.py check
python manage.py test
python -m black .
python -m black --check .
```

Black is configured in `pyproject.toml` with a target line length of 100. Black may leave
unbreakable strings longer than its target. The test suite mocks model calls; it does not
establish the quality of live model responses.

## Future scope

- [ ] Retry sending a message after a connection interruption, with request deduplication so a response lost in transit does not cause duplicate messages or model runs.
- [ ] Measure response latency using existing step timings; consider background processing and streaming if measurements justify them.
- [ ] Complete production configuration: external Django secret, debug disabled, allowed hosts, secure transport, and deployment-specific settings.
- [ ] In the next version, evaluate context-aware safety assessment and explicit crisis resolution against escalation and de-escalation cases, avoiding stale crisis decisions.
- [ ] Evaluate giving output safety review the user context and approved crisis resources.

These items are planned work. The current response path remains synchronous, and safety context behavior is unchanged.
