Product:
- write better analysis prompt: figure out what to extract and do it properly
- add some sort of memory: either pass in previous state, or what

Deployment:

Engineering:
- make LLM client async --> use vllm
- split vision_llm into a CV part and an LLM part
- before unwarping should check if the unwarped does not already exists (unwarping is fast though)
- add telemetry and logs (for ex profiling the lambda)

