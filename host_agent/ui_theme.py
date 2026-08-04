"""Visual design system for the travel planner UI.

Kept separate from `gradio_app.py` so the layout code stays readable. Everything
here is presentation only — no application logic.

The palette is defined with CSS custom properties and adapts to the viewer's
light/dark preference, so the app doesn't glare in a dark room.
"""
from __future__ import annotations

import gradio as gr

# Teal/ocean primary with a warm amber accent — reads as "travel" without
# resorting to the usual saturated blue.
CSS = """
:root {
  --tp-primary:        #0f766e;
  --tp-primary-hover:  #115e59;
  --tp-primary-soft:   #ccfbf1;
  /* Solid teal for surfaces that carry WHITE text (buttons, chosen pills, user
     bubbles). Kept dark enough for legible white text in BOTH themes — separate
     from --tp-primary, which flips bright in dark mode for text/accents. */
  --tp-btn:            #0f766e;
  --tp-btn-hover:      #0c5f58;
  --tp-accent:         #f59e0b;
  --tp-bg:             #f8fafc;
  --tp-surface:        #ffffff;
  --tp-surface-2:      #f1f5f9;
  --tp-border:         #bcc8d9;   /* visible hairline on the off-white ground */
  --tp-border-strong:  #a6b4c9;   /* stronger edge for the main boxes */
  --tp-text:           #0f172a;
  --tp-text-muted:     #64748b;
  --tp-radius:         14px;
  --tp-radius-lg:      20px;
  --tp-shadow:         0 1px 2px rgba(15,23,42,.06), 0 8px 24px -12px rgba(15,23,42,.14);
}

/* Gradio drives light/dark itself by putting a `.dark` class on <body> (it
   auto-detects the OS preference and also honours a manual toggle). Keying our
   palette off that class — rather than @media (prefers-color-scheme) — keeps our
   surfaces in lock-step with Gradio's, so our text never lands on a mismatched
   background. Custom properties set on body.dark inherit down to every element. */
.dark {
  --tp-primary:       #2dd4bf;
  --tp-primary-hover: #5eead4;
  --tp-primary-soft:  #134e4a;
  --tp-btn:           #0d8577;   /* white text stays ~4.5:1 legible */
  --tp-btn-hover:     #109c8b;
  --tp-accent:        #fbbf24;
  --tp-bg:            #0b1120;
  --tp-surface:       #131c31;
  --tp-surface-2:     #1c2740;
  --tp-border:        #2c3b57;
  --tp-border-strong: #3a4c6d;
  --tp-text:          #e8eef9;
  --tp-text-muted:    #a3b2cc;
  --tp-shadow:        0 1px 2px rgba(0,0,0,.4), 0 10px 30px -12px rgba(0,0,0,.6);
}

/* ---------- page shell ---------- */
.gradio-container {
  max-width: 1180px !important;
  margin: 0 auto !important;
  background: var(--tp-bg) !important;
  font-family: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif !important;
  /* Gradio's Soft theme colours ALL component labels with the primary hue
     (teal), which is unreadable on the light card. Point the label/title text
     variables at our neutral text colour so every field label — dropdowns,
     date pickers, checkbox groups, textboxes — stays high-contrast. */
  --block-label-text-color: var(--tp-text) !important;
  --block-title-text-color: var(--tp-text) !important;
  /* Gradio's own borders default to near-invisible on the light ground
     (its --input-border-color is literally the page background). Route every
     Gradio border variable through our visible hairline so boxes, inputs,
     dropdowns, and date pickers all have a clear edge. */
  --border-color-primary: var(--tp-border) !important;
  --border-color-accent-subdued: var(--tp-border) !important;
  --block-border-color: var(--tp-border) !important;
  --input-border-color: var(--tp-border) !important;
  --input-border-color-hover: var(--tp-border-strong) !important;
  --input-border-color-focus: var(--tp-primary) !important;
  --checkbox-border-color: var(--tp-border) !important;
}
.gradio-container .prose :is(h1,h2,h3,p,li,td,th) { color: var(--tp-text); }

/* ---------- hero ---------- */
#tp-hero {
  background: linear-gradient(135deg, var(--tp-primary) 0%, #0891b2 55%, #0e7490 100%);
  border-radius: var(--tp-radius-lg);
  padding: 30px 34px 26px;
  margin-bottom: 20px;
  box-shadow: var(--tp-shadow);
  position: relative;
  overflow: hidden;
}
#tp-hero::after {                 /* soft light bloom, purely decorative */
  content: "";
  position: absolute;
  top: -70px; right: -50px;
  width: 260px; height: 260px;
  background: radial-gradient(circle, rgba(255,255,255,.22), transparent 70%);
  pointer-events: none;
}
#tp-hero h1 {
  color: #fff !important;
  font-size: 1.85rem !important;
  font-weight: 700 !important;
  margin: 0 0 6px !important;
  letter-spacing: -.02em;
}
#tp-hero p {
  color: rgba(255,255,255,.92) !important;
  margin: 0 !important;
  font-size: 1.02rem !important;
  max-width: 62ch;
}
#tp-hero .tp-badge {
  display: inline-block;
  margin-top: 14px;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,.18);
  border: 1px solid rgba(255,255,255,.3);
  color: #fff !important;
  font-size: .78rem;
  font-weight: 500;
  backdrop-filter: blur(4px);
}

/* ---------- cards ---------- */
.tp-card {
  background: var(--tp-surface) !important;
  border: 1px solid var(--tp-border-strong) !important;
  border-radius: var(--tp-radius-lg) !important;
  padding: 18px !important;
  box-shadow: var(--tp-shadow) !important;
}
.tp-card-title {
  font-weight: 650;
  font-size: .95rem;
  color: var(--tp-text);
  margin: 0 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ---------- chat ---------- */
#tp-chat {
  border: 1px solid var(--tp-border-strong) !important;
  border-radius: var(--tp-radius-lg) !important;
  background: var(--tp-surface) !important;
  box-shadow: var(--tp-shadow) !important;
}
#tp-chat .message-wrap { gap: 14px !important; }
#tp-chat .message {
  border-radius: var(--tp-radius) !important;
  font-size: .95rem !important;
  line-height: 1.62 !important;
  border: none !important;
  padding: 13px 16px !important;
}
#tp-chat .user .message,
#tp-chat .message.user {
  background: var(--tp-btn) !important;
  color: #fff !important;
}
#tp-chat .user .message :is(p,span,strong) { color: #fff !important; }
#tp-chat .bot .message,
#tp-chat .message.bot {
  background: var(--tp-surface-2) !important;
  color: var(--tp-text) !important;
}
/* Itineraries are long and table-heavy — keep them legible. */
#tp-chat .message table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: .88rem;
  display: block;
  overflow-x: auto;        /* wide tables scroll, page never does */
}
#tp-chat .message th {
  background: var(--tp-primary-soft);
  color: var(--tp-text);
  text-align: left;
  padding: 8px 10px;
  font-weight: 600;
  white-space: nowrap;
}
#tp-chat .message td {
  padding: 8px 10px;
  border-top: 1px solid var(--tp-border);
}
#tp-chat .message h2 {
  font-size: 1.06rem !important;
  margin: 20px 0 8px !important;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--tp-primary-soft);
}
#tp-chat .message h3 {
  font-size: .98rem !important;
  margin: 16px 0 6px !important;
  color: var(--tp-primary) !important;
}
#tp-chat .message hr { border-color: var(--tp-border); margin: 18px 0; }
#tp-chat .message blockquote {
  border-left: 3px solid var(--tp-accent);
  padding-left: 12px;
  color: var(--tp-text-muted);
}

/* ---------- inputs ---------- */
#tp-input textarea {
  border-radius: var(--tp-radius) !important;
  border: 1.5px solid var(--tp-border) !important;
  background: var(--tp-surface) !important;
  color: var(--tp-text) !important;
  font-size: .97rem !important;
  padding: 13px 15px !important;
  resize: none !important;
  transition: border-color .15s, box-shadow .15s;
}
#tp-input textarea:focus {
  border-color: var(--tp-primary) !important;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--tp-primary) 18%, transparent) !important;
  outline: none !important;
}
.tp-card :is(input, textarea, select) {
  border-radius: 10px !important;
  border: 1.5px solid var(--tp-border) !important;
  background: var(--tp-surface) !important;
  color: var(--tp-text) !important;
}
.tp-card :is(input, textarea, select):focus {
  border-color: var(--tp-primary) !important;
  outline: none !important;
}
.tp-card label span, .tp-card .block-title {
  font-size: .84rem !important;
  font-weight: 600 !important;
  color: var(--tp-text) !important;      /* crisp field labels */
  background: transparent !important;    /* drop Gradio's stray tinted label bg */
}

/* ---------- buttons ---------- */
#tp-send, #tp-plan {
  background: var(--tp-btn) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--tp-radius) !important;
  font-weight: 600 !important;
  font-size: .95rem !important;
  box-shadow: 0 2px 8px -2px color-mix(in srgb, var(--tp-btn) 55%, transparent) !important;
  transition: transform .12s, background .15s;
}
#tp-send:hover, #tp-plan:hover {
  background: var(--tp-btn-hover) !important;
  transform: translateY(-1px);
}
#tp-send:active, #tp-plan:active { transform: translateY(0); }
#tp-plan { padding: 13px 18px !important; margin-top: 6px !important; }
#tp-clear button, #tp-clear {
  background: transparent !important;
  color: var(--tp-text-muted) !important;
  border: 1.5px solid var(--tp-border) !important;
  border-radius: var(--tp-radius) !important;
  font-weight: 500 !important;
}
#tp-clear:hover { border-color: var(--tp-primary) !important; color: var(--tp-primary) !important; }

/* ---------- suggestion chips ---------- */
#tp-chips { gap: 8px !important; flex-wrap: wrap !important; }
#tp-chips button {
  background: var(--tp-surface) !important;
  border: 1.5px solid var(--tp-border) !important;
  border-radius: 999px !important;
  color: var(--tp-text) !important;
  font-size: .86rem !important;
  font-weight: 500 !important;
  padding: 8px 15px !important;
  box-shadow: none !important;
  transition: all .15s;
  white-space: nowrap;
}
#tp-chips button:hover {
  border-color: var(--tp-primary) !important;
  background: var(--tp-primary-soft) !important;
  color: var(--tp-primary) !important;
  transform: translateY(-1px);
}

/* ---------- interest checkboxes as pills ---------- */
.tp-interests .wrap { gap: 7px !important; flex-wrap: wrap !important; }
.tp-interests label {
  border: 1.5px solid var(--tp-border) !important;
  border-radius: 999px !important;
  padding: 6px 13px !important;
  background: var(--tp-surface) !important;
  font-size: .84rem !important;
  cursor: pointer;
  transition: all .14s;
  margin: 0 !important;
}
.tp-interests label:hover { border-color: var(--tp-primary) !important; }
.tp-interests label:has(input:checked) {
  background: var(--tp-btn) !important;
  border-color: var(--tp-btn) !important;
}
.tp-interests label:has(input:checked) span { color: #fff !important; }
.tp-interests input { display: none !important; }

/* radios read better as pills too */
.tp-pills .wrap { gap: 7px !important; flex-wrap: wrap !important; }
.tp-pills label {
  border: 1.5px solid var(--tp-border) !important;
  border-radius: 999px !important;
  padding: 6px 13px !important;
  background: var(--tp-surface) !important;
  font-size: .84rem !important;
  cursor: pointer;
  margin: 0 !important;
  transition: all .14s;
}
.tp-pills label:has(input:checked) {
  background: var(--tp-primary) !important;
  border-color: var(--tp-primary) !important;
}
.tp-pills label:has(input:checked) span { color: #fff !important; }
.tp-pills input { display: none !important; }

/* ---------- status line ---------- */
#tp-status { font-size: .84rem !important; color: var(--tp-text-muted) !important; }
#tp-status p { margin: 3px 0 !important; }

/* ---------- date pickers (gr.DateTime) ---------- */
.tp-card .datetime, .tp-date input {
  border-radius: 10px !important;
}
.tp-date input {
  border: 1.5px solid var(--tp-border) !important;
  background: var(--tp-surface) !important;
  color: var(--tp-text) !important;
  padding: 9px 12px !important;
}
.tp-date input:focus {
  border-color: var(--tp-primary) !important;
  outline: none !important;
}
/* Gradio's calendar dropdown */
.tp-date .calendar, .datetime .calendar {
  border: 1px solid var(--tp-border) !important;
  background: var(--tp-surface) !important;
  border-radius: 12px !important;
  box-shadow: var(--tp-shadow) !important;
}

/* dropdowns match the rest of the form */
.tp-card .wrap-inner, .tp-card [data-testid="dropdown"] {
  border-radius: 10px !important;
}

/* ---------- hero banner (image at top) ---------- */
#tp-hero-banner {
  position: relative;
  border-radius: var(--tp-radius-lg);
  overflow: hidden;
  box-shadow: var(--tp-shadow);
  margin-bottom: 20px;
  min-height: 210px;
  display: flex;
  align-items: flex-end;
}
#tp-hero-banner svg.tp-scene {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
#tp-hero-banner .tp-scrim {
  position: absolute;
  inset: 0;
  background: linear-gradient(100deg,
    rgba(6, 20, 30, .74) 0%,
    rgba(6, 20, 30, .42) 42%,
    rgba(6, 20, 30, .05) 72%);
}
#tp-hero-banner .tp-hero-content {
  position: relative;
  z-index: 2;
  padding: 26px 30px 24px;
  color: #fff;
}
#tp-hero-banner .tp-kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: .74rem;
  font-weight: 600;
  letter-spacing: .04em;
  text-transform: uppercase;
  padding: 5px 12px;
  border-radius: 999px;
  color: #ffffff;                 /* sits on the dark banner scrim in both themes */
  background: rgba(255, 255, 255, .18);
  border: 1px solid rgba(255, 255, 255, .30);
  backdrop-filter: blur(4px);
  margin-bottom: 14px;
}
#tp-hero-banner .tp-kicker .live-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #fca5a5;
  box-shadow: 0 0 0 0 rgba(252, 165, 165, .7);
  animation: tp-pulse 2.4s ease-out infinite;
}
@keyframes tp-pulse {
  0% { box-shadow: 0 0 0 0 rgba(252,165,165,.6); }
  70% { box-shadow: 0 0 0 8px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
}
@media (prefers-reduced-motion: reduce) { #tp-hero-banner .tp-kicker .live-dot { animation: none; } }
#tp-hero-banner h1 {
  margin: 0 0 8px !important;
  font-size: clamp(1.7rem, 3.6vw, 2.5rem) !important;
  font-weight: 800 !important;
  letter-spacing: -.02em;
  color: #fff !important;
  text-shadow: 0 2px 18px rgba(0, 0, 0, .35);
}
#tp-hero-banner p {
  margin: 0 !important;
  max-width: 54ch;
  font-size: 1.02rem !important;
  color: rgba(255, 255, 255, .94) !important;
  text-shadow: 0 1px 10px rgba(0, 0, 0, .3);
}

/* ---------- website-style footer ---------- */
#tp-foot {
  margin-top: 30px;
  border-radius: var(--tp-radius-lg);
  background: var(--tp-surface);
  border: 1px solid var(--tp-border-strong);
  overflow: hidden;
}
#tp-foot .tp-foot-cols {
  display: grid;
  grid-template-columns: 1.6fr 1fr 1fr 1.4fr;
  gap: 28px;
  padding: 30px 34px 26px;
}
#tp-foot .tp-foot-brand h3 {
  margin: 0 0 8px;
  font-size: 1.15rem;
  font-weight: 750;
  color: var(--tp-text);
}
#tp-foot .tp-foot-brand p {
  margin: 0;
  font-size: .86rem;
  color: var(--tp-text-muted);
  line-height: 1.6;
  max-width: 34ch;
}
#tp-foot .tp-foot-col h4 {
  margin: 0 0 12px;
  font-size: .72rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--tp-primary);
  font-weight: 700;
}
#tp-foot .tp-foot-col ul { list-style: none; margin: 0; padding: 0; }
#tp-foot .tp-foot-col li {
  font-size: .88rem;
  color: var(--tp-text-muted);
  padding: 4px 0;
}
#tp-foot .tp-foot-note {
  font-size: .82rem;
  color: var(--tp-text-muted);
  line-height: 1.6;
}
#tp-foot .tp-foot-note strong { color: var(--tp-text); }
#tp-foot .tp-foot-bottom {
  border-top: 1px solid var(--tp-border);
  background: var(--tp-surface-2);
  padding: 15px 34px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  font-size: .8rem;
  color: var(--tp-text-muted);
}
#tp-foot .tp-foot-bottom .tp-made { display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }
#tp-foot .tp-foot-bottom .tp-badge2 {
  font-size: .72rem;
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--tp-primary-soft);
  color: var(--tp-primary);
  font-weight: 600;
}

/* hide Gradio's own branding footer — this should feel like a product */
footer { display: none !important; }

/* ---------- responsive ---------- */
@media (max-width: 860px) {
  #tp-hero-banner { min-height: 180px; }
  #tp-hero-banner .tp-hero-content { padding: 20px 22px; }
  #tp-foot .tp-foot-cols { grid-template-columns: 1fr 1fr; gap: 22px; }
  .gradio-container { padding: 8px !important; }
}
@media (max-width: 520px) {
  #tp-foot .tp-foot-cols { grid-template-columns: 1fr; }
  #tp-foot .tp-foot-bottom { flex-direction: column; align-items: flex-start; }
}
"""


def theme() -> gr.Theme:
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.teal,
        secondary_hue=gr.themes.colors.cyan,
        neutral_hue=gr.themes.colors.slate,
        font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
    )
