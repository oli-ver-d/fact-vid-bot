import os
import time
import datetime

from pydantic import BaseModel
from openai import AzureOpenAI, OpenAI, BadRequestError
import requests
from dotenv import load_dotenv
import json
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip


class GPTResponse(BaseModel):
    script: str
    caption: str
    prompts: list[str]


load_dotenv()


def get_fact() -> str:
    url = 'https://api.api-ninjas.com/v1/facts'
    headers = {'X-Api-Key': os.getenv('API_NINJAS_KEY')}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return json.loads(response.text)[0]['fact']
    else:
        print(response.status_code)
        print(response.text)


def get_script_and_prompts(topic: str) -> GPTResponse:
    client = OpenAI()
    print("Querying OpenAI chatgpt")
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are a creative AI scriptwriter, you're scripts only include what the "
                                          "narrator will say, no stage directions and always start with 'Did you know'"},
            {"role": "user", "content": f"Create a 30 second script based on the following: {topic}. The script should "
                                        "only include what the narrator will say in plain text. As well return a "
                                        "caption for a video produced from the script and 3 prompts that will be used "
                                        "to generate AI images, ensure the prompts have high levels of detail and are "
                                        "relevant to the script, the theme of the images should be consistent."},
        ],
        response_format=GPTResponse,
    )

    event = completion.choices[0].message.parsed
    return event


def generate_images(prompts: list[str]) -> list[str]:
    images = []

    client = AzureOpenAI(
        api_version="2024-05-01-preview",
        azure_endpoint="https://openai-tiktokbot2.openai.azure.com/",
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )

    for idx, prompt in enumerate(prompts):
        print(f"Generating images for prompt {idx + 1} of {len(prompts)}")
        print(prompt)

        try:
            result = client.images.generate(
                model="dall-e-3",  # the name of your DALL-E 3 deployment
                prompt=prompt,
                n=1,
                size="1024x1792"
            )
        except BadRequestError as e:
            error_content = e
            if 'content_policy_violation' in error_content.code:
                # Log the policy violation
                print(f"Policy violation detected for prompt {idx + 1}: {prompt}")

                # Extract the revised (safe) prompt
                revised_prompt = error_content.body['inner_error']['revised_prompt']
                print(f"Rerunning with revised prompt: {revised_prompt}")

                # Retry with the safe prompt
                result = client.images.generate(
                    model="dall-e-3",
                    prompt=revised_prompt,
                    n=1,
                    size="1024x1792"
                )
            else:
                raise  # Re-raise the error if it's not a content policy violation

        image_url = json.loads(result.model_dump_json())['data'][0]['url']
        img_response = requests.get(image_url)
        img_filename = f"image_{idx + 1}.png"
        with open(img_filename, 'wb') as f:
            f.write(img_response.content)
        images.append(img_filename)

    return images


def text_to_speech_openai(text, filename, voice="nova"):
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT_SPEECH")
    AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")

    tts_url = AZURE_OPENAI_ENDPOINT
    tts_headers_list = {
        "api-key": AZURE_OPENAI_KEY,
        "Content-Type": "application/json"
    }

    tts_payload = json.dumps({
        "model": "tts",
        "input": text,
        "voice": voice,
    })

    print(f"Generating: {text}")

    while True:
        tts_response = requests.request("POST", tts_url, data=tts_payload, headers=tts_headers_list)
        if tts_response.status_code == 200:
            # Save the binary content to a file
            with open(filename, 'wb') as file:
                file.write(tts_response.content)
            print("TTS output file saved successfully as " + filename)
            return filename
        elif tts_response.status_code == 429:
            retry_after = int(tts_response.headers.get('Retry-After', 60))  # Default to 60 seconds if not specified
            print(f"Rate limit exceeded. Retrying after {retry_after} seconds...")
            time.sleep(retry_after)
        else:
            print(f"Failed to retrieve content. Status code: {tts_response.status_code}")
            print(f"Response content: {tts_response.text}")
            return None


def create_video(image_files, audio_file):
    clips = []
    audio = AudioFileClip(audio_file)
    duration = audio.duration / len(image_files)

    for img_file in image_files:
        clip = ImageClip(img_file).set_duration(duration)
        clips.append(clip)

    video = concatenate_videoclips(clips)
    final_video = video.set_audio(audio)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    final_video_filename = f"output_video_{timestamp}.mp4"
    final_video.write_videofile(final_video_filename, fps=24, audio_codec='aac')
    return final_video_filename


def generate_video():
    gpt = get_script_and_prompts(get_fact())
    images = generate_images(gpt.prompts)
    audio = text_to_speech_openai(gpt.script, "text_to_speech.mp3")
    filename = create_video(images, audio)
    return filename, gpt.caption


# images = generate_images(["A diverse crowd"])
_, caption = generate_video()
print(caption)
