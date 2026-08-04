"""Gradio UI for the travel planner.

Two ways to ask for the same thing:
  * the chat box — free-form natural language
  * the trip form — fields composed into a request

Both go through the Host Router, which delegates over A2A. Deliberately, this
surface exposes none of that: no framework names, no agent names, no execution
trace. The trace is still captured and logged by `runner.py` for debugging, and
`SHOW_TRACE` below flips it back into the UI in one step if it is ever wanted.

Run (after the backend services are up):
    uv run python -m host_agent.main
"""
from __future__ import annotations

import gradio as gr

from common.config import settings
from common.logging_utils import get_logger
from host_agent.a2a_client import health_check
from host_agent.runner import HostRunner
from host_agent.ui_theme import CSS, theme

logger = get_logger("host.ui")

# The backend always records an execution trace (see HostResult.trace); this only
# controls whether the UI renders it.
SHOW_TRACE = False

# A self-contained travel scene (dusk sky, mountains, a plane on a flight path).
# Inline SVG so there's no external image dependency.
HERO_SCENE = """
<svg class="tp-scene" viewBox="0 0 1200 260" preserveAspectRatio="xMidYMid slice"
     xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Travel scene">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#0b2a4a"/>
      <stop offset="45%" stop-color="#14577a"/>
      <stop offset="78%" stop-color="#2f9c96"/>
      <stop offset="100%" stop-color="#f0a35e"/>
    </linearGradient>
    <linearGradient id="m1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0d3b47"/><stop offset="100%" stop-color="#0a2c38"/>
    </linearGradient>
    <linearGradient id="m2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#124e52"/><stop offset="100%" stop-color="#0e3d45"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="260" fill="url(#sky)"/>
  <circle cx="915" cy="150" r="46" fill="#ffd9a0" opacity="0.92"/>
  <circle cx="915" cy="150" r="70" fill="#ffcf8f" opacity="0.18"/>
  <!-- clouds -->
  <g fill="#ffffff" opacity="0.22">
    <ellipse cx="230" cy="70" rx="60" ry="15"/><ellipse cx="290" cy="78" rx="45" ry="12"/>
    <ellipse cx="1000" cy="55" rx="52" ry="13"/><ellipse cx="1055" cy="62" rx="38" ry="10"/>
  </g>
  <!-- birds -->
  <g stroke="#e8f6f2" stroke-width="2.5" fill="none" opacity="0.6" stroke-linecap="round">
    <path d="M120 96 q9 -8 18 0 q9 -8 18 0"/>
    <path d="M170 112 q7 -6 14 0 q7 -6 14 0"/>
  </g>
  <!-- flight path + plane -->
  <path d="M60 205 Q 430 60 1120 120" stroke="#eaf6f2" stroke-width="2.5"
        stroke-dasharray="3 9" fill="none" opacity="0.75"/>
  <g transform="translate(690 92) rotate(18)">
    <path d="M0 0 L34 8 L34 -8 Z" fill="#ffffff"/>
    <path d="M8 0 L20 -18 L26 -18 L18 0 Z" fill="#eaf6f2"/>
    <path d="M8 0 L20 18 L26 18 L18 0 Z" fill="#d7ece6"/>
  </g>
  <!-- mountain layers -->
  <path d="M0 260 L0 175 L160 120 L320 178 L470 128 L640 195 L640 260 Z" fill="url(#m2)" opacity="0.9"/>
  <path d="M560 260 L560 168 L720 118 L900 182 L1050 132 L1200 186 L1200 260 Z" fill="url(#m2)" opacity="0.9"/>
  <path d="M0 260 L0 214 L210 168 L430 216 L640 176 L860 220 L1080 178 L1200 214 L1200 260 Z" fill="url(#m1)"/>
</svg>
"""

HERO = f"""
<div id="tp-hero-banner">
  {HERO_SCENE}
  <div class="tp-scrim"></div>
  <div class="tp-hero-content">
    <span class="tp-kicker"><span class="live-dot"></span>Live flight booking · sample stays</span>
    <h1>Where would you like to go?</h1>
    <p>Tell me about your trip and I'll plan it end to end — a day-by-day
       itinerary with costs, places to stay, and things to do.</p>
  </div>
</div>
"""

GREETING = (
    "Hi! I can help you plan a trip from start to finish.\n\n"
    "Tell me **where** you'd like to go, **how long** you have, and roughly "
    "**what you'd like to spend** — and I'll put together a day-by-day plan "
    "with costs, hotels, food, and things to do.\n\n"
    "You can also ask me narrower things, like *\"find a hotel in Tokyo under "
    "$150 a night\"* or *\"what's the cancellation policy?\"*"
)

# Short label -> the request actually sent.
SUGGESTIONS = [
    ("🗾 7 days in Japan",
     "Plan a 7-day trip to Japan for 2 people in October with a budget of $3,000. "
     "We love Japanese food, anime, temples, and cultural experiences. We prefer "
     "mid-range hotels and don't want a hectic schedule."),
    ("🥐 Paris, museums & food",
     "Plan a 5-day trip to Paris. I love museums and food but don't like nightlife."),
    ("💰 London on $2,000",
     "Plan a trip to London for $2,000. If it exceeds my budget, optimize it."),
    ("🏨 Hotels in Tokyo",
     "Find a mid-range hotel in Tokyo under $150 per night."),
    ("⛩️ Things to do in Kyoto",
     "What are the best cultural activities in Kyoto?"),
    ("📄 Cancellation policy",
     "What is the hotel cancellation policy?"),
]

INTERESTS = [
    "food", "history", "art & museums", "temples", "anime", "nature",
    "beaches", "hiking", "shopping", "nightlife", "photography", "relaxation",
]

POPULAR_DESTINATIONS = ["Tokyo", "Kyoto", "Paris", "Rome", "Barcelona",
                        "Bangkok", "New York", "Dubai"]

CAPABILITIES = ["Plan day-by-day itineraries", "Search & book flights",
                "Find hotels & activities", "Optimise to your budget",
                "Explain travel policies"]


def _footer_html() -> str:
    """A website-style footer, honest about which data is live.

    Flights are live when a flight provider is configured; hotels, activities,
    and policies are always sample data.
    """
    from common.config import settings

    if settings.use_duffel_flights:
        note = ("<strong>Flights are booked live</strong> in a safe test mode — "
                "real airlines and a real booking reference, but no payment is "
                "taken and no seat is really held. Hotels, activities, and "
                "policies are sample data with estimated prices.")
    else:
        note = ("<strong>This is a demonstration.</strong> Flights, hotels, and "
                "activities are sample data with estimated prices; bookings are "
                "practice records with no payment and nothing really reserved.")

    dests = "".join(f"<li>{d}</li>" for d in POPULAR_DESTINATIONS[:6])
    caps = "".join(f"<li>{c}</li>" for c in CAPABILITIES)

    return f"""
<div id="tp-foot">
  <div class="tp-foot-cols">
    <div class="tp-foot-brand">
      <h3>🧭 Wanderplan</h3>
      <p>Your AI travel companion — describe a trip in plain words and get a
         complete, budget-aware plan in seconds.</p>
    </div>
    <div class="tp-foot-col">
      <h4>Popular</h4>
      <ul>{dests}</ul>
    </div>
    <div class="tp-foot-col">
      <h4>What it does</h4>
      <ul>{caps}</ul>
    </div>
    <div class="tp-foot-col">
      <h4>Good to know</h4>
      <p class="tp-foot-note">{note} Please confirm details with the airline,
         hotel, or an official source before you travel.</p>
    </div>
  </div>
  <div class="tp-foot-bottom">
    <span>© 2026 Wanderplan · A demonstration project.</span>
    <span class="tp-made">
      Planned by a team of AI travel agents
      <span class="tp-badge2">AI planning</span>
      <span class="tp-badge2">Live flights</span>
    </span>
  </div>
</div>
"""


FOOTER = _footer_html()


def _to_iso_date(value) -> str:
    """Normalise a date-picker value to an ISO date string (YYYY-MM-DD).

    gr.DateTime can hand back a float epoch timestamp or a string depending on
    version/config, so accept either and always emit a clean date (or "").
    """
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        from datetime import datetime
        try:
            return datetime.fromtimestamp(float(value)).date().isoformat()
        except (ValueError, OSError, OverflowError):
            return ""
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]  # already ISO-ish
    from datetime import datetime
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text[:10]


def compose_request(
    destination: str, origin: str, start_date, end_date,
    travelers: int, budget: float, currency: str, interests: list[str],
    travel_style: str, accommodation: str, extra: str,
) -> str:
    """Turn the trip form into a natural-language request."""
    parts: list[str] = []

    destination = (destination or "").strip()
    parts.append(f"Plan a trip to {destination}" if destination else "Plan a trip")

    origin = (origin or "").strip()
    if origin:
        parts.append(f"departing from {origin}")

    start_date = _to_iso_date(start_date)
    end_date = _to_iso_date(end_date)
    if start_date and end_date:
        parts.append(f"from {start_date} to {end_date}")
    elif start_date:
        parts.append(f"starting {start_date}")

    if travelers:
        count = int(travelers)
        parts.append(f"for {count} {'traveller' if count == 1 else 'travellers'}")
    if budget:
        parts.append(f"with a total budget of {budget:,.0f} {currency}")

    request = " ".join(parts) + "."

    if interests:
        request += f" We are interested in {', '.join(interests)}."
    if travel_style and travel_style != "no preference":
        request += f" We prefer a {travel_style} pace."
    if accommodation and accommodation != "no preference":
        request += f" We would like {accommodation} accommodation."
    if (extra or "").strip():
        request += f" {extra.strip()}"

    return request


def _initial_history() -> list[dict]:
    return [{"role": "assistant", "content": GREETING}]


async def _run(message: str, history: list, runner: HostRunner | None):
    """Shared handler for the chat box, the suggestion chips, and the form."""
    if not message or not message.strip():
        return history, runner, ""

    if runner is None:
        runner = HostRunner()

    history = list(history) + [{"role": "user", "content": message}]

    try:
        result = await runner.ask(message)
        reply = result.answer
        if SHOW_TRACE and result.trace:
            reply += "\n\n---\n" + "\n".join(f"- {step.strip()}"
                                             for step in result.trace)
    except Exception:
        # Never let a backend failure blank the UI.
        logger.exception("UI request failed")
        reply = ("Sorry — I couldn't reach the planning service just now. "
                 "Please try again in a moment.")

    history = history + [{"role": "assistant", "content": reply}]
    return history, runner, ""


async def respond_chat(message: str, history: list, runner: HostRunner | None):
    return await _run(message, history, runner)


async def respond_form(
    destination: str, origin: str, start_date: str, end_date: str,
    travelers: int, budget: float, currency: str, interests: list[str],
    travel_style: str, accommodation: str, extra: str,
    history: list, runner: HostRunner | None,
):
    message = compose_request(
        destination, origin, start_date, end_date, travelers, budget,
        currency, interests, travel_style, accommodation, extra,
    )
    return await _run(message, history, runner)


def reset_chat():
    """Start a fresh conversation (new runner = new session)."""
    return _initial_history(), None, ""


async def service_status() -> str:
    """A quiet, user-facing readiness line — no hostnames or agent internals."""
    try:
        status = await health_check()
    except Exception:
        return "⚠️ Can't check the service right now."

    if all(info["online"] for info in status.values()):
        return "🟢 Ready to plan your trip."
    if any(info["online"] for info in status.values()):
        return "🟡 Partly available — some requests may not work yet."
    return ("🔴 The planning service isn't running. Start it with "
            "`uv run python run_all.py`.")


def build_ui() -> gr.Blocks:
    """Build the Blocks tree.

    Styling is applied at launch time — Gradio 6 moved `css` and `theme` off the
    Blocks constructor onto `launch()`. Use `launch_ui()` so both are applied.
    """
    with gr.Blocks(title="Travel Planner") as demo:
        gr.HTML(HERO)

        runner_state = gr.State(None)

        with gr.Row(equal_height=False):
            # ---------------- conversation ----------------
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    value=_initial_history(),
                    height=560,
                    show_label=False,
                    elem_id="tp-chat",
                )

                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="e.g. Plan 6 relaxed days in Rome for two, "
                                    "around $2,500…",
                        show_label=False,
                        autofocus=True,
                        lines=2,
                        scale=9,
                        elem_id="tp-input",
                    )
                    with gr.Column(scale=1, min_width=112):
                        send = gr.Button("Send", elem_id="tp-send")
                        clear = gr.Button("New chat", elem_id="tp-clear")

                gr.Markdown("**Try one of these**")
                with gr.Row(elem_id="tp-chips"):
                    chips = [gr.Button(label, size="sm") for label, _ in SUGGESTIONS]

                status = gr.Markdown("🟢 Ready to plan your trip.", elem_id="tp-status")

            # ---------------- trip form ----------------
            with gr.Column(scale=2):
                with gr.Group(elem_classes="tp-card"):
                    gr.HTML('<p class="tp-card-title">✈️ Trip details '
                            '<span style="font-weight:400;opacity:.65">— optional'
                            '</span></p>')

                    destination = gr.Textbox(label="Destination",
                                             placeholder="Tokyo, Paris, Rome…")
                    origin = gr.Textbox(label="Flying from",
                                        placeholder="New York, London, Delhi…")
                    with gr.Row():
                        # Calendar date pickers (date only).
                        start_date = gr.DateTime(
                            label="Depart", include_time=False, type="string",
                            elem_classes="tp-date",
                        )
                        end_date = gr.DateTime(
                            label="Return", include_time=False, type="string",
                            elem_classes="tp-date",
                        )
                    with gr.Row():
                        travelers = gr.Dropdown(
                            choices=[str(n) for n in range(1, 11)],
                            value="2", label="Travellers",
                        )
                        budget = gr.Number(label="Budget", value=3000)
                        currency = gr.Dropdown(
                            ["USD", "EUR", "GBP", "INR", "AUD"],
                            value="USD", label="Currency",
                        )

                    interests = gr.CheckboxGroup(
                        INTERESTS, label="What do you enjoy?",
                        elem_classes="tp-interests",
                    )
                    with gr.Row():
                        travel_style = gr.Dropdown(
                            ["relaxed", "moderate", "packed", "no preference"],
                            value="moderate", label="Pace",
                        )
                        accommodation = gr.Dropdown(
                            ["budget", "mid-range", "luxury", "no preference"],
                            value="mid-range", label="Stay",
                        )
                    extra = gr.Textbox(
                        label="Anything else I should know?",
                        placeholder="Dietary needs, accessibility, things to avoid…",
                        lines=2,
                    )
                    plan_btn = gr.Button("Plan my trip", elem_id="tp-plan")

        gr.HTML(FOOTER)

        # ---------------- wiring ----------------
        outputs = [chatbot, runner_state, msg]

        for trigger in (msg.submit, send.click):
            trigger(respond_chat, [msg, chatbot, runner_state], outputs)

        plan_btn.click(
            respond_form,
            [destination, origin, start_date, end_date, travelers, budget,
             currency, interests, travel_style, accommodation, extra,
             chatbot, runner_state],
            outputs,
        )

        clear.click(reset_chat, None, outputs)

        # Each chip sends its full request text, not the short label.
        for button, (_, request_text) in zip(chips, SUGGESTIONS):
            button.click(
                respond_chat,
                [gr.State(request_text), chatbot, runner_state],
                outputs,
            )

        # Check readiness once on load so a stopped backend is obvious.
        demo.load(service_status, None, status)

    return demo


# Force the app into light mode regardless of the visitor's OS/browser setting.
# Gradio honours a `?__theme=light` URL parameter and, when present, never adds
# its `.dark` class — so both Gradio's components and our palette stay light and
# consistent. This <head> script runs while the page is parsing (before Gradio's
# theme logic), so it redirects once and light renders from the very first paint.
FORCE_LIGHT_HEAD = """
<script>
(function () {
  try {
    var u = new URL(window.location.href);
    if (u.searchParams.get('__theme') !== 'light') {
      u.searchParams.set('__theme', 'light');
      window.location.replace(u.toString());
    }
  } catch (e) {}
})();
</script>
"""

# Belt-and-suspenders: if anything still adds the dark class, strip it on load.
FORCE_LIGHT_JS = """
() => {
  const strip = () => document.body && document.body.classList.remove('dark');
  strip();
  new MutationObserver(strip).observe(
    document.documentElement, { subtree: true, attributes: true, attributeFilter: ['class'] }
  );
}
"""


def launch_ui(**kwargs):
    """Build and launch the UI with its styling applied.

    Single place that owns the css/theme/head/js arguments, so every entry point
    (`host_agent.main`, `run_all.py`, this module) renders identically — and
    always in light mode.
    """
    options = {
        "server_name": settings.host,
        "server_port": settings.ui_port,
        "css": CSS,
        "theme": theme(),
        "head": FORCE_LIGHT_HEAD,
        "js": FORCE_LIGHT_JS,
        **kwargs,
    }
    return build_ui().launch(**options)


if __name__ == "__main__":
    launch_ui()
