import os
import base64
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

groq_key = os.getenv("GROQ_API_KEY")
client = OpenAI(
    api_key=groq_key,
    base_url="https://api.groq.com/openai/v1",
)

import io
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (200, 100), color = 'white')
d = ImageDraw.Draw(img)
d.text((10,10), "Hello World OCR", fill=(0,0,0))
img_byte_arr = io.BytesIO()
img.save(img_byte_arr, format='JPEG')
b64_image = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
image_url = f"data:image/jpeg;base64,{b64_image}"

try:
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract the text from this image exactly."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ],
            }
        ],
    )
    print("Success:")
    print(response.choices[0].message.content)
except Exception as e:
    if hasattr(e, 'response') and hasattr(e.response, 'json'):
        print("API Error from Groq:")
        print(e.response.json())
    else:
        print("Other Error:", e)
