---
name: coach-router
description: Route badminton coaching requests into prematch, postmatch, health, or fallback flows. Trigger when the user asks what kind of badminton guidance they need, mixes multiple goals, or the next skill choice is unclear.
---

# Coach Router

Use this skill first when the intent is ambiguous or mixed.

## Route Types

- `prematch`: before training or playing, asking what to focus on today
- `postmatch`: after playing, summarizing what went well or badly
- `health`: fatigue, soreness, recovery, heart rate, pain, or training load adjustment
- `fallback`: general planning, broad badminton advice, or incomplete context

## Decision Rules

1. Read the current message first.
2. Check recent thread context for missing details already mentioned.
3. Prefer the narrowest route that leads to an actionable answer.
4. If critical details are missing, ask 1-2 follow-up questions only.
5. For injury or sharp pain language, route to `health` immediately.

## Output Contract

When routing, make the decision explicit in your working context:
- primary route
- missing information
- whether a follow-up question is required
