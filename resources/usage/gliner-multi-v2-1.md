## Use in Code

How to use with Pixels

```jsx
// Start or stop the model
RemoteModelStart ( engine = "{ENGINE_ID}" )
RemoteModelShutdown ( engine = "{ENGINE_ID}" )


NER( engine = "{ENGINE_ID}" , prompt = "John Smith works at Microsoft in Seattle" , entities=["PERSON", "ORGANIZATION", "LOCATION"], maskEntities=["PERSON", "ORGANIZATION"] )
```

How to use in Python

```python
from gaas_gpt_model import ModelEngine

text="John Smith works at Apple in California."
entities=["PERSON", "ORGANIZATION", "LOCATION"]
mask_entities=["PERSON", "ORGANIZATION"]

model = ModelEngine(engine_id = "ENGINE_ID", insight_id='${i}')

model.ner(text = text, entities = entities, mask_entities = mask_entities )
```