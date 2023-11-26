import os
import json
import sys
import webbrowser
from pprint import pprint

from deep_translator import DeeplTranslator
from notion_client import Client
import click

# ------------------------
# Loading .env and env variables
from dotenv import load_dotenv

load_dotenv()
config = os.environ

global_debug = False


# Open a URL in the default web browser
def open_url(url):
    webbrowser.open(url)


# Check for required environment variables
if "NOTION_API_TOKEN" not in config:
    open_url("https://www.notion.so/my-integrations")
    sys.stderr.write("This tool requires a valid Notion API token...")
    sys.exit(1)

if "DEEPL_API_TOKEN" not in config:
    open_url("https://www.deepl.com/pro-api")
    sys.stderr.write("This tool requires a DeepL API token...")
    sys.exit(1)

# ------------------------
# DeepL API Client
translator = DeeplTranslator(api_key=config["DEEPL_API_TOKEN"])


def translate_text(rich_text_array, from_lang, to_lang):
    for each in rich_text_array:
        if "plain_text" in each:
            result = translator.translate(
                each["plain_text"], from_lang=from_lang, to_lang=to_lang
            )
            each["plain_text"] = result
            if "text" in each:
                each["text"]["content"] = each["plain_text"]


# Supported languages
supported_from_langs = [
    "BG",  # Bulgarian
    "CS",  # Czech
    "DA",  # Danish
    "DE",  # German
    "EL",  # Greek
    "EN",  # English
    "ES",  # Spanish
    "ET",  # Estonian
    "FI",  # Finnish
    "FR",  # French
    "HU",  # Hungarian
    "ID",  # Indonesian
    "IT",  # Italian
    "JA",  # Japanese
    "LT",  # Lithuanian
    "LV",  # Latvian
    "NL",  # Dutch
    "PL",  # Polish
    "PT",  # Portuguese
    "RO",  # Romanian
    "RU",  # Russian
    "SK",  # Slovak
    "SL",  # Slovenian
    "SV",  # Swedish
    "TR",  # Turkish
    "ZH",  # Chinese
]

supported_to_langs = [
    "BG",  # Bulgarian
    "CS",  # Czech
    "DA",  # Danish
    "DE",  # German
    "EL",  # Greek
    "EN-GB",  # English(British)
    "EN-US",  # English(American)
    "ES",  # Spanish
    "ET",  # Estonian
    "FI",  # Finnish
    "FR",  # French
    "HU",  # Hungarian
    "ID",  # Indonesian
    "IT",  # Italian
    "JA",  # Japanese
    "LT",  # Lithuanian
    "LV",  # Latvian
    "NL",  # Dutch
    "PL",  # Polish
    "PT-PT",  # Portuguese(all Portuguese varieties excluding Brazilian Portuguese)
    "PT-BR",  # Portuguese(Brazilian)
    "RO",  # Romanian
    "RU",  # Russian
    "SK",  # Slovak
    "SL",  # Slovenian
    "SV",  # Swedish
    "TR",  # Turkish
    "ZH",  # Chinese
]

printable_supported_from_langs = ",".join(
    [lang.lower() for lang in supported_from_langs]
)
printable_supported_to_langs = ",".join([lang.lower() for lang in supported_to_langs])


# ------------------------
# Utilities


def to_prettified_json(obj):
    return json.dumps(obj, indent=2)


def remove_unnecessary_properties(obj):
    keys_to_remove = [
        "id",
        "created_time",
        "last_edited_time",
        "created_by",
        "last_edited_by",
    ]
    for key in keys_to_remove:
        obj.pop(key, None)


# ------------------------
# Notion API Client

notion = Client(auth=config["NOTION_API_TOKEN"], log_level="ERROR")


# ------------------------
# Main code


def build_translated_blocks(block_id, nested_depth, debug):
    translated_blocks = []
    cursor = None
    has_more = True
    while has_more:
        blocks = notion.blocks.children.list(
            block_id=block_id, start_cursor=cursor, page_size=100
        )
        if debug:
            print(f"Fetched original blocks: {to_prettified_json(blocks['results'])}")
        sys.stdout.write(".")

        for result in blocks["results"]:
            b = result
            if nested_depth >= 2:
                b["has_children"] = False
            if nested_depth == 1 and b["type"] == "column_list":
                b["column_list"]["children"] = []
                continue
            if b["type"] == "unsupported":
                continue
            # ... [Rest of the block processing and translation logic]
            remove_unnecessary_properties(b)
            translated_blocks.append(b)

        if blocks["has_more"]:
            cursor = blocks["next_cursor"]
        else:
            has_more = False
    return translated_blocks


def create_new_page_for_translation(original_page, to_lang, debug):
    new_page = json.loads(json.dumps(original_page))  # Deep copy

    new_page["parent"] = {"page_id": original_page["id"]}

    original_title = (
        original_page["properties"]["title"]["title"][0]
        if "title" in original_page["properties"]
        else {"plain_text": "Translated page"}
    )

    new_title = new_page["properties"]["title"]["title"][0]
    new_title["text"]["content"] = original_title["text"]["content"] + f" ({to_lang})"
    new_title["plain_text"] = original_title["plain_text"] + f" ({to_lang})"
    remove_unnecessary_properties(new_page)

    if debug:
        print(f"New page creation request params: {to_prettified_json(new_page)}")
    new_page_creation = notion.pages.create(**new_page)
    if debug:
        print(f"New page creation response: {to_prettified_json(new_page_creation)}")
    return new_page_creation


@click.command()
@click.option(
    "--from",
    "-f",
    "from_lang",
    required=True,
    help="The language code of the original page",
)
@click.option(
    "--to",
    "-t",
    "to_lang",
    required=True,
    help="The language code of the translated page",
)
@click.option("--url", "-u", required=True, help="The URL of the original page")
@click.option("--debug", "-d", is_flag=True, help="Enable debug mode")
def main(from_lang, to_lang, url, debug):
    # Check if language codes are valid
    if from_lang.upper() not in supported_from_langs:
        sys.stderr.write(
            f"ERROR: {from_lang.upper()} is not a supported language code..."
        )
        sys.exit(1)

    if to_lang.upper() not in supported_to_langs:
        sys.stderr.write(
            f"ERROR: {to_lang.upper()} is not a supported language code..."
        )
        sys.exit(1)

    try:
        content_id = url.split("/")[-1].split("-")[-1]
        original_page = notion.pages.retrieve(page_id=content_id)
    except Exception as e:
        sys.stderr.write(
            f"\nERROR: Failed to read the page content!\n\nError details: {e}\n"
        )
        sys.exit(1)

    if debug:
        print(f"The page metadata: {to_prettified_json(original_page)}")

    sys.stdout.write(
        f"\nWait a minute! Now translating the Notion page: {url}\n\n(this may take some time) ..."
    )
    translated_blocks = build_translated_blocks(original_page["id"], 0, debug)
    new_page = create_new_page_for_translation(original_page, to_lang, debug)
    blocks_append_params = {"block_id": new_page["id"], "children": translated_blocks}

    if debug:
        print(
            f"Block creation request params: {to_prettified_json(blocks_append_params)}"
        )

    page_size = 10
    end_index = 0
    while end_index < len(translated_blocks):
        begin_index = end_index
        end_index = min(begin_index + page_size, len(translated_blocks))
        reduced_blocks = translated_blocks[begin_index:end_index]

        blocks_addition = notion.blocks.children.append(
            block_id=new_page["id"], children=reduced_blocks
        )
        if debug:
            print(f"Block creation response: {to_prettified_json(blocks_addition)}")

    print(
        "... Done!"
        "\n\nDisclaimer:"
        "\nSome parts might not be perfect."
        "\nIf the generated page is missing something, please adjust the details on your own.\n"
    )
    print(f"Here is the translated Notion page: {new_page['url']}\n")
    open_url(new_page["url"])


if __name__ == "__main__":
    main()
