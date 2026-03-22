---
name: coach-prematch
description: Generate badminton pre-match guidance based on recent weaknesses, workload, and conditions. Trigger when the user asks what to focus on before training or a match.
---

# Coach Pre-match

Produce concise, actionable pre-match guidance.

## Required Focus

- Today's training or match focus
- Warm-up priorities
- Risk reminders for fatigue, hydration, or overload
- One concrete drill or tactical action

## Personalization Order

1. Current request
2. Recent thread context
3. `coach_profile.json`
4. `memory.json`
5. Recent review logs

## Follow-up Rules

If needed, ask about:
- singles or doubles
- indoor or outdoor
- today's main goal

Do not ask more than 2 questions before helping.
