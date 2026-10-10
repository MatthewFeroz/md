@~/.agents/AGENTS.md

## Delegation

You (Opus) own the taste work: writing the code I merge, designing the architecture, building the UI, and making the editorial calls on my content. Everything outside Astra's list is yours too, with Opus subagents (Agent tool, `model: "opus"`) when work splits.

A background subagent from the Agent tool that ends its turn is finished, even if it says it's waiting on something. It won't wake up on its own. So a subagent must not end while its own background agents are still running. And when you get a `completed` notification, treat that agent as done: use its result, or message it if you need more.

Astra (`gpt-6-astra`, reasoning `high`, through T3's `delegate_task` on the `codex` provider) gets exactly these jobs: review, debugging, deep dives through unfamiliar code, computer use, visual checks. Its nitpickiness is the point. Astra reports findings; you write the fix. Outside T3, where `delegate_task` doesn't exist, run it from the shell with `codex exec -m gpt-6-astra -c model_reasoning_effort=high "<brief>"`.

Astra doesn't inherit this conversation. Give it the goal, the relevant context and a done condition, and ask it to report what it actually observed. For computer use it drives my real desktop, so keep it within the scope of my request.
