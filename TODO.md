Product:
- write better analysis prompt: figure out what to extract and do it properly
- add some sort of memory: either pass in previous state, or what

Deployment:

Engineering:
- before unwarping should check if the unwarped does not already exists (unwarping is fast though)
- add telemetry and logs (for ex profiling the lambda)
- restructure the Lambda repo better
    - annoying to copy llm_vision in there
    - makefile should be at root
    - split llm and vision
    - etc
- add tests

