## Use in Code

Florence-2-large is a powerful multimodal model that can perform various tasks:

- `<CAPTION>`: Generates a concise description of the entire image, summarizing its main content
- `<DETAILED_CAPTION>`: Produces a more elaborate description of the image, including finer details and contextual information
- `<MORE_DETAILED_CAPTION>`: Creates an exceptionally detailed caption, capturing intricate attributes and relationships within the image
- `<OD>`: Detects objects in an image and provides their bounding box coordinates along with labels
- `<DENSE_REGION_CAPTION>`: Generates captions for densely packed regions within an image, identifying multiple objects or areas simultaneously
- `<REGIONAL_PROPOSAL>`: Suggests specific regions in an image that may contain objects or areas of interest for further analysis
- `<CAPTION_TO_PHRASE_GROUNDING> your_text_input`: Aligns phrases from a generated caption with specific regions in the image, enabling precise visual-textual mapping
- `<REFERRING_EXPRESSION_SEGMENTATION> your_text_input`: Segments parts of an image based on textual descriptions of specific objects or regions
- `<REGION_TO_SEGMENTATION> your_text_input`: Converts bounding boxes into segmentation masks to outline specific objects or areas within an image
- `<OCR>`: Extracts text from an image as a single string, useful for reading printed or handwritten text
- `<OCR_WITH_REGION>`: Retrieves text from an image along with its location, providing bounding boxes for each piece of text

How to use with Pixels

```
// Start or stop the model
RemoteModelStart ( engine = "{ENGINE_ID}" )
RemoteModelShutdown ( engine = "{ENGINE_ID}" )


LLM ( engine = "{ENGINE_ID}" , command = "<CAPTION>", paramValues = [ {"image_url": "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/tasks/car.jpg?download=true"} ]) ;
// OR
Vision( engine = "{ENGINE_ID}" , command = "<DETAILED_CAPTION>", image = "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/tasks/car.jpg?download=true" )
```

How to use in Python

```
from gaas_gpt_model import ModelEngine

question = '<CAPTION>'
model = ModelEngine(engine_id = "{ENGINE_ID}", insight_id = '${i}')

model.ask(question = question, param_dict={"image_url": "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/tasks/car.jpg?download=true"})
```