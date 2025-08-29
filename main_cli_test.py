import os
from openai import OpenAI

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://c9c2e2967d13.ngrok-free.app")
MCP_PATH = os.getenv("MCP_PATH", "/mcp")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

def ask_forecast(
    place: str = "Copenhagen, DK",
    days: int = 3,
    units: str = "C",
    lang: str = "en",
):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    server_url = f"{MCP_SERVER_URL.rstrip('/')}{MCP_PATH}/"

    mcp_tool = {
        "type": "mcp",
        "server_label": "weather_server",
        "server_url": server_url,
        "allowed_tools": ["get_weather_forecast"],
        "require_approval": "never",
    }

    prompt = (
        f"Use the get_weather_forecast tool for '{place}', days={days}, "
        f"units='{units}', lang='{lang}'. Return a concise summary."
    )

    resp = client.responses.create(
        model=OPENAI_MODEL,
        tools=[mcp_tool],
        input=prompt,
    )

    print(resp.output_text)
    return resp

if __name__ == "__main__":
    ask_forecast()
