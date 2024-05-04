from openai import OpenAI
from flask import Flask, request
from dotenv import load_dotenv
from yaml import full_load
from pathlib import Path
from uuid import uuid4
import re
from flask_cors import CORS, cross_origin
from diskcache import Cache

cache = Cache(".cache")

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
SPLIT_REGEX = r"([A-Z ]{4,})?:(.+)"

load_dotenv()
client = OpenAI() # pulls api key from dotenv

client.chat.completions.create = cache.memoize()(client.chat.completions.create)

prompts = full_load(Path("prompts.yml").read_text())
describe_prompt, reimagine_prompt, recipe_prompt = list(prompts.values())


sessions = {}

@app.route("/describe", methods=["POST"])
def ai_describe():
    global sessions
    history = [
        {"role": "user", "content": [
            {"type": "text", "text": describe_prompt},
            {
                "type": "image_url",
                "image_url": { "url": f"data:{request.get_json()["media_type"]};base64,{request.get_json()["image"]}" }
            }
        ]}
    ]
    
    print("Describing Image...")
    message = client.chat.completions.create(
        model="gpt-4-turbo",
        max_tokens=1024,
        messages=history
    )

    session_id = str(uuid4())

    history.append(message.choices[0].message)

    print(re.findall(SPLIT_REGEX, message.choices[0].message.content))
    sessions[session_id] = history

    return {k.lower().replace(" ", "_"):v for (k, v) in re.findall(SPLIT_REGEX, message.choices[0].message.content)} | {"session_id": session_id}

@app.route("/reimagine", methods=["POST"])
def ai_reimagine():
    print(request.get_json())
    history = sessions[request.get_json()["session_id"]]
    #TODO include the image as well because it might help
    history.append({"role": "user", "content": reimagine_prompt.format(request.get_json()["change"])})
    print("Requesting idea...")
    message = client.chat.completions.create(
        model="gpt-4-turbo",
        max_tokens=1024,
        messages=history
    )
    history.append(message.choices[0].message)
    print(message.choices[0].message.content)
    history.append({"role": "user", "content": recipe_prompt})
    print("Requesting Recipe...")
    message = client.chat.completions.create(
        model="gpt-4-turbo",
        max_tokens=1024,
        messages=history
    )

    text = message.choices[0].message.content

    print(text)

    ingredients = [s.strip() for s in re.search(r"(- .+\n)+", text).group(0).split("- ") if s.strip()]
    steps = [s.split('. ')[1].strip() for s in re.search(r"(\d+\. .+\n)+", text + "\n").group(0).splitlines() if s.strip()]

    print(ingredients)
    print(steps)  

    return {
        "ingredients": ingredients,
        "instructions": steps
    }


@app.route("/test", methods=["POST"])
def test():
    #print(request.get_json())
    return {
        "cultural_description": " Spaghetti Bolognese is a popular Italian dish known globally. Though its origins are from Bologna, Italy, it has been adapted in many countries to suit local tastes. Traditionally, it is a hearty meal, making it a staple in many households, and is often associated with family gatherings and comfort food.  ",
        "dietary_restriction": " non-vegetarian, non-vegan",
        "name": " Spaghetti Bolognese  ",
        "possible_allergens": " gluten, eggs (in pasta), beef  ",
        "session_id": "4c16f1ac-4ab9-48ab-9905-a602bc739eaa"
    }