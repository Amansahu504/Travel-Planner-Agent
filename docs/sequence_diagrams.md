# Sequence diagrams

End-to-end traces for the main request shapes. Every arrow is a real network call.

---

## 1. Full end-to-end: combined multi-agent request

The hardest path — a request that needs both specialists (spec scenario 10).

> *"Plan a 7-day trip to Japan, find suitable hotels, estimate the total cost, and
> explain the relevant cancellation policies."*

```mermaid
sequenceDiagram
    actor U as User
    participant UI as Gradio UI
    participant H as Host Router<br/>(ADK)
    participant A1 as Remote Agent 1<br/>(LangGraph)
    participant A2 as Remote Agent 2<br/>(Agno)
    participant M1 as MCP 1<br/>Knowledge
    participant M2 as MCP 2<br/>Operations
    participant M3 as MCP 3<br/>Policies
    participant W as Tavily

    U->>UI: submit request
    UI->>H: HostRunner.ask(query)
    H->>H: LlmAgent decides: BOTH agents needed

    par Travel intelligence
        H->>A1: A2A message/send
        A1->>A1: parse_query → TripSpec
        A1->>A1: decide_retrieval → retrieve
        A1->>M1: search_travel_knowledge ×7
        M1-->>A1: knowledge chunks
        A1->>A1: check_relevance
        alt context weak
            A1->>W: web search
            W-->>A1: web results
            A1->>A1: check_web_relevance
        end
        A1->>M3: find_policy → get_policy
        M3-->>A1: hotel-cancellation policy
        A1->>A1: generate_itinerary
        A1->>A1: validate_itinerary (Python arithmetic)
        A1->>A1: critic → CritiqueResult
        alt over budget or issues found
            A1->>A1: revise_itinerary (+ optimisation)
            A1->>A1: validate + critic again
        end
        A1->>A1: finalize_response
        A1-->>H: A2A artifact (itinerary + sources + trace)
    and Travel operations
        H->>A2: A2A message/send
        A2->>A2: classify → search
        A2->>M2: search_hotels / calculate_trip_budget
        M2-->>A2: rows + budget totals
        A2->>A2: compose with demo footer
        A2-->>H: A2A artifact (tables + estimates)
    end

    H->>H: merge into one consolidated answer
    H-->>UI: answer + execution trace
    UI-->>U: itinerary, budget, hotels, policies, trace
```

**Real observed trace:**

```text
Gradio UI received the request
Host Router (Google ADK) analysing the request
A2A call → Remote Agent 1 — Travel Intelligence (LangGraph)
A2A call → Remote Agent 2 — Travel Operations (Agno)
Response received from Remote Agent 1
    ↳ Parsed request → destination=Japan, 7 days, 1 traveller(s)
    ↳ Retrieval decision: retrieve knowledge (intent=planning)
    ↳ MCP Server 1 → retrieved 8 knowledge chunk(s)
    ↳ Relevance check: PASS (score=1.00)
    ↳ MCP Server 3 → fetched 1 policy document(s): hotel-cancellation
    ↳ Generated itinerary (7087 chars)
    ↳ Budget validation: total $3,150 (no budget given)
    ↳ Critic: PASS (preference match 100%, 0 issue(s))
    ↳ Finalised response
Response received from Remote Agent 2 — Travel Operations (Agno)
Host Router consolidated the final response
```

---

## 2. Single-agent: operational request

> *"Find a mid-range hotel in Tokyo under \$150 per night."*

```mermaid
sequenceDiagram
    actor U as User
    participant H as Host Router
    participant A2 as Remote Agent 2
    participant M2 as MCP 2

    U->>H: query
    H->>H: route → operations only
    H->>A2: A2A message/send
    A2->>A2: classify → "search"
    A2->>A2: Router → operations branch
    A2->>M2: search_hotels(destination=Tokyo,<br/>max_price_per_night=150, minimum_rating=4.0)
    M2->>M2: SQLite query
    M2-->>A2: 1 row (HT0004, $127.77, 4.4★)
    A2->>A2: broaden search (agent instruction)
    A2->>M2: search_hotels(destination=Tokyo,<br/>max_price_per_night=150)
    M2-->>A2: 4 rows
    A2->>A2: compose markdown table + demo footer
    A2-->>H: A2A artifact
    H-->>U: table with ids, prices, ratings
```

Note the agent's own retry-with-relaxed-filters behaviour — instructed in
`remote_agent_2/agents.py`, so a strict filter returning one row still yields a useful
answer, and the agent says it broadened the search.

---

## 3. Single-agent: policy question

> *"What is the hotel cancellation policy?"*

```mermaid
sequenceDiagram
    actor U as User
    participant H as Host Router
    participant A2 as Remote Agent 2
    participant M3 as MCP 3

    U->>H: query
    H->>A2: A2A message/send
    A2->>A2: classify → "policy"<br/>(not cancel_booking!)
    A2->>A2: Router → policy branch
    A2->>M3: find_policy("hotel cancellation policy")
    M3-->>A2: ranked: hotel-cancellation (score 4)
    A2->>M3: get_policy("hotel-cancellation")
    M3->>M3: read data/policies/hotel_cancellation_policy.md
    M3-->>A2: full text + metadata + disclaimer
    A2->>A2: answer with rate types, fee schedule,<br/>version, effective date
    A2-->>H: A2A artifact
    H-->>U: policy answer + fictional-policy disclaimer
```

The classifier distinguishing *asking about* cancellation from *performing* a
cancellation is the key routing subtlety — the same word routes to two different MCP
servers.

---

## 4. Corrective retrieval: web fallback with query rewrite

Triggered when the internal knowledge base cannot answer.

```mermaid
sequenceDiagram
    participant G as LangGraph
    participant M1 as MCP 1
    participant W as Tavily

    G->>M1: search_travel_knowledge(query)
    M1-->>G: 0 results (or low relevance)
    G->>G: check_relevance → score 0.0 → FAIL
    G->>W: web_search(query + destination)
    W-->>G: 4 results
    G->>G: check_web_relevance → score 0.85 → PASS
    G->>G: proceed to generation, results tagged "(web)"

    Note over G,W: If web results were also weak and<br/>retries < MAX_RETRIEVAL_RETRIES:<br/>rewrite_query → back to MCP 1
    Note over G: At the retry cap the graph proceeds<br/>with best effort — it never loops forever
```

Web-derived facts are labelled `(web)` in the itinerary and listed separately under
**Sources**, so the user can always tell retrieved knowledge from web content.

---

## 5. Booking lifecycle (all mock)

```mermaid
sequenceDiagram
    actor U as User
    participant A2 as Remote Agent 2
    participant M2 as MCP 2
    participant DB as SQLite

    U->>A2: "Book hotel HT0004 for Demo Traveler A at $890"
    A2->>A2: classify → "booking"
    A2->>M2: create_booking(hotel, HT0004,<br/>"Demo Traveler A", 890)
    M2->>M2: validate booking_type, item_id,<br/>traveler_name, total_cost
    M2->>DB: INSERT (file-locked)
    DB-->>M2: BK-414962B5
    M2-->>A2: booking + "MOCK BOOKING" note
    A2-->>U: confirmation, clearly labelled demo

    U->>A2: "Show me booking BK-414962B5"
    A2->>M2: retrieve_booking(booking_id)
    M2->>DB: SELECT
    M2-->>A2: row
    A2-->>U: table

    U->>A2: "Cancel it"
    A2->>M2: cancel_booking(BK-414962B5)
    M2->>DB: UPDATE status='cancelled'
    Note over M2,DB: Soft cancel — the record is retained<br/>for audit and never hard-deleted
    M2-->>A2: cancelled + no-refund-processed note
    A2-->>U: confirmation + cancellation policy pointer
```

---

## 6. Startup and dependency order

```mermaid
sequenceDiagram
    participant R as run_all.py
    participant D as data / vector DB
    participant M as MCP servers 1-3
    participant A as Remote agents 1-2
    participant U as Gradio UI

    R->>D: seed CSVs present?
    alt missing
        R->>D: scripts.generate_data
        R->>D: scripts.generate_policies
    end
    R->>D: Chroma populated?
    alt missing
        R->>D: ingest.build_vectordb (throttled)
    end
    R->>M: spawn 3 MCP servers
    R->>M: wait for :8001, :8002, :8003
    M-->>R: ports accepting
    R->>A: spawn 2 A2A agents
    R->>A: wait for :9001, :9002
    A-->>R: agent cards served
    R->>U: launch Gradio on :7860
```

Under Docker the same ordering is expressed with compose healthchecks: agents wait for
their MCP servers, and the host waits for both agents' AgentCard endpoints to answer.
