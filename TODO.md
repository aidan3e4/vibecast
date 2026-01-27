Product: 
- write better analysis prompt: figure out what to extract
- add prompt versioning
- add some sort of memory: either pass in previous state, or what

Deployment:
- deploy a serverless function to process on runpod
- best practice to inject some vars into the script, for now they're copied from local repo

Engineer debt / optimizations:
- make LLM client async --> use vllm
- split vision_llm into a CV part and an LLM part
- before unwarping should check if the unwarped does not already exists (unwarping is fast though)