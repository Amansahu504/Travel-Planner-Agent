# Architecture

Detailed diagrams and design rationale. See the [README](../README.md) for setup and the
high-level overview.

---

## 1. System architecture

```mermaid
flowchart TD
    subgraph Client
        U([User])
    end

    subgraph "Host tier — :7860"
        UI["Gradio UI<br/>chat + structured form + trace"]
        HOST["Host / Router Agent<br/>Google ADK LlmAgent"]
        AT1["AgentTool<br/>RemoteA2aAgent"]
        AT2["AgentTool<br/>RemoteA2aAgent"]
    end

    subgraph "Agent tier — A2A servers"
        RA1["Remote Agent 1 :9001<br/>LangGraph<br/>Travel Intelligence"]
        RA2["Remote Agent 2 :9002<br/>Agno Workflow<br/>Travel Operations"]
    end

    subgraph "Tool tier — MCP streamable HTTP"
        M1["MCP Server 1 :8001<br/>Travel Knowledge"]
        M2["MCP Server 2 :8002<br/>Travel Operations"]
        M3["MCP Server 3 :8003<br/>Travel Policies"]
    end

    subgraph "Data tier"
        VDB[("Chroma<br/>253 chunks")]
        DB[("SQLite<br/>658 rows")]
        POL[("10 policy<br/>documents")]
        WEB{{"Tavily<br/>web search"}}
    end

    U --> UI --> HOST
    HOST --> AT1 --> RA1
    HOST --> AT2 --> RA2

    RA1 -->|MCP client| M1
    RA1 -->|MCP client| M3
    RA1 -.->|fallback| WEB
    RA2 -->|MCP client| M2
    RA2 -->|MCP client| M3

    M1 --> VDB
    M2 --> DB
    M3 --> POL

    classDef host fill:#4c6ef5,stroke:#364fc7,color:#fff
    classDef agent fill:#12b886,stroke:#0ca678,color:#fff
    classDef mcp fill:#fd7e14,stroke:#e8590c,color:#fff
    classDef data fill:#868e96,stroke:#495057,color:#fff
    class UI,HOST,AT1,AT2 host
    class RA1,RA2 agent
    class M1,M2,M3 mcp
    class VDB,DB,POL,WEB data
```

### Tier boundaries (enforced, not just documented)

| Boundary | Rule | Where enforced |
| --- | --- | --- |
| Host → MCP | The host has **no** MCP client and never calls a tool directly | `host_agent/router.py` only holds two `AgentTool`s; asserted by `test_host_has_no_direct_mcp_access` |
| Agent → Agent | Remote agents never call each other; they are peers behind the host | Neither agent imports the other, nor holds the other's URL |
| Agent → MCP | Each agent connects only to the servers it owns | Agent 1 → MCP 1 + 3; Agent 2 → MCP 2 + 3 |

Agent 1 and Agent 2 both reach MCP Server 3, deliberately: Agent 1 needs cancellation
terms to attach to an itinerary, while Agent 2 answers direct policy questions. MCP
Server 3 is read-only, so shared access carries no consistency risk.

---

## 2. A2A communication

```mermaid
flowchart LR
    subgraph "Host (A2A client)"
        H[ADK LlmAgent]
        RC["RemoteA2aAgent<br/>resolves AgentCard"]
    end

    subgraph "Remote agent (A2A server)"
        SA["A2AStarletteApplication"]
        RH["DefaultRequestHandler"]
        FE["FunctionExecutor<br/>(common/a2a_server.py)"]
        TS[("InMemoryTaskStore")]
        WF["framework workflow<br/>LangGraph / Agno"]
    end

    H --> RC
    RC -->|"GET /.well-known/agent-card.json"| SA
    RC -->|"POST / JSON-RPC message/send"| SA
    SA --> RH --> FE --> WF
    RH --> TS
    WF -->|"artifact: response"| FE
    FE -->|"Task completed"| RC --> H
```

`common/a2a_server.py` is framework-agnostic: it adapts any
`async handler(query: str) -> str` into an A2A `AgentExecutor`. That is why the LangGraph
agent and the Agno agent are served by identical scaffolding despite having nothing else
in common — and why adding a third agent would take only a new handler plus an AgentCard.

### Task lifecycle

```mermaid
stateDiagram-v2
    [*] --> submitted: new_task()
    submitted --> working: start_work()
    working --> completed: add_artifact() + complete()
    working --> failed: exception → update_status(failed)
    completed --> [*]
    failed --> [*]
```

Handler exceptions become a `failed` task carrying a readable message — never a stack
trace leaking to the user.

---

## 3. MCP communication

```mermaid
flowchart TD
    subgraph "Remote Agent 1"
        LG[LangGraph node]
        MC1["MultiServerMCPClient<br/>langchain-mcp-adapters"]
    end
    subgraph "Remote Agent 2"
        AG[Agno agent]
        MC2["MCPTools<br/>agno.tools.mcp"]
    end

    LG --> MC1
    AG --> MC2

    MC1 -->|"streamable_http"| S1["FastMCP :8001/mcp"]
    MC1 -->|"streamable_http"| S3["FastMCP :8003/mcp"]
    MC2 -->|"streamable-http"| S2["FastMCP :8002/mcp"]
    MC2 -->|"streamable-http"| S3

    S1 --> T1["tools:<br/>search_travel_knowledge<br/>list_destinations<br/>list_categories"]
    S2 --> T2["tools:<br/>search_flights / hotels / activities<br/>calculate_trip_budget<br/>create / retrieve / update / cancel booking"]
    S3 --> T3["resources: travel://policies/*<br/>tools: list_policies<br/>get_policy / find_policy"]
```

Two different MCP client libraries are in play because each framework brings its own —
`langchain-mcp-adapters` exposes MCP tools as LangChain tools, while Agno's `MCPTools` is
an async context manager that binds tools to an agent for the duration of a call. Both
speak the same streamable-HTTP protocol to the same servers.

Agent 1 caches its tool handles after first load (`remote_agent_1/mcp_client.py`); Agent 2
opens a session per request, which is why its MCP branches are wrapped in `async with`.

---

## 4. Corrective RAG in detail

```mermaid
flowchart TD
    Q[User query] --> P["parse_query<br/>→ TripSpec structured output"]
    P --> D{"decide_retrieval<br/>→ RetrievalDecision"}

    D -->|direct| POL
    D -->|retrieve| R1

    R1["retrieve_travel_context"] --> R2{"planning intent<br/>+ destination?"}
    R2 -->|yes| R3["one search per category:<br/>attractions, food, culture,<br/>transportation, accommodation,<br/>activities + free-text pass"]
    R2 -->|no| R4["single broad search"]
    R3 --> DEDUP["de-duplicate,<br/>rank by score"]
    R4 --> DEDUP

    DEDUP --> G{"check_relevance<br/>→ RelevanceGrade"}
    G -->|"≥ 0.55"| POL
    G -->|"< 0.55"| W["web_search"]

    W --> GW{"check_web_relevance"}
    GW -->|relevant| POL
    GW -->|"weak, retries < 2"| RW["rewrite_query"] --> R1
    GW -->|"retries = 2"| POL

    POL["retrieve_policies<br/>MCP Server 3"] --> GEN["generate_itinerary"]

    classDef mcp fill:#fd7e14,stroke:#e8590c,color:#fff
    class R1,R3,R4,POL mcp
```

**Why one search per category for itineraries:** a single semantic search over a
7-day-trip query returns whichever chunks are closest overall — often five variations of
"attractions" and nothing about transport. Fanning out per category guarantees the
generator sees the full spread it needs, and de-duplication keeps the context tight.

---

## 5. Self-reflection and budget optimisation

```mermaid
flowchart TD
    GEN["generate_itinerary<br/>markdown with cost table"] --> V1["validate_itinerary"]

    V1 --> V2["extract cost lines<br/>→ CostLines structured output"]
    V2 --> V3{"extraction ok?"}
    V3 -->|no| V4["regex-scrape the Total row"]
    V3 -->|yes| V5["sum components in Python"]
    V4 --> V6
    V5 --> V6{"budget stated?"}
    V6 -->|yes| V7["compare → within_budget / over_budget"]
    V6 -->|no| V8["status = unknown"]

    V7 --> C["critic → CritiqueResult"]
    V8 --> C

    C --> C2["arithmetic verdict OVERRIDES<br/>the model's budget opinion"]
    C2 --> C3{"relevant AND budget_valid<br/>AND feasible?"}

    C3 -->|yes| F["finalize_response"]
    C3 -->|"no, iterations < 3"| REV["revise_itinerary"]
    C3 -->|"no, iterations = 3"| F2["finalize_response<br/>+ disclose open findings"]

    REV --> REV2{"over budget?"}
    REV2 -->|yes| REV3["inject optimisation brief:<br/>ranked savings levers +<br/>required Budget Optimisation section"]
    REV2 -->|no| REV4["fix reviewer findings only"]
    REV3 --> V1
    REV4 --> V1

    classDef code fill:#12b886,stroke:#0ca678,color:#fff
    class V5,V7,C2 code
```

The green steps are plain Python. That matters: a language model asked to check its own
arithmetic will often declare a \$3,450 plan "within a \$3,000 budget". By computing the
sum in code and instructing the critic to trust that verdict, the budget claim in the
final answer is always consistent with the numbers in the table.

**Observed behaviour** (real run, Rome, \$1,500 budget):

```text
Generated itinerary (4221 chars)
Budget validation: total $1,552 vs budget $1,500 → over budget
Critic: FAIL (preference match 100%, 2 issues)
Revised itinerary (attempt 1 of 3)
Budget validation: total $1,500 vs budget $1,500 → within budget
Critic: PASS (0 issues)
Finalised response
```

---

## 6. Loop termination guarantees

Three independent mechanisms, because an agent that cannot stop is worse than one that
gives an imperfect answer:

| Loop | Guard | Default | Behaviour at the cap |
| --- | --- | ---: | --- |
| retrieve → grade → web → rewrite → retrieve | `state["retries"]` vs `MAX_RETRIEVAL_RETRIES` | 2 | Proceed to generation with the best context found |
| validate → critic → revise → validate | `state["iteration_count"]` vs `MAX_REVISIONS` | 3 | Finalise and disclose unresolved findings |
| any unexpected cycle | LangGraph `recursion_limit` | 40 | Graph raises; `answer()` catches and returns a graceful message |

---

## 7. Error handling strategy

| Failure | Handling |
| --- | --- |
| MCP server down | `mcp_client.call_tool` returns `{"error": ...}`; retrieval yields no docs → web fallback engages |
| Vector DB missing | Retriever returns an actionable error naming the build command |
| Embedding 429 | Throttled batching + exponential backoff; ingest resumes from what is already stored |
| LLM 429 / 5xx | `HttpRetryOptions(attempts=6)` on ADK and Agno models; `max_retries=6` on LangChain |
| Structured output invalid | Every call returns `None` on failure; each node has an explicit fallback path |
| Remote agent down | Host catches, returns a graceful message, logs the cause; UI *Service status* panel shows which agent is offline |
| Booking on unknown id | Tool returns a validation error, never a partial write |
| Bad tool input | Validated and rejected with a message naming the offending field |
| Any handler exception | Becomes an A2A `failed` task with a readable message; stack traces stay in the server log |

---

## 8. Observability

`common/logging_utils.py` emits greppable `key=value` lines and redacts anything that
looks like a credential.

```text
event=host_request request_id=e35f48fb query="Find a mid-range hotel in Tokyo…"
event=a2a_delegation request_id=e35f48fb agent=travel_operations_agent
event=request_classified category=search
event=tool_call tool=search_hotels destination=Tokyo count=4 nights=-
event=host_request_complete request_id=e35f48fb agents=['travel_operations_agent'] chars=898
```

Logged: request id, user query, routing decision, agent selected, MCP server and tool
called, retrieval count, relevance result, budget status, critic verdict, revision count,
final status. Never logged: API keys, tokens, authorization headers.
